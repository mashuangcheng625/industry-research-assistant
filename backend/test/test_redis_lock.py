"""Redis execution lock tests without a live Redis server."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.redis_client import RedisCache  # noqa: E402
from router.research_router import (  # noqa: E402
    ResearchRequest,
    acquire_research_run_lock,
)


class RedisLockTests(unittest.TestCase):
    def make_cache(self):
        cache = RedisCache.__new__(RedisCache)
        cache.client = MagicMock()
        return cache

    def test_acquire_lock_uses_atomic_set_nx_with_lease(self):
        cache = self.make_cache()
        cache.client.set.return_value = True

        acquired = cache.acquire_lock("research:1", "owner-a", expire=90)

        self.assertTrue(acquired)
        cache.client.set.assert_called_once_with(
            "research:1",
            "owner-a",
            nx=True,
            ex=90,
        )

    def test_lock_contention_and_redis_failure_are_distinct(self):
        cache = self.make_cache()
        cache.client.set.return_value = None
        self.assertFalse(cache.acquire_lock("research:1", "owner-a"))

        cache.client.set.side_effect = RuntimeError("redis down")
        self.assertIsNone(cache.acquire_lock("research:1", "owner-a"))

    def test_release_lock_is_compare_and_delete(self):
        cache = self.make_cache()
        cache.client.eval.return_value = 1

        released = cache.release_lock("research:1", "owner-a")

        self.assertTrue(released)
        args = cache.client.eval.call_args.args
        self.assertIn("redis.call('get'", args[0])
        self.assertEqual(args[1:], (1, "research:1", "owner-a"))

    def test_router_maps_contention_to_409_and_redis_failure_to_503(self):
        with patch(
            "router.research_router.cache.acquire_lock",
            return_value=False,
        ), self.assertRaises(HTTPException) as contention:
            acquire_research_run_lock("session-1")
        self.assertEqual(contention.exception.status_code, 409)

        with patch(
            "router.research_router.cache.acquire_lock",
            return_value=None,
        ), self.assertRaises(HTTPException) as unavailable:
            acquire_research_run_lock("session-1")
        self.assertEqual(unavailable.exception.status_code, 503)

    def test_v2_iteration_budget_is_bounded(self):
        self.assertEqual(
            ResearchRequest(query="q", max_iterations=1).max_iterations,
            1,
        )
        self.assertEqual(
            ResearchRequest(query="q", max_iterations=5).max_iterations,
            5,
        )
        with self.assertRaises(ValidationError):
            ResearchRequest(query="q", max_iterations=0)
        with self.assertRaises(ValidationError):
            ResearchRequest(query="q", max_iterations=6)


if __name__ == "__main__":
    unittest.main()
