# BusinessNewsroom V1

Hourly automated business-news selection and Telegram publishing pipeline.

## Approved sources

International:
- Reuters
- Bloomberg
- Financial Times
- Visual Capitalist
- The Economist

Bangladesh:
- The Business Standard
- The Financial Express
- The Daily Star
- Dhaka Tribune
- New Age

All sources are treated equally. There is no source-quality score, source rotation, source-frequency penalty, or preferred publication.

## Pipeline

1. Exa searches only the 10 approved domains for recent business/economic news.
2. The candidate window covers the previous 24 hours.
3. Hard eligibility filtering removes non-business, promotional, stale, and already-published stories.
4. Local title/event similarity removes obvious duplicates.
5. Candidates are ranked by impact, importance, freshness, magnitude, factual substance, and reader usefulness.
6. Cerebras performs the final editorial comparison and selects at least six stories when six eligible candidates exist, with up to eight allowed for unusually news-heavy cycles.
7. Cerebras generates concise Telegram copy.
8. URLs, titles, timestamps, and event keys are stored in `news_state.json`; URL compatibility is preserved in `posted_urls.txt`.

## Secrets

Configure these GitHub Actions secrets:

- `EXA_API_KEY`
- `CEREBRAS_API_KEY`
- `TELEGRAM_BOT_TOKEN`

`TELEGRAM_CHANNEL` is already configured as `@BusinessNewsroom` in the workflow.

## Important

The workflow intentionally fails rather than publishing fewer than six when fewer than six eligible candidates are found. This protects the feed from inventing or padding news. If the requirement is an absolute six even during quiet periods, the retrieval strategy should be expanded before weakening editorial filters.
