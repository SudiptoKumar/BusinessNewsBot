# BusinessNewsroom V1: Multi-API Setup

## GitHub Secrets

Create these repository secrets under **Settings → Secrets and variables → Actions**:

Required:

- `EXA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `CEREBRAS_API_KEY_1`

Optional additional AI slots:

- `CEREBRAS_API_KEY_2`
- `CEREBRAS_API_KEY_3`
- `CEREBRAS_API_KEY_4`
- `CEREBRAS_API_KEY_5`
- `CEREBRAS_API_KEY_6`
- `CEREBRAS_API_KEY_7`
- `CEREBRAS_API_KEY_8`
- `CEREBRAS_API_KEY_9`
- `CEREBRAS_API_KEY_10`

Optional: `TELEGRAM_ADMIN_CHAT_ID`, `CEREBRAS_MODEL`.

You can run with only two keys, three keys, or any other number from 1 to 10. Empty slots are ignored. Sparse configurations also work, such as only `_2` and `_3`.

## How failover works

The bot starts with the **last successful API slot** stored in `news_state.json`. It does not test every key at the start of every hourly run.

Example:

```text
Run 1: API 1 succeeds → API 1 remains preferred
Run 2: API 1 hits quota → API 2 succeeds → API 2 becomes preferred
Run 3: API 2 succeeds → start with API 2
Run 4: API 2 hits quota → API 3 succeeds → API 3 becomes preferred
```

Temporary failures such as HTTP 429, 5xx, timeouts, and quota/rate-limit errors trigger failover and a cooldown. Once the cooldown expires, the old slot becomes eligible again. Permanent request/configuration errors do not trigger blind rotation.

Only non-secret routing metadata is saved. API key values are never stored in `news_state.json` and are never written to logs.

## Upgrade from the old single-key setup

The workflow still accepts the old `CEREBRAS_API_KEY` secret as a temporary fallback for slot 1. The recommended setup is to create `CEREBRAS_API_KEY_1` and move additional keys to `_2`, `_3`, etc.

## Local verification

```bash
python -m py_compile main.py ai_router.py
python -m unittest discover -s tests -v
```

The GitHub Actions workflow also runs the existing application self-test before the live bot run.
