import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class CerebrasAPIRouter:
    """Preferred-key routing with persistent failover and cooldowns.

    Up to 10 API-key slots are supported. Empty slots are skipped, so the
    deployment can safely run with 1, 2, 3, or more configured keys.
    """

    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, keys, model, state, persist_callback=None):
        self.keys = list(keys)
        if not any(self.keys):
            raise RuntimeError(
                "No Cerebras API keys configured. Add at least "
                "CEREBRAS_API_KEY_1 in GitHub Actions Secrets."
            )
        self.model = model
        self.state = state
        self.persist_callback = persist_callback
        router_state = self.state.setdefault(
            "ai_router",
            {"preferred_api_index": 0, "apis": {}},
        )
        self.preferred = self._normalize_index(
            router_state.get("preferred_api_index", 0)
        )
        self.clients = {}
        self._normalize_api_state()

    @staticmethod
    def _normalize_index(value):
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    def _api_state(self, index):
        apis = self.state["ai_router"].setdefault("apis", {})
        return apis.setdefault(
            str(index),
            {"status": "active", "failure_count": 0},
        )

    def _normalize_api_state(self):
        now = datetime.now(timezone.utc)
        for idx, key in enumerate(self.keys):
            if not key:
                continue
            item = self._api_state(idx)
            retry_after = item.get("retry_after")
            if retry_after:
                try:
                    dt = datetime.fromisoformat(retry_after)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt <= now:
                        item["status"] = "active"
                        item.pop("retry_after", None)
                except ValueError:
                    item["status"] = "active"
                    item.pop("retry_after", None)
        self.state["ai_router"]["preferred_api_index"] = self.preferred

    @staticmethod
    def _exception_status_code(exc):
        for attr in ("status_code", "status"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
        return value if isinstance(value, int) else None

    @classmethod
    def _is_transient(cls, exc):
        status = cls._exception_status_code(exc)
        if status in cls.TRANSIENT_STATUS_CODES:
            return True
        text = str(exc).lower()
        transient_terms = (
            "rate limit",
            "ratelimit",
            "quota",
            "too many requests",
            "temporarily unavailable",
            "service unavailable",
            "gateway timeout",
            "bad gateway",
            "server error",
            "timed out",
            "timeout",
            "connection reset",
            "connection refused",
            "connection error",
        )
        return any(term in text for term in transient_terms)

    @staticmethod
    def _retry_after_seconds(exc):
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers:
            raw = headers.get("Retry-After") or headers.get("retry-after")
            if raw:
                try:
                    return max(1, int(float(raw)))
                except (TypeError, ValueError):
                    pass
        return None

    def _mark_failed(self, index, exc):
        item = self._api_state(index)
        item["status"] = "temporarily_unavailable"
        item["failure_count"] = int(item.get("failure_count", 0)) + 1
        item["last_error"] = str(exc)[:300]
        retry_seconds = self._retry_after_seconds(exc)
        if retry_seconds is None:
            retry_seconds = min(
                3600,
                30 * (2 ** min(item["failure_count"] - 1, 6)),
            )
        item["retry_after"] = (
            datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)
        ).isoformat()
        item["status_code"] = self._exception_status_code(exc)

    def _eligible_indices(self):
        now = datetime.now(timezone.utc)
        eligible = []
        for idx, key in enumerate(self.keys):
            if not key:
                continue
            item = self._api_state(idx)
            retry_after = item.get("retry_after")
            if retry_after:
                try:
                    dt = datetime.fromisoformat(retry_after)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt > now:
                        continue
                except ValueError:
                    pass
            if item.get("status") != "active":
                item["status"] = "active"
                item.pop("retry_after", None)
            eligible.append(idx)
        return eligible

    def _ordered_indices(self):
        eligible = self._eligible_indices()
        if not eligible:
            return []

        preferred = self.preferred if self.preferred in eligible else None
        if preferred is None:
            for offset in range(len(self.keys)):
                candidate = (self.preferred + offset) % len(self.keys)
                if candidate in eligible:
                    preferred = candidate
                    break

        ordered = [preferred]
        for offset in range(1, len(self.keys) + 1):
            candidate = (preferred + offset) % len(self.keys)
            if candidate in eligible and candidate not in ordered:
                ordered.append(candidate)
        return ordered

    def _client(self, index):
        client = self.clients.get(index)
        if client is None:
            # Lazy import keeps the router unit-testable without the SDK and
            # avoids constructing clients for unused/empty API slots.
            from cerebras.cloud.sdk import Cerebras
            client = Cerebras(api_key=self.keys[index])
            self.clients[index] = client
        return client

    def _persist(self):
        if self.persist_callback:
            self.persist_callback(self.state)

    def chat_completion(self, **kwargs):
        ordered = self._ordered_indices()
        if not ordered:
            raise RuntimeError(
                "All configured Cerebras API keys are temporarily unavailable."
            )

        last_transient = None
        for index in ordered:
            logger.info(
                "AI router: trying API slot %d of %d configured slots",
                index + 1,
                len(self.keys),
            )
            try:
                response = self._client(index).chat.completions.create(
                    model=self.model,
                    **kwargs,
                )
                item = self._api_state(index)
                item["status"] = "active"
                item["failure_count"] = 0
                item.pop("retry_after", None)
                item.pop("last_error", None)
                item.pop("status_code", None)
                if self.preferred != index:
                    self.preferred = index
                    self.state["ai_router"]["preferred_api_index"] = index
                    logger.info(
                        "AI router: API slot %d is now preferred",
                        index + 1,
                    )
                    self._persist()
                return response
            except Exception as exc:
                if not self._is_transient(exc):
                    logger.error(
                        "AI router: API slot %d permanent/configuration error: %s",
                        index + 1,
                        exc,
                    )
                    raise
                self._mark_failed(index, exc)
                last_transient = exc
                logger.warning(
                    "AI router: API slot %d temporary failure; failing over: %s",
                    index + 1,
                    exc,
                )
                self._persist()

        raise RuntimeError(
            "All configured Cerebras API keys are temporarily unavailable."
        ) from last_transient
