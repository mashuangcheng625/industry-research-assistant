"""Embedding provider routing and vector-collection identity contracts."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Literal


EmbeddingRouteName = Literal["cloud", "local"]
EmbeddingRoutingMode = Literal["cloud", "local", "hybrid"]
VALID_EMBEDDING_MODES = {"cloud", "local", "hybrid"}


class EmbeddingRoutingError(ValueError):
    """Embedding route is invalid or unavailable."""


@dataclass(frozen=True)
class EmbeddingRoute:
    name: EmbeddingRouteName
    provider: str
    api_key: str
    base_url: str
    model: str
    dimensions: int
    version: str = "v1"

    @property
    def model_slug(self) -> str:
        aliases = {
            "text-embedding-v4": "text_v4",
            "bge-m3": "bge_m3",
        }
        return aliases.get(
            self.model,
            re.sub(r"[^a-z0-9]+", "_", self.model.casefold()).strip("_"),
        )

    @property
    def fingerprint(self) -> str:
        return f"{self.provider}:{self.model}:{self.dimensions}:{self.version}"

    def public_info(self) -> dict[str, object]:
        return {
            "route": self.name,
            "provider": self.provider,
            "model": self.model,
            "dimensions": self.dimensions,
            "version": self.version,
            "configured": bool(self.api_key and self.base_url and self.model),
        }


def get_embedding_route(name: EmbeddingRouteName) -> EmbeddingRoute:
    if name == "cloud":
        return EmbeddingRoute(
            name="cloud",
            provider=os.getenv("CLOUD_EMBEDDING_PROVIDER", "bailian"),
            api_key=(
                os.getenv("CLOUD_EMBEDDING_API_KEY")
                or os.getenv("EMBEDDING_API_KEY")
                or os.getenv("DASHSCOPE_API_KEY", "")
            ),
            base_url=os.getenv(
                "CLOUD_EMBEDDING_BASE_URL",
                os.getenv(
                    "EMBEDDING_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
            ),
            model=os.getenv(
                "CLOUD_EMBEDDING_MODEL",
                os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
            ),
            dimensions=int(os.getenv(
                "CLOUD_EMBEDDING_DIMENSIONS",
                os.getenv("EMBEDDING_DIMENSIONS", "1024"),
            )),
            version=os.getenv("CLOUD_EMBEDDING_VERSION", "v1"),
        )
    if name == "local":
        return EmbeddingRoute(
            name="local",
            provider=os.getenv("LOCAL_EMBEDDING_PROVIDER", "ollama"),
            api_key=os.getenv("LOCAL_EMBEDDING_API_KEY", "ollama"),
            base_url=os.getenv(
                "LOCAL_EMBEDDING_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ),
            model=os.getenv("LOCAL_EMBEDDING_MODEL", "bge-m3"),
            dimensions=int(os.getenv("LOCAL_EMBEDDING_DIMENSIONS", "1024")),
            version=os.getenv("LOCAL_EMBEDDING_VERSION", "v1"),
        )
    raise EmbeddingRoutingError(f"不支持的 Embedding 路由: {name}")


def resolve_embedding_mode(requested_mode: str | None = None) -> EmbeddingRoutingMode:
    mode = (requested_mode or os.getenv("EMBEDDING_ROUTING_MODE", "cloud")).lower()
    if mode not in VALID_EMBEDDING_MODES:
        raise EmbeddingRoutingError(f"不支持的 Embedding 模式: {mode}")
    return mode  # type: ignore[return-value]


def routes_for_mode(mode: str | None = None) -> tuple[EmbeddingRoute, ...]:
    resolved = resolve_embedding_mode(mode)
    if resolved == "hybrid":
        return (get_embedding_route("cloud"), get_embedding_route("local"))
    return (get_embedding_route(resolved),)  # type: ignore[arg-type]


def routes_for_ingestion() -> tuple[EmbeddingRoute, ...]:
    return routes_for_mode(
        os.getenv("EMBEDDING_INGEST_MODE", os.getenv("EMBEDDING_ROUTING_MODE", "cloud"))
    )


def normalize_collection_base(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", name.casefold()).strip("_")
    return normalized or "knowledge"


def collection_name_for_route(base_name: str, route: EmbeddingRoute) -> str:
    base = normalize_collection_base(base_name)
    suffix = f"_{route.model_slug}_{route.dimensions}_{route.version}"
    return base if base.endswith(suffix) else f"{base}{suffix}"


def route_collections(base_name: str, routes: Iterable[EmbeddingRoute]) -> dict[str, str]:
    return {route.name: collection_name_for_route(base_name, route) for route in routes}


def get_embedding_routing_status() -> dict[str, object]:
    mode = resolve_embedding_mode()
    routes = {
        name: get_embedding_route(name).public_info()
        for name in ("cloud", "local")
    }
    return {
        "requested_mode": mode,
        "active_routes": [route.name for route in routes_for_mode(mode)],
        "routes": routes,
    }
