"""Embedding route identity, collection isolation, and Hybrid fusion tests."""

from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.embedding_router import (  # noqa: E402
    EmbeddingRoutingError,
    collection_name_for_route,
    get_embedding_route,
    routes_for_mode,
)
from service.retrieval_service import retrieve_content  # noqa: E402


class EmbeddingRoutingTests(unittest.TestCase):
    def test_cloud_and_local_use_isolated_collections(self):
        with patch.dict(os.environ, {}, clear=True):
            cloud = get_embedding_route("cloud")
            local = get_embedding_route("local")
        self.assertEqual(
            collection_name_for_route("kb_Packaging Testing", cloud),
            "kb_packaging_testing_text_v4_1024_v1",
        )
        self.assertEqual(
            collection_name_for_route("kb_Packaging Testing", local),
            "kb_packaging_testing_bge_m3_1024_v1",
        )

    def test_hybrid_mode_resolves_both_routes(self):
        with patch.dict(os.environ, {"EMBEDDING_ROUTING_MODE": "hybrid"}, clear=True):
            self.assertEqual(
                [route.name for route in routes_for_mode()],
                ["cloud", "local"],
            )

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(EmbeddingRoutingError):
            routes_for_mode("automatic")

    def test_hybrid_rrf_deduplicates_and_maps_rerank_scores(self):
        cloud_results = [
            {
                "id": 1,
                "chunk_id": "shared",
                "document_id": "doc-a",
                "document_name": "a.md",
                "content_with_weight": "shared cloud text",
                "chunk_index": 0,
                "score": 0.9,
                "query_relevance_scores": [0.9, 0.1],
                "query_variant_count": 2,
            },
            {
                "id": 2,
                "chunk_id": "cloud-only",
                "document_id": "doc-b",
                "document_name": "b.md",
                "content_with_weight": "cloud only",
                "chunk_index": 0,
                "score": 0.8,
                "query_relevance_scores": [0.8, 0.0],
                "query_variant_count": 2,
            },
        ]
        local_results = [
            {
                "id": 1,
                "chunk_id": "shared",
                "document_id": "doc-a",
                "document_name": "a.md",
                "content_with_weight": "shared local text",
                "chunk_index": 0,
                "score": 0.7,
                "query_relevance_scores": [0.7, 0.2],
                "query_variant_count": 2,
            },
            {
                "id": 2,
                "chunk_id": "local-only",
                "document_id": "doc-c",
                "document_name": "c.md",
                "content_with_weight": "local only",
                "chunk_index": 0,
                "score": 0.6,
                "query_relevance_scores": [0.0, 0.95],
                "query_variant_count": 2,
            },
        ]

        def fake_single(collection_name, *args, **kwargs):
            kwargs.get("diagnostics", {}).update({"status": "ok"})
            return local_results if "bge_m3" in collection_name else cloud_results

        environment = {
            "EMBEDDING_ROUTING_MODE": "hybrid",
            "HYBRID_CLOUD_TOP_K": "20",
            "HYBRID_LOCAL_TOP_K": "20",
        }
        with patch.dict(os.environ, environment, clear=True), \
             patch("service.retrieval_service._retrieve_content_single", side_effect=fake_single), \
             patch("service.retrieval_service.rerank_scores", return_value=[0.9, 0.8, 0.1]):
            results = retrieve_content("kb_demo", "question", top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["score"], 0.9)
        shared = next(result for result in results if result["chunk_id"] == "shared")
        self.assertEqual(shared["retrieval_routes"], ["cloud", "local"])
        self.assertIsNone(shared["degraded_route"])
        self.assertEqual(shared["query_relevance_scores"], [0.9, 0.2])
        self.assertIn("local-only", {result["chunk_id"] for result in results})

    def test_hybrid_surfaces_single_route_degradation(self):
        local_result = [{
            "id": 1,
            "chunk_id": "local-only",
            "document_id": "doc-c",
            "document_name": "c.md",
            "content_with_weight": "local evidence",
            "chunk_index": 0,
            "score": 0.6,
        }]

        def fake_single(collection_name, *args, **kwargs):
            diagnostics = kwargs.get("diagnostics", {})
            if "bge_m3" in collection_name:
                diagnostics.update({"status": "ok"})
                return local_result
            diagnostics.update({"status": "error", "error_type": "embedding_unavailable"})
            return []

        with patch.dict(os.environ, {"EMBEDDING_ROUTING_MODE": "hybrid"}, clear=True), \
             patch("service.retrieval_service._retrieve_content_single", side_effect=fake_single), \
             patch("service.retrieval_service.rerank_scores", return_value=[0.8]):
            results = retrieve_content("kb_demo", "question", top_k=1)

        self.assertEqual(results[0]["degraded_route"], ["cloud"])
        self.assertEqual(results[0]["retrieval_routes"], ["local"])


if __name__ == "__main__":
    unittest.main()
