from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_contains_alembic_runtime_assets():
    dockerfile = (REPOSITORY_ROOT / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "COPY alembic /app/alembic" in dockerfile
    assert "COPY alembic.ini /app/alembic.ini" in dockerfile
    assert "COPY sample-data /app/sample-data" in dockerfile
    assert dockerfile.startswith("FROM python:3.12-slim-bookworm\n")
    assert "postgresql-client" in dockerfile
    assert "ENV PYTHONDONTWRITEBYTECODE=1" in dockerfile
    assert "PYTHONPATH=/app/app" in dockerfile
    assert 'CMD ["python", "/app/app/scripts/run_backend.py"]' in dockerfile


def test_compose_runs_migrations_before_backend_startup():
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    assert services["migrate"]["command"] == [
        "python",
        "/app/app/scripts/run_migrations.py",
    ]
    assert services["backend"]["depends_on"]["migrate"] == {
        "condition": "service_completed_successfully"
    }
    assert services["backend"]["environment"]["AUTO_CREATE_TABLES"] == "false"
    assert services["backend"]["environment"]["PROMETHEUS_MULTIPROC_DIR"] == (
        "/tmp/prometheus_multiproc"
    )
    assert services["migrate"]["image"] == services["backend"]["image"]


def test_compose_runs_persistent_worker_with_shared_upload_storage():
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    worker = services["task-worker"]

    assert worker["command"] == ["python", "/app/app/scripts/run_task_worker.py"]
    assert worker["image"] == services["backend"]["image"]
    assert worker["depends_on"]["redis"] == {"condition": "service_healthy"}
    assert "task_uploads:/data/task_uploads" in worker["volumes"]
    assert "task_uploads:/data/task_uploads" in services["backend"]["volumes"]
    assert services["backend"]["depends_on"]["task-worker"] == {
        "condition": "service_healthy"
    }


def test_compose_runs_transactional_outbox_dispatcher_before_api():
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    dispatcher = services["outbox-dispatcher"]

    assert dispatcher["command"] == [
        "python",
        "/app/app/scripts/run_outbox_dispatcher.py",
    ]
    assert dispatcher["image"] == services["backend"]["image"]
    assert dispatcher["depends_on"]["postgres"] == {"condition": "service_healthy"}
    assert dispatcher["depends_on"]["redis"] == {"condition": "service_healthy"}
    assert services["backend"]["depends_on"]["outbox-dispatcher"] == {
        "condition": "service_healthy"
    }
    assert services["backend"]["environment"][
        "READINESS_CHECK_OUTBOX_DISPATCHER"
    ] == "true"


def test_compose_postgres_has_no_competing_schema_initializer():
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    postgres_volumes = compose["services"]["postgres"]["volumes"]
    assert all("/docker-entrypoint-initdb.d" not in volume for volume in postgres_volumes)

    env_example = (REPOSITORY_ROOT / "backend" / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "AUTO_CREATE_TABLES=false" in env_example
