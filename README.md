# BusinessNewsroom V1

> Automated business and economic news intelligence for Telegram, powered by GitHub Actions, Exa, and Cerebras.

BusinessNewsroom V1 discovers, filters, ranks, verifies, and publishes **five high-value business/economic stories per run**:

- **3 Bangladesh**
- **2 International**

The system is designed for frequent automated publishing while keeping editorial selection strict and source control explicit.

---

## Editorial Mission

BusinessNewsroom is not intended to publish every business story it can find.

Its job is to identify the **most useful, material, recent, and factually supportable developments** within the current news window.

The editorial system therefore prioritizes:

- Material economic developments
- Banking and monetary policy
- Markets and financial conditions
- Trade and tariffs
- Currency and reserves
- Inflation and macroeconomic indicators
- Commodities and energy
- Major corporate/business developments
- International institutions and economic policy
- Stories with clear relevance to readers now

Routine, promotional, duplicate, stale, opinion-only, and weakly supported material is deprioritized.

---

# Source Strategy

## Primary Sources

The primary source universe contains **10 trusted publications**.

### Bangladesh

| Source | Domain |
|---|---|
| The Business Standard | `tbsnews.net` |
| The Financial Express | `thefinancialexpress.com.bd` |
| The Daily Star | `thedailystar.net` |
| Dhaka Tribune | `dhakatribune.com` |
| New Age | `newagebd.net` |

### International

| Source | Domain |
|---|---|
| Reuters | `reuters.com` |
| Bloomberg | `bloomberg.com` |
| Financial Times | `ft.com` |
| Visual Capitalist | `visualcapitalist.com` |
| The Economist | `economist.com` |

These sources form the normal discovery universe.

## Fallback Sources

Fallback sources are **not mixed into the primary pool by default**.

They are opened only when the primary sources cannot provide enough eligible stories for a region.

### International fallback examples

- Yahoo Finance
- Forbes
- CNBC
- MarketWatch
- Investing.com
- Fortune

### Bangladesh fallback examples

- bdnews24
- The Business Post
- Prothom Alo English
- UNB

The fallback list is configurable.

### Fallback principle

A fallback article is judged by the **same editorial standard** as a primary article.

There is no permanent source-quality score.

A strong fallback article can beat a weak primary article when a regional slot must be filled.

---

# Discovery Architecture

The system uses multiple discovery mechanisms because individual publisher feeds can fail, lag, or expose incomplete coverage.

```text
                 ┌──────────────┐
                 │     RSS      │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │ Google News  │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │     Exa      │
                 └──────┬───────┘
                        │
                        ▼
              Candidate Collection
                        │
                        ▼
                Source Validation
                        │
                        ▼
                24-Hour Filtering
                        │
                        ▼
             URL + Event Deduplication
                        │
                        ▼
                Editorial Ranking
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       Bangladesh Pool      International Pool
              │                   │
              ▼                   ▼
          Best 3               Best 2
              │                   │
              └─────────┬─────────┘
                        │
                        ▼
              Article Extraction
                        │
                        ▼
             Story Generation
                        │
                        ▼
           Numeric / Claim Checks
                        │
                        ▼
                 Telegram
```

---

# 24-Hour Editorial Window

Each run considers recent news within a rolling **24-hour discovery window**.

The system does not simply publish the newest five URLs.

Instead, it compares eligible candidates and determines which developments are most important.

When two stories cover essentially the same event, the system attempts to treat them as one event rather than publishing duplicate coverage.

---

# Regional Selection

The Bangladesh and International pools are ranked **independently**.

The target is:

```text
Bangladesh      → 3 stories
International   → 2 stories
Total           → 5 stories
```

A strong Bangladesh story therefore competes against other Bangladesh stories, while international stories compete inside the International pool.

This protects the required **3 + 2 editorial structure**.

---

# Fallback Logic

Fallback is triggered **only when the primary pool is insufficient**.

For each region:

```text
Primary sources
      │
      ▼
Enough eligible stories?
      │
   ┌──┴──┐
  YES    NO
   │      │
   │      ▼
   │   Open fallback
   │      │
   │      ▼
   │   Search missing slots
   │      │
   │      ▼
   └──► Same filtering
          │
          ▼
       Same ranking
          │
          ▼
      Fill missing slots
```

### Example

