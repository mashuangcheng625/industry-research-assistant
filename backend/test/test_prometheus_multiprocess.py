import os
from pathlib import Path
import subprocess
import sys
import tempfile

from scripts.run_backend import prepare_metrics_directory


APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _run_python(code: str, environment: dict[str, str]) -> str:
    return subprocess.check_output(
        [sys.executable, "-c", code],
        env=environment,
        text=True,
    )


def test_prepare_metrics_directory_removes_only_metric_databases(tmp_path):
    (tmp_path / "counter_123.db").write_text("stale", encoding="utf-8")
    marker = tmp_path / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    assert prepare_metrics_directory(str(tmp_path)) == tmp_path.resolve()
    assert not (tmp_path / "counter_123.db").exists()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_prometheus_multiprocess_registry_aggregates_worker_counters():
    with tempfile.TemporaryDirectory(
        prefix="prometheus-multiprocess-", dir="/tmp"
    ) as metrics_dir:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(APP_DIR)
        environment["PROMETHEUS_MULTIPROC_DIR"] = metrics_dir
        worker_code = (
            "from prometheus_client import Counter, Gauge; "
            "import sys; "
            "Counter('worker_contract_total', 'test counter').inc(float(sys.argv[1])); "
            "Gauge('worker_active_contract', 'test gauge', "
            "multiprocess_mode='livesum').inc()"
        )
        for increment in (1, 2):
            subprocess.run(
                [sys.executable, "-c", worker_code, str(increment)],
                check=True,
                env=environment,
            )

        exposition = _run_python(
            "from core.metrics import render_metrics; "
            "print(render_metrics()[0].decode('utf-8'))",
            environment,
        )
        assert "worker_contract_total 3.0" in exposition
        assert "worker_active_contract" not in exposition
