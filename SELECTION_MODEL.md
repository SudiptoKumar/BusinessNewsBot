# BusinessNewsroom Ranked Publishing Model

## Goal

Replace fixed hourly story quotas with importance-driven editorial selection.

## Rules

1. Every ranked candidate receives an editorial score from 0 to 100.
2. `80` is the default publication threshold.
3. Only `score >= 80` is publishable.
4. There is no fixed 3 Bangladesh + 2 International quota.
5. If both Bangladesh and International have qualifying stories, include the strongest qualifying story from each.
6. After the two-region minimum is satisfied, rank all remaining qualifying stories globally by score.
7. Never insert a story below 80 to satisfy regional balance.
8. Zero qualifying stories means zero posts.
9. A configurable safety ceiling of 20 posts per run prevents accidental floods. It is not a target.
10. Region/category labels are internal metadata and are not shown in the public Telegram output.

## Pipeline

Collect -> normalize -> deduplicate/event cluster -> rank 0-100 -> threshold -> generate/verify -> diversity floor -> global ordering -> publish.

## Examples

20 qualifying stories -> publish 20.

5 qualifying stories -> publish 5.

2 qualifying Bangladesh + 0 qualifying International -> publish 2.

0 qualifying stories -> publish 0.

4 Bangladesh and 4 International qualifying stories are not forced into a 3+3 or 3+2 split. All 8 compete by score after the two-region minimum is secured.