Suppose Bangladesh produces:

```text
20 candidates
↓
duplicates / stale / irrelevant / already published
↓
2 strong eligible stories
```

The system searches Bangladesh fallback sources for the missing third story.

If the primary pool already contains three strong eligible stories, fallback is not needed.

---

# Editorial Ranking

The ranking system does **not** assign fixed source-quality points.

There is no rule such as:

```text
Reuters = 10
TBS = 9
New Age = 7
```

The publication is judged at the **article level**.

The editor considers factors such as:

1. Importance of the development
2. Material economic or business impact
3. Policy significance
4. Market significance
5. Freshness
6. Factual substance
7. Evidence available in the source material
8. Reader relevance
9. Originality
10. Whether the story represents a genuinely new development

It deprioritizes:

- Exact duplicates
- Routine low-impact updates
- Promotional material
- Opinion/editorial pieces without new factual developments
- Lifestyle/entertainment material
- Weak or unsupported claims

The LLM is used as an **editorial ranking layer**, not as an unrestricted source selector.

---

# No Source Rotation

The system does not force source rotation.

If the best three Bangladesh stories happen to come from:

```text
TBS
TBS
The Daily Star
```

that is acceptable.

If New Age publishes the strongest story in a cycle, it can win.

The goal is **best news selection**, not artificial source balancing.

---

# Article Processing

After selection, the system retrieves and processes the original article.

The existing pipeline supports:

- Article extraction
- Source text cleanup
- Thin-excerpt enrichment
- Structured LLM generation
- Numeric grounding
- Claim verification
- Event/state tracking
- Image handling
- Telegram Rich Message publication

A discovery result is not treated as sufficient evidence when deeper article content is available.

---

# Publication Format

BusinessNewsroom retains its established Rich Message structure.

Each published story contains:

1. Image
2. Headline
3. One-line summary
4. Key highlights
5. What to Know
6. Vocabulary
7. Hashtags
8. Source
9. Original article URL

The publication layer is intentionally separate from candidate discovery and editorial ranking.

---

# State Management

The bot maintains persistent state in:

```text
news_state.json
posted_urls.txt
```

### `news_state.json`

Tracks operational information such as:

- Candidate queue
- Events
- Event clusters
- Published event IDs
- Recent titles
- Feed health
- Category coverage

### `posted_urls.txt`

Maintains URL-level publication history.

This prevents the scheduler from repeatedly publishing the same article.

**Do not overwrite these files when deploying an updated `main.py`.**

---

# GitHub Actions

The bot can run automatically through GitHub Actions.

The workflow uses Bangladesh time:

```yaml
on:
  schedule:
    - cron: "0 7-23 * * *"
      timezone: "Asia/Dhaka"
  workflow_dispatch:
```

This means the workflow is scheduled hourly from **07:00 through 23:00 Asia/Dhaka**, with manual execution also available.

The workflow:

1. Checks out the repository
2. Installs Python
3. Installs dependencies
4. Runs a syntax check
5. Executes `main.py`
6. Saves updated state
7. Commits state changes back to the repository

---

# Required GitHub Secrets

Configure one or more Cerebras keys. The bot supports up to 10 slots. Empty/unset slots are skipped, so you can use only 2 or 3 keys today and add more later without changing the Python code.

```text
EXA_API_KEY
CEREBRAS_API_KEY_1
CEREBRAS_API_KEY_2
CEREBRAS_API_KEY_3
CEREBRAS_API_KEY_4
CEREBRAS_API_KEY_5
CEREBRAS_API_KEY_6
CEREBRAS_API_KEY_7
CEREBRAS_API_KEY_8
CEREBRAS_API_KEY_9
CEREBRAS_API_KEY_10
TELEGRAM_BOT_TOKEN
```

Only `CEREBRAS_API_KEY_1` is required for a minimum configuration. `CEREBRAS_API_KEY_2` through `_10` are optional.

Optional:

```text
TELEGRAM_ADMIN_CHAT_ID
CEREBRAS_MODEL
```

The default Cerebras model is configured by the application when `CEREBRAS_MODEL` is not supplied.

---

# Environment Variables

Typical workflow configuration:

