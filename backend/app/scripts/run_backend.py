"""Start Uvicorn after preparing Prometheus multiprocess storage."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MULTIPROCESS_DIR = "/tmp/prometheus_multiproc"


def prepare_metrics_directory(raw_path: str) -> Path:
    path = Path(raw_path).resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise ValueError("refusing to use a broad directory for Prometheus worker files")
    path.mkdir(parents=True, exist_ok=True)
    for database_file in path.glob("*.db"):
        database_file.unlink()
    return path


def main() -> int:
    metrics_dir = (
        os.getenv("PROMETHEUS_MULTIPROC_DIR") or DEFAULT_MULTIPROCESS_DIR
    )
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(
        prepare_metrics_directory(metrics_dir)
    )

    workers = max(int(os.getenv("WEB_CONCURRENCY", "1")), 1)
    import uvicorn

    uvicorn.run(
        "app_main:app",
        host="0.0.0.0",
        port=8000,
        workers=workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
