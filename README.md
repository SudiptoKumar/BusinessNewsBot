# BusinessNewsroom V1

Preserves the existing Telegram Rich Message structure and 3 Bangladesh + 3 International target.

Primary sources: TBS, The Financial Express, The Daily Star, Dhaka Tribune, New Age; Reuters, Bloomberg, Financial Times, Visual Capitalist, The Economist.

RSS, Google News RSS, and Exa remain discovery layers. A hard source whitelist prevents unapproved sources from entering the primary pool.

Fallback sources are opened independently by region only when the primary pool cannot produce all 3 verified stories. Fallback uses the same filtering, event deduplication, editorial ranking, extraction, generation, and verification.

There is no source-quality weighting, source rotation, or source-frequency penalty.