```text
EXA_API_KEY
CEREBRAS_API_KEY_1
CEREBRAS_API_KEY_2
CEREBRAS_API_KEY_3
CEREBRAS_API_KEY_4
CEREBRAS_API_KEY_5
CEREBRAS_API_KEY_6
CEREBRAS_API_KEY_7
CEREBRAS_API_KEY_8
CEREBRAS_API_KEY_9
CEREBRAS_API_KEY_10
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL=@BusinessNewsroom
NEWS_MODE=update
PYTHONUNBUFFERED=1
```

---

# Multi-API AI Failover

The AI layer uses a **preferred API + failover** strategy rather than simple round-robin rotation.

```text
Last successful API
        │
        ▼
   Try preferred
        │
   ┌────┴────┐
 success    temporary failure
   │            │
   ▼            ▼
  done     next eligible API
                  │
                  ▼
          save successful API
          as new preferred API
```

The preferred API is persisted in `news_state.json`. Temporary failures such as rate limits, quota exhaustion, timeouts, and server-side 5xx failures place an API in cooldown. When its cooldown expires, that API becomes eligible again.

The bot never prints or stores the actual API key values. It stores only slot numbers and non-secret failure metadata.

A future deployment can add `CEREBRAS_API_KEY_4` through `_10` in GitHub Secrets without modifying the router code. Missing slots are ignored. The router also supports sparse slots, for example only `_2` and `_3` being configured.

### Secret migration

The workflow keeps backward compatibility with the old `CEREBRAS_API_KEY` secret as a temporary source for slot 1. For the new setup, create `CEREBRAS_API_KEY_1`, `_2`, and so on.

---

# Project Structure

```text
BusinessNewsroom/
│
├── main.py
├── ai_router.py
├── requirements.txt
├── news_state.json
├── posted_urls.txt
├── README.md
│
└── .github/
    └── workflows/
        └── newbot.yml
```

---

# Running Locally

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set the required environment variables:

```bash
export EXA_API_KEY="..."
export CEREBRAS_API_KEY_1="..."
export CEREBRAS_API_KEY_2="..."
export CEREBRAS_API_KEY_3="..."
# Add CEREBRAS_API_KEY_4 through _10 only when needed
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHANNEL="@BusinessNewsroom"
export NEWS_MODE="update"
```

Run:

```bash
python main.py
```

If the application exposes the self-test command in the current build:

```bash
python main.py --self-test
```

---

# Operational Principles

## 1. Quality over volume

The system should not fill a slot with obviously weak material simply because an article exists.

## 2. Five-story target

The normal objective is:

```text
3 Bangladesh
+
2 International
=
5 stories
```

## 3. Primary sources first

The 10 trusted sources are the first choice for discovery.

## 4. Fallback only when needed

Secondary sources are opened only to solve a genuine regional coverage shortage.

## 5. No source favoritism

No publication receives a permanent editorial quality multiplier.

## 6. No forced rotation

The system does not publish a weaker article merely to rotate publishers.

## 7. No duplicate events

Multiple articles covering the same underlying event should normally result in one selected story.

## 8. No invented facts

Generated content must remain grounded in the available source material.

## 9. Persistent memory

Published URLs and event state survive subsequent hourly runs.

## 10. Existing publication design stays intact

Discovery and selection can evolve without changing the established Telegram publication format.

---

# Pipeline Summary

```text
DISCOVER
   ↓
RSS + Google News + Exa
   ↓
PRIMARY 10-SOURCE WHITELIST
   ↓
24-HOUR WINDOW
   ↓
BASIC ELIGIBILITY
   ↓
DEDUPLICATION
   ↓
EVENT CLUSTERING
   ↓
EDITORIAL RANKING
   ↓
3 BANGLADESH + 3 INTERNATIONAL
   ↓
IF REGION IS SHORT
   ↓
OPEN REGIONAL FALLBACK SOURCES
   ↓
SAME QUALITY STANDARD
   ↓
FILL MISSING SLOTS
   ↓
ARTICLE EXTRACTION
   ↓
GENERATION
   ↓
NUMERIC + CLAIM VERIFICATION
   ↓
IMAGE / RICH MESSAGE
   ↓
TELEGRAM
   ↓
PERSIST STATE
```

---

## Version Philosophy

BusinessNewsroom V1 is built around a simple principle:

> **Control the source universe, judge the actual news, use fallback only when necessary, and preserve the publication experience.**

The system should behave like an automated newsroom rather than a generic news feed.
