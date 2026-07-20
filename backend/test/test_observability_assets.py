import json
from pathlib import Path
import re

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GRAFANA_ROOT = REPOSITORY_ROOT / "docker" / "grafana"
DASHBOARD_PATH = (
    GRAFANA_ROOT / "dashboards" / "industry-research-operations.json"
)


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def test_grafana_datasource_and_dashboard_provider_are_provisioned():
    datasource = yaml.safe_load(
        (
            GRAFANA_ROOT / "provisioning" / "datasources" / "prometheus.yml"
        ).read_text(encoding="utf-8")
    )["datasources"][0]
    provider = yaml.safe_load(
        (
            GRAFANA_ROOT / "provisioning" / "dashboards" / "dashboards.yml"
        ).read_text(encoding="utf-8")
    )["providers"][0]

    assert datasource["uid"] == "prometheus"
    assert datasource["url"] == "http://prometheus:9090"
    assert datasource["isDefault"] is True
    assert provider["options"]["path"] == "/var/lib/grafana/dashboards"


def test_operations_dashboard_has_stable_identity_and_unique_panels():
    dashboard = _dashboard()
    panels = dashboard["panels"]
    panel_ids = [panel["id"] for panel in panels]

    assert dashboard["uid"] == "industry-research-operations"
    assert dashboard["title"] == "Semiconductor Research Agent Operations"
    assert dashboard["schemaVersion"] >= 39
    assert len(panels) >= 10
    assert len(panel_ids) == len(set(panel_ids))
    assert all(panel.get("description") for panel in panels)


def test_operations_dashboard_queries_only_bounded_research_metrics():
    expressions = [
        target["expr"]
        for panel in _dashboard()["panels"]
        for target in panel.get("targets", [])
    ]
    referenced_metrics = {
        match
        for expression in expressions
        for match in re.findall(r"industry_research_[a-z_]+", expression)
    }
    required_metrics = {
        "industry_research_active_runs",
        "industry_research_runs_total",
        "industry_research_run_duration_seconds_bucket",
        "industry_research_phase_duration_seconds_bucket",
        "industry_research_llm_duration_seconds_bucket",
        "industry_research_llm_tokens_total",
        "industry_research_checkpoint_operations_total",
        "industry_research_run_lock_operations_total",
        "industry_research_agent_timeouts_total",
        "industry_research_review_outcomes_total",
    }
    assert referenced_metrics == required_metrics
    assert all("session_id" not in expression for expression in expressions)


def test_compose_grafana_is_read_only_by_default_and_uses_prometheus():
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    grafana = compose["services"]["grafana"]

    assert grafana["image"] == "grafana/grafana:13.1.0"
    assert grafana["environment"]["GF_AUTH_ANONYMOUS_ORG_ROLE"] == "Viewer"
    assert grafana["environment"]["GF_USERS_ALLOW_SIGN_UP"] == "false"
    assert grafana["depends_on"] == ["prometheus"]
    assert "3000:3000" in grafana["ports"]
    assert grafana["healthcheck"]["retries"] == 10
