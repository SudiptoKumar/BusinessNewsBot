import os
import re
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse
from difflib import SequenceMatcher

import requests

EXA_API_URL = "https://api.exa.ai/search"
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

SOURCE_GROUPS = {
    "international": [
        "reuters.com",
        "bloomberg.com",
        "ft.com",
        "visualcapitalist.com",
        "economist.com",
    ],
    "bangladesh": [
        "tbsnews.net",
        "thefinancialexpress.com.bd",
        "thedailystar.net",
        "dhakatribune.com",
        "newagebd.net",
    ],
}
ALL_DOMAINS = SOURCE_GROUPS["international"] + SOURCE_GROUPS["bangladesh"]

# Equal source treatment is intentional. These are allowed sources, not ranked sources.

SEARCH_QUERIES = [
    "latest business economy finance markets banking companies trade investment policy",
    "latest major economic financial corporate market development",
    "latest business breaking news major companies banks central banks trade investment",
]

MAX_RESULTS_PER_QUERY = 8
TOP_FOR_EDITOR = 30
MINIMUM_OUTPUT = 6
MAXIMUM_OUTPUT = 8
LOOKBACK_HOURS = 24

STATE_FILE = "news_state.json"
POSTED_FILE = "posted_urls.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def utc_now():
    return datetime.now(timezone.utc)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_url(url):
    try:
        p = urlparse(url)
        clean = p._replace(query="", fragment="")
        return urlunparse(clean).rstrip("/")
    except Exception:
        return url.strip()


def domain_of(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def clean_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def tokenize(text):
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


def title_similarity(a, b):
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq * 0.85)


def load_state():
    state = {
        "posted": [],
        "events": [],
        "last_run": None,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    state.update(loaded)
        except Exception as exc:
            logging.warning("Could not read state: %s", exc)

    # Keep compatibility with the existing simple URL state file.
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                urls = [normalize_url(x.strip()) for x in f if x.strip()]
            existing = {normalize_url(x.get("url", "")) for x in state.get("posted", []) if isinstance(x, dict)}
            for url in urls:
                if url and url not in existing:
                    state["posted"].append({"url": url, "published_at": None, "title": ""})
        except Exception as exc:
            logging.warning("Could not read posted_urls.txt: %s", exc)
    return state


def save_state(state):
    state["last_run"] = utc_now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    urls = []
    seen = set()
    for item in state.get("posted", []):
        url = normalize_url(item.get("url", ""))
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(urls) + ("\n" if urls else ""))


def exa_search(query, domains, start_date):
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise RuntimeError("EXA_API_KEY is missing")

    payload = {
        "query": query,
        "type": "auto",
        "category": "news",
        "numResults": MAX_RESULTS_PER_QUERY,
        "includeDomains": domains,
        "startPublishedDate": start_date,
        "contents": {
            "highlights": {"query": query, "maxCharacters": 1800},
            "text": {"maxCharacters": 5000},
        },
    }
    r = requests.post(EXA_API_URL, headers={"x-api-key": key, "Content-Type": "application/json"}, json=payload, timeout=60)
    r.raise_for_status()
    return r.json().get("results", [])


