import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import TestCase, main as unittest_main

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_router import CerebrasAPIRouter


class FakeError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, responses):
        self.responses = responses

    def create(self, **kwargs):
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


class RouterTests(TestCase):
    def make_router(self, keys, preferred=0):
        state = {"ai_router": {"preferred_api_index": preferred, "apis": {}}}
        persisted = []
        router = CerebrasAPIRouter(keys, "gpt-oss-120b", state, persisted.append)
        return router, state, persisted

    def test_single_configured_key_works(self):
        router, state, _ = self.make_router(["k1", "", "", ""])
        router.clients[0] = FakeClient(["ok"])
        self.assertEqual(router.chat_completion(), "ok")
        self.assertEqual(state["ai_router"]["preferred_api_index"], 0)

    def test_two_keys_failover_and_preference_persists(self):
        router, state, persisted = self.make_router(["k1", "k2", "", ""])
        router.clients[0] = FakeClient([FakeError("quota exceeded", 429)])
        router.clients[1] = FakeClient(["ok-2"])
        result = router.chat_completion()
        self.assertEqual(result, "ok-2")
        self.assertEqual(state["ai_router"]["preferred_api_index"], 1)
        self.assertTrue(persisted)

    def test_next_run_starts_with_last_successful_api(self):
        router, state, _ = self.make_router(["k1", "k2", "", ""], preferred=1)
        router.clients[1] = FakeClient(["ok-2"])
        router.clients[0] = FakeClient([FakeError("should not be called", 429)])
        result = router.chat_completion()
        self.assertEqual(result, "ok-2")
        self.assertEqual(len(router.clients[0].chat.completions.responses), 1)

    def test_three_keys_work_with_only_two_configured(self):
        router, _, _ = self.make_router(["k1", "k2", "", ""])
        router.clients[0] = FakeClient([FakeError("rate limit", 429)])
        router.clients[1] = FakeClient(["ok-2"])
        self.assertEqual(router.chat_completion(), "ok-2")

    def test_failover_to_third_key(self):
        router, state, _ = self.make_router(["k1", "k2", "k3", ""])
        router.clients[0] = FakeClient([FakeError("quota", 429)])
        router.clients[1] = FakeClient([FakeError("temporarily unavailable", 503)])
        router.clients[2] = FakeClient(["ok-3"])
        self.assertEqual(router.chat_completion(), "ok-3")
        self.assertEqual(state["ai_router"]["preferred_api_index"], 2)

    def test_permanent_error_does_not_rotate(self):
        router, _, _ = self.make_router(["k1", "k2", "", ""])
        router.clients[0] = FakeClient([FakeError("invalid model", 400)])
        router.clients[1] = FakeClient(["ok-2"])
        with self.assertRaises(FakeError):
            router.chat_completion()
        self.assertEqual(router.clients[1].chat.completions.responses, ["ok-2"])

    def test_exhausted_api_gets_cooldown(self):
        router, state, _ = self.make_router(["k1", "k2", "", ""])
        router.clients[0] = FakeClient([FakeError("quota", 429)])
        router.clients[1] = FakeClient(["ok-2"])
        router.chat_completion()
        api0 = state["ai_router"]["apis"]["0"]
        self.assertEqual(api0["status"], "temporarily_unavailable")
        self.assertIn("retry_after", api0)

    def test_expired_cooldown_recovers(self):
        router, state, _ = self.make_router(["k1", "k2", "", ""], preferred=1)
        state["ai_router"]["apis"]["0"] = {
            "status": "temporarily_unavailable",
            "failure_count": 1,
            "retry_after": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        }
        router.clients[1] = FakeClient(["ok-2"])
        router.clients[0] = FakeClient(["unexpected-api1"])
        self.assertEqual(router.chat_completion(), "ok-2")
        self.assertEqual(state["ai_router"]["apis"]["0"]["status"], "active")

    def test_all_temporary_failures(self):
        router, _, _ = self.make_router(["k1", "k2", "k3", ""])
        for idx in range(3):
            router.clients[idx] = FakeClient([FakeError("timeout", None)])
        with self.assertRaises(RuntimeError):
            router.chat_completion()

    def test_empty_slots_are_skipped(self):
        router, _, _ = self.make_router(["k1", "", "k3", ""])
        router.clients[0] = FakeClient([FakeError("quota", 429)])
        router.clients[2] = FakeClient(["ok-3"])
        self.assertEqual(router.chat_completion(), "ok-3")

    def test_ten_slots_supported_without_changing_router(self):
        keys = [f"k{i}" for i in range(1, 11)]
        router, _, _ = self.make_router(keys)
        router.clients[9] = FakeClient(["ok-10"])
        router.preferred = 9
        router.state["ai_router"]["preferred_api_index"] = 9
        self.assertEqual(router.chat_completion(), "ok-10")

    def test_sparse_slots_start_with_first_configured_slot(self):
        router, _, _ = self.make_router(["", "k2", "k3", ""])
        router.clients[1] = FakeClient(["ok-2"])
        router.clients[2] = FakeClient(["unused-3"])
        self.assertEqual(router.chat_completion(), "ok-2")

    def test_state_round_trip_preserves_preferred_slot_without_secrets(self):
        router, state, _ = self.make_router(["k1", "k2", "", ""])
        router.clients[0] = FakeClient([FakeError("quota", 429)])
        router.clients[1] = FakeClient(["ok-2"])
        router.chat_completion()
        reloaded = CerebrasAPIRouter(["k1", "k2", "", ""], "gpt-oss-120b", state)
        self.assertEqual(reloaded.preferred, 1)
        state_text = str(state)
        self.assertNotIn("k1", state_text)
        self.assertNotIn("k2", state_text)

    def test_missing_all_keys_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.make_router(["", "", "", ""])


if __name__ == "__main__":
    unittest_main()
