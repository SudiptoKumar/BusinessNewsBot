"""Pure editorial selection logic for BusinessNewsroom.

No external dependencies. The selector enforces the publish threshold and the
Bangladesh/International minimum-diversity rule without imposing a regional
quota.
"""

PUBLISH_SCORE_THRESHOLD = 80
DEFAULT_MAX_POSTS_PER_RUN = 20


def _score(item):
    try:
        return int(item.get("editor_score", item.get("score", 0)))
    except (TypeError, ValueError):
        return 0


def _rank_key(item):
    score = _score(item)
    rank = item.get("editor_rank", 999999)
    try:
        rank = int(rank)
    except (TypeError, ValueError):
        rank = 999999
    return (-score, rank, str(item.get("canonical", "")))


def select_publishable_stories(
    bd_stories,
    intl_stories,
    threshold=PUBLISH_SCORE_THRESHOLD,
    max_posts=DEFAULT_MAX_POSTS_PER_RUN,
):
    """Select publishable stories by score with a two-region diversity floor.

    Rules:
    - Only stories at or above ``threshold`` are eligible.
    - If both regions have eligible stories, the strongest story from each
      region is guaranteed inclusion.
    - Remaining eligible stories compete globally by score.
    - No fixed Bangladesh/International quota exists.
    - No story below the threshold is inserted to create diversity.
    - Duplicate canonical URLs are removed.
    - ``max_posts`` is a safety ceiling, not a target.
    """
    try:
        threshold = int(threshold)
    except (TypeError, ValueError):
        threshold = PUBLISH_SCORE_THRESHOLD
    threshold = max(0, min(100, threshold))

    try:
        max_posts = int(max_posts)
    except (TypeError, ValueError):
        max_posts = DEFAULT_MAX_POSTS_PER_RUN
    max_posts = max(1, max_posts)

    eligible = []
    seen = set()
    for region, items in (("Bangladesh", bd_stories), ("International", intl_stories)):
        for item in items or []:
            if _score(item) < threshold:
                continue
            key = str(item.get("canonical") or item.get("url") or item.get("headline") or "")
            if not key or key in seen:
                continue
            row = dict(item)
            row["region"] = region
            row["editor_score"] = _score(row)
            seen.add(key)
            eligible.append(row)

    if not eligible:
        return []

    eligible.sort(key=_rank_key)

    by_region = {
        "Bangladesh": [x for x in eligible if x.get("region") == "Bangladesh"],
        "International": [x for x in eligible if x.get("region") == "International"],
    }

    selected = []
    selected_keys = set()

    # Diversity floor only applies when both sides actually have qualifying news.
    if by_region["Bangladesh"] and by_region["International"]:
        for region in ("Bangladesh", "International"):
            anchor = by_region[region][0]
            key = str(anchor.get("canonical") or anchor.get("url") or anchor.get("headline") or "")
            if key not in selected_keys:
                selected.append(anchor)
                selected_keys.add(key)

    for item in eligible:
        key = str(item.get("canonical") or item.get("url") or item.get("headline") or "")
        if key in selected_keys:
            continue
        selected.append(item)
        selected_keys.add(key)
        if len(selected) >= max_posts:
            break

    # Importance determines public order. Diversity only determines inclusion.
    selected.sort(key=_rank_key)
    return selected[:max_posts]