def collect_candidates():
    start = (utc_now() - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    candidates = {}

    for group, domains in SOURCE_GROUPS.items():
        for query in SEARCH_QUERIES:
            try:
                results = exa_search(query, domains, start)
            except Exception as exc:
                logging.error("Exa search failed (%s): %s", group, exc)
                continue
            for r in results:
                url = normalize_url(r.get("url", ""))
                if not url or domain_of(url) not in ALL_DOMAINS:
                    continue
                title = clean_text(r.get("title", ""))
                if not title:
                    continue
                published = parse_dt(r.get("publishedDate"))
                if published and published < utc_now() - timedelta(hours=LOOKBACK_HOURS):
                    continue
                highlights = r.get("highlights") or []
                text = clean_text(r.get("text", ""))
                excerpt = clean_text(" ".join(highlights)) or text[:1800]
                candidates[url] = {
                    "url": url,
                    "title": title,
                    "domain": domain_of(url),
                    "group": group,
                    "published_at": published.isoformat() if published else None,
                    "excerpt": excerpt[:3000],
                    "text": text[:6000],
                }
    logging.info("Collected %d unique candidates", len(candidates))
    return list(candidates.values())


def posted_urls(state):
    return {normalize_url(x.get("url", "")) for x in state.get("posted", []) if isinstance(x, dict)}


def already_posted_event(candidate, state):
    title = candidate["title"]
    for item in state.get("posted", []):
        if not isinstance(item, dict):
            continue
        if title_similarity(title, item.get("title", "")) >= 0.82:
            return True
    return False


def hard_filter(candidates, state):
    posted = posted_urls(state)
    out = []
    for c in candidates:
        if c["url"] in posted:
            continue
        if already_posted_event(c, state):
            continue
        text = f"{c['title']} {c['excerpt']}".lower()
        # Narrow editorial eligibility. This is intentionally broad enough to support quiet hours.
        business_terms = [
            "econom", "market", "bank", "finance", "financial", "invest", "trade", "export", "import",
            "inflation", "interest rate", "central bank", "gdp", "tariff", "tax", "budget", "debt", "bond",
            "stock", "share", "currency", "oil", "gas", "energy", "company", "corporate", "earnings", "profit",
            "revenue", "merger", "acquisition", "ipo", "funding", "investment", "manufactur", "semiconductor",
            "artificial intelligence", "ai", "supply chain", "regulation", "policy", "employment", "jobs",
        ]
        if not any(term in text for term in business_terms):
            continue
        promotional_terms = ["sponsored", "advertorial", "promo code", "buy now", "press release only"]
        if sum(term in text for term in promotional_terms) >= 2:
            continue
        out.append(c)
    return out


def freshness_points(published_at):
    if not published_at:
        return 5
    dt = parse_dt(published_at)
    if not dt:
        return 5
    age = max(0, (utc_now() - dt).total_seconds() / 3600)
    if age <= 1: return 25
    if age <= 3: return 23
    if age <= 6: return 20
    if age <= 12: return 15
    if age <= 18: return 10
    return 6


def score_candidate(c):
    text = f"{c['title']} {c['excerpt']}".lower()
    score = freshness_points(c.get("published_at"))

    impact_terms = ["rate", "inflation", "gdp", "tariff", "sanction", "bank failure", "default", "billion", "trillion", "acquisition", "merger", "ipo", "earnings", "central bank", "budget"]
    magnitude_terms = ["major", "record", "surge", "plunge", "crisis", "largest", "first", "cut", "hike", "deal", "billion", "trillion"]
    factual_terms = ["%", "$", "€", "£", "bn", "billion", "million", "rate", "forecast", "data", "according"]
    relevance_terms = ["economy", "market", "bank", "finance", "investment", "trade", "company", "business", "energy", "policy"]

    impact = min(30, 5 + 5 * sum(t in text for t in impact_terms))
    magnitude = min(15, 3 + 3 * sum(t in text for t in magnitude_terms))
    factual = min(10, 2 + 2 * sum(t in text for t in factual_terms))
    relevance = min(20, 5 + 2 * sum(t in text for t in relevance_terms))
    importance = min(25, round((impact * 0.65) + (magnitude * 0.35)))
    return min(100, round(importance + score + magnitude + factual + relevance))


def local_dedupe(candidates):
    # Keep the strongest representative of highly similar titles.
    ranked = sorted(candidates, key=score_candidate, reverse=True)
    kept = []
    for c in ranked:
        if any(title_similarity(c["title"], k["title"]) >= 0.86 for k in kept):
            continue
        kept.append(c)
    return kept


def cerebras_json(prompt):
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        raise RuntimeError("CEREBRAS_API_KEY is missing")
    model = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b")
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_completion_tokens": 5000,
        "messages": [
            {"role": "system", "content": "You are a rigorous business-news editor. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
    }
    r = requests.post(CEREBRAS_API_URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=90)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("Cerebras did not return JSON")
    return json.loads(match.group(0))


def editorial_select(candidates):
    candidates = sorted(candidates, key=score_candidate, reverse=True)[:TOP_FOR_EDITOR]
    compact = []
    for i, c in enumerate(candidates):
        compact.append({
            "id": i,
            "title": c["title"],
            "source": c["domain"],
            "region": c["group"],
            "published_at": c["published_at"],
            "url": c["url"],
            "excerpt": c["excerpt"][:1600],
            "algorithm_score": score_candidate(c),
        })

    prompt = f"""
Select the strongest 6 to {MAXIMUM_OUTPUT} DISTINCT business/economic news stories for an hourly news update.

Rules:
- These 10 publications are the complete approved source universe. Treat EVERY publication equally.
- Never favor Reuters, Bloomberg, FT, TBS, New Age, or any other source.
- Do not use source identity as a quality signal.
- Judge the underlying NEWS, not the publication.
- Prefer genuinely recent developments within the last 24 hours.
- Prefer material economic, financial, market, corporate, trade, investment, energy, policy, or business developments.
- Do not select multiple articles covering the same underlying event unless one contains a genuinely material new development.
- Do not select routine/promotional/trivial items.
- There is NO numerical minimum score. If a story is eligible and is among the best available, it may be selected.
- The hourly target is at least 6 stories. Select 6 by default and up to 8 only when there are additional clearly useful stories.
- Do not enforce a Bangladesh/international quota. Choose the six strongest stories overall from the supplied candidates.
- If an article is older but materially more important than a new trivial article, it can win.
- Do not invent facts.

Return JSON exactly as:
{{"selected_ids":[1,2,3,4,5,6],"event_clusters":[{{"ids":[1,4],"same_event":true,"reason":"..."}}],"notes":"..."}}

Candidates:
{json.dumps(compact, ensure_ascii=False)}
"""
    try:
        result = cerebras_json(prompt)
        ids = result.get("selected_ids", [])
        selected = [candidates[int(i)] for i in ids if isinstance(i, int) and 0 <= i < len(candidates)]
        # Ensure at least six if the model under-selects.
        if len(selected) < MINIMUM_OUTPUT:
            selected_ids = {c["url"] for c in selected}
            for c in candidates:
                if c["url"] not in selected_ids:
                    selected.append(c)
                    selected_ids.add(c["url"])
                if len(selected) >= MINIMUM_OUTPUT:
                    break
        return selected[:MAXIMUM_OUTPUT]
    except Exception as exc:
        logging.warning("Editorial selection failed; using deterministic ranking: %s", exc)
        return candidates[:MAXIMUM_OUTPUT]


def generate_post(c):
    prompt = f"""
Create a concise Telegram business-news post from this article.
Do not invent information. Do not add a generic introduction.
Return JSON only with keys: headline, bullets, source.
headline: one strong factual headline.
bullets: exactly 3 concise factual bullets explaining what happened, key number/fact, and why it matters.
source: publication domain.

Title: {c['title']}
Source: {c['domain']}
Published: {c.get('published_at')}
Article excerpt:
{c['text'][:5000] or c['excerpt'][:3000]}
"""
    try:
        data = cerebras_json(prompt)
        headline = clean_text(data.get("headline", c["title"]))
        bullets = data.get("bullets", [])
        if not isinstance(bullets, list):
            bullets = [str(bullets)]
        bullets = [clean_text(str(x)) for x in bullets if clean_text(str(x))][:3]
        while len(bullets) < 3:
            bullets.append(c["excerpt"][:250])
        return headline, bullets, c["domain"]
    except Exception:
        return c["title"], [c["excerpt"][:300], "Source: " + c["domain"], "See the original article for full details."], c["domain"]


def telegram_send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL", "@BusinessNewsroom")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = TELEGRAM_API.format(token=token)
    r = requests.post(url, json={"chat_id": channel, "text": text, "disable_web_page_preview": False}, timeout=30)
    r.raise_for_status()


def record_post(state, c, event_key=None):
    state.setdefault("posted", []).append({
        "url": c["url"],
        "title": c["title"],
        "published_at": c.get("published_at"),
        "posted_at": utc_now().isoformat(),
        "event_key": event_key or hashlib.sha256(c["title"].lower().encode()).hexdigest()[:16],
        "domain": c["domain"],
    })
    # Keep a useful rolling history while preserving posted_urls compatibility.
    state["posted"] = state["posted"][-1000:]


def main():
    state = load_state()
    candidates = collect_candidates()
    candidates = hard_filter(candidates, state)
    logging.info("After hard filters: %d candidates", len(candidates))
    candidates = local_dedupe(candidates)
    logging.info("After local event dedupe: %d candidates", len(candidates))

    if len(candidates) < MINIMUM_OUTPUT:
        raise RuntimeError(f"Only {len(candidates)} eligible candidates found; cannot safely produce {MINIMUM_OUTPUT} stories")

    selected = editorial_select(candidates)
    selected = selected[:MAXIMUM_OUTPUT]
    if len(selected) < MINIMUM_OUTPUT:
        raise RuntimeError(f"Editorial selector returned only {len(selected)} stories")

    logging.info("Selected %d stories", len(selected))

    for idx, c in enumerate(selected, 1):
        headline, bullets, source = generate_post(c)
        text = f"{headline}\n\n" + "\n".join(f"• {b}" for b in bullets) + f"\n\nSource: {source}\n{c['url']}"
        telegram_send(text)
        record_post(state, c)
        logging.info("Published %d/%d: %s", idx, len(selected), c["title"])
        time.sleep(1)

    save_state(state)


if __name__ == "__main__":
    main()
