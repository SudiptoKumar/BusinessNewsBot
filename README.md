# BusinessNewsroom V1

## Channel

@BusinessNewsroom

## Purpose

Automated Bangladesh-focused business and economic news publishing. Version 1 is designed for simple, high-recall editorial selection: examine the previous 24 hours, prefer important and recent developments, remove duplicates and already-published events, then publish the top three Bangladesh and top three International stories.

## Hourly publishing

The bot runs only in `update` mode and targets **6 stories per hourly run**:

- 3 Bangladesh business/economic stories
- 3 International business/economic stories

The regional target is handled independently. There is no cross-region competition and no 100-point score formula.

If a region genuinely has fewer than three eligible, verified stories after searching the full 24-hour window and all discovery layers, the bot does not invent stories. It logs the shortfall.

## Version 1 selection philosophy

1. Search the previous 24 hours, not just the last hour.
2. Discover broadly from RSS, Google News RSS, and Exa gap-fill.
3. Remove only obvious junk and exact/near-exact duplicates.
4. Remove events already published.
5. Let an editorial LLM rank candidates by actual news importance.
6. Prefer newer news when importance is otherwise similar.
7. Keep the candidate pool large enough to replace generation or verification failures.
8. Generate and verify the best candidates.
9. Publish the top three valid Bangladesh stories and top three valid International stories.

There is deliberately no numeric 100-point scoring system.

## What does not affect selection

Bank Job preparation, BCS preparation, viva preparation, study value, and exam relevance are not selection criteria. `What to Know` is story-related reader knowledge only.

## Pipeline

RSS → Google News RSS → Exa gap-fill → normalization → light noise filtering → URL deduplication → conservative event deduplication → already-published removal → intelligent editorial ranking → regional top candidates → article extraction → story generation → numeric/claim verification → Telegram publication → state update.

## Event deduplication

Multiple articles describing the same real-world event are reduced to one representative event. The clustering is conservative: uncertain matches are kept rather than discarded.

## 24-hour lookback

Every run considers approximately the previous 24 hours. Newer stories are preferred when importance is otherwise similar. This gives the bot a recovery window when an earlier hourly run missed a story because of a feed, API, or extraction problem.

## Output structure

1. Photo
2. Heading
3. One-line Summary
4. Key Highlights
5. What to Know (collapsed)
6. Vocabulary (collapsed)
7. Hashtags
8. Source

No Key Context, Exam Focus, or other dynamic top-level sections.

## Branding

Images use only `@BusinessNewsroom` branding.

## Schedule

Bangladesh time (UTC+6): 07:00 through 23:00 every hour.

GitHub Actions uses the equivalent UTC cron schedule in `.github/workflows/newbot.yml`.

## State

`posted_urls.txt` stores canonical URLs already published.

`news_state.json` stores the queue, published events, feed health, event clusters, category metadata, and recent titles.

## Required secrets

- `EXA_API_KEY`
- `CEREBRAS_API_KEY`
- `TELEGRAM_BOT_TOKEN`

## Explicitly removed

- Breaking-news detection
- Business News Watchdog
- 5-minute watchdog schedule
- Underdog feature
- Morning mode
- Roundup mode
- 100-point editorial score
- Regional soft-balance score
- Hard 3+2 quota
- Exam/Bank Job/BCS/viva/study selection logic
- Key Context
- Exam Focus

## Reliability

The bot keeps verification at the end of the pipeline. A candidate that fails extraction, generation, numeric grounding, claim verification, or Telegram publication does not cause the pipeline to lower standards; the selection pool provides another ranked candidate.
