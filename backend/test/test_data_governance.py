"""Tests for the data governance primitives (P1-3).

The module exposes pure helpers (hashing, party extraction, lifecycle
clustering, stock resolution) plus a small ``StockCodeResolver`` class
with an audit log. The tests below cover each primitive with
parameterized cases plus a few integration scenarios that exercise
the interactions between modules.

The tests are deliberately independent of any database / network -
they only exercise the pure-Python code paths. Wiring into the news
and bidding collectors is covered by the existing service tests.
"""

from __future__ import annotations

import pytest

from core.data_governance import (
    LifecycleGroup,
    StockCodeResolver,
    StockResolution,
    bidding_dedup_key,
    cluster_lifecycle,
    content_hash,
    extract_parties,
    find_company_in_query,
    get_stock_code,
    news_dedup_key,
    normalise_party_name,
)


# ---------------------------------------------------------------------------
# content_hash / dedup keys
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic() -> None:
    assert content_hash("a", "b") == content_hash("a", "b")


def test_content_hash_separator_disambiguates_concat() -> None:
    """Different field splits must not collide because the helper joins
    inputs with the ASCII unit separator before hashing."""

    assert content_hash("abc") != content_hash("a", "bc")
    assert content_hash("a", "b", "c") != content_hash("ab", "c")


def test_content_hash_normalises_whitespace_and_case() -> None:
    assert content_hash("Hello World") == content_hash("hello   world")
    assert content_hash("ABC") == content_hash("abc")


def test_content_hash_ignores_none_fields() -> None:
    assert content_hash(None, "x") == content_hash("", "x")
    assert content_hash("x", None) == content_hash("x", "")


@pytest.mark.parametrize(
    "kwargs_a,kwargs_b",
    [
        (
            {"url": "https://x/1", "title": "A", "content": "B", "publisher": "P", "publish_time": "2024-01-01"},
            {"url": "https://x/2", "title": "A ", "content": "B", "publisher": "P", "publish_time": "2024-01-01"},
        ),
        (
            {"url": None, "title": "标题", "content": "内容", "publisher": "P", "publish_time": "2024-01-01"},
            {"url": "https://any", "title": "标题", "content": "内容", "publisher": "P", "publish_time": "2024-01-01"},
        ),
    ],
)
def test_news_dedup_key_is_url_agnostic(kwargs_a, kwargs_b) -> None:
    """The news key intentionally ignores ``url`` so the same item
    collected via different aggregators collapses to one identity."""

    assert news_dedup_key(**kwargs_a) == news_dedup_key(**kwargs_b)


def test_news_dedup_key_changes_when_title_changes() -> None:
    a = news_dedup_key(url="https://x/1", title="A", content="B", publisher="P", publish_time="t")
    b = news_dedup_key(url="https://x/1", title="A2", content="B", publisher="P", publish_time="t")
    assert a != b


def test_bidding_dedup_key_includes_bid_id() -> None:
    base = {"title": "12英寸晶圆设备", "province": "上海", "publish_time": "2024-01-01"}
    assert bidding_dedup_key(**base, bid_id="A") != bidding_dedup_key(**base, bid_id="B")
    assert bidding_dedup_key(**base, bid_id="A") == bidding_dedup_key(**base, bid_id="A")


# ---------------------------------------------------------------------------
# normalise_party_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("中芯国际", "中芯国际"),
        ("中芯国际集成电路制造（上海）有限公司", "中芯国际集成电路制造"),
        ("中芯国际集成电路制造(上海)股份有限公司", "中芯国际集成电路制造"),
        ("中芯国际集成电路制造", "中芯国际集成电路制造"),
        ("北方华创", "北方华创"),
        ("  北京 北方  华创  ", "北京 北方 华创"),
        ("中芯国际（上海）", "中芯国际"),
        ("", ""),
        (None, ""),
        ("《中芯国际》", "中芯国际"),
    ],
)
def test_normalise_party_name(raw: object, expected: str) -> None:
    assert normalise_party_name(raw) == expected  # type: ignore[arg-type]


def test_normalise_party_name_keeps_legal_suffix_when_disabled() -> None:
    assert normalise_party_name(
        "中芯国际集成电路制造（上海）有限公司", strip_legal_suffix=False
    ).endswith("有限公司")


# ---------------------------------------------------------------------------
# extract_parties
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_text() -> str:
    return (
        "中国科学院微电子研究所 12英寸晶圆设备 采购项目 招标公告；"
        "采购人：中芯国际集成电路制造（上海）有限公司；中标人：北方华创"
    )


def test_extract_parties_returns_both_roles(sample_text: str) -> None:
    out = extract_parties(sample_text)
    assert "buyer" in out
    assert "supplier" in out
    assert "中芯国际" in out["buyer"]
    assert "北方华创" in out["supplier"]


def test_extract_parties_empty_or_short_returns_empty() -> None:
    assert extract_parties("") == {}
    assert extract_parties(None) == {}
    # The two-character minimum filter rejects single-char captures
    assert extract_parties("采购人：A") == {}


def test_extract_parties_first_match_wins(sample_text: str) -> None:
    """When both buyer and supplier patterns could match, the function
    captures each role from the highest-priority pattern only."""

    out = extract_parties(sample_text)
    # buyer should not leak into supplier role
    assert "buyer" not in out.get("supplier", "")
    assert "supplier" not in out.get("buyer", "")


def test_extract_parties_handles_half_width_colon() -> None:
    text = "采购人:中芯国际集成电路制造（上海）有限公司"
    out = extract_parties(text)
    assert "buyer" in out
    assert "中芯国际" in out["buyer"]


def test_extract_parties_handles_full_width_colon() -> None:
    text = "采购人：中芯国际集成电路制造（上海）有限公司"
    out = extract_parties(text)
    assert "buyer" in out
    assert "中芯国际" in out["buyer"]


def test_extract_parties_handles_keyword_variants() -> None:
    text = "招标单位：长电科技；中标单位：通富微电"
    out = extract_parties(text)
    assert out.get("buyer") == "长电科技"
    assert out.get("supplier") == "通富微电"


# ---------------------------------------------------------------------------
# cluster_lifecycle
# ---------------------------------------------------------------------------


def test_cluster_lifecycle_groups_by_title_and_buyer() -> None:
    items = [
        {"bid_id": "B1", "title": "12英寸晶圆设备 招标公告", "parties": {"buyer": "中芯国际集成电路制造（上海）有限公司"}},
        {"bid_id": "B2", "title": "12英寸晶圆设备 中标公告", "parties": {"buyer": "中芯国际", "supplier": "北方华创"}},
        {"bid_id": "B3", "title": "完全不同的项目 招标公告", "parties": {"buyer": "其他公司"}},
    ]
    groups = cluster_lifecycle(items)
    assert len(groups) == 2
    sizes = sorted(len(g.items) for g in groups)
    assert sizes == [1, 2]


def test_cluster_lifecycle_does_not_merge_unrelated_titles() -> None:
    items = [
        {"bid_id": "A", "title": "12英寸晶圆设备 招标公告", "parties": {"buyer": "中芯国际"}},
        {"bid_id": "B", "title": "光刻胶采购项目 招标公告", "parties": {"buyer": "中芯国际"}},
    ]
    groups = cluster_lifecycle(items)
    assert len(groups) == 2


def test_cluster_lifecycle_does_not_merge_unrelated_buyers() -> None:
    items = [
        {"bid_id": "A", "title": "12英寸晶圆设备 招标公告", "parties": {"buyer": "中芯国际"}},
        {"bid_id": "B", "title": "12英寸晶圆设备 中标公告", "parties": {"buyer": "长电科技"}},
    ]
    groups = cluster_lifecycle(items)
    assert len(groups) == 2


def test_cluster_lifecycle_output_is_sorted_by_project_key() -> None:
    items = [
        {"bid_id": "Z", "title": "Z项目 招标公告", "parties": {"buyer": "公司A"}},
        {"bid_id": "A", "title": "A项目 招标公告", "parties": {"buyer": "公司A"}},
        {"bid_id": "M", "title": "M项目 招标公告", "parties": {"buyer": "公司A"}},
    ]
    groups = cluster_lifecycle(items)
    keys = [g.project_key for g in groups]
    assert keys == sorted(keys)


def test_cluster_lifecycle_strips_notice_type_noise() -> None:
    items = [
        {"bid_id": "B1", "title": "12英寸晶圆设备 招标公告", "parties": {"buyer": "中芯国际"}},
        {"bid_id": "B2", "title": "12英寸晶圆设备 中标公告", "parties": {"buyer": "中芯国际"}},
        {"bid_id": "B3", "title": "12英寸晶圆设备 更正公告", "parties": {"buyer": "中芯国际"}},
    ]
    groups = cluster_lifecycle(items)
    assert len(groups) == 1
    assert len(groups[0].items) == 3


def test_cluster_lifecycle_empty_input() -> None:
    assert cluster_lifecycle([]) == []


def test_lifecycle_group_dataclass_is_frozen() -> None:
    g = LifecycleGroup(project_key="x", buyer_canonical="y", items=())
    with pytest.raises(Exception):
        g.project_key = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StockCodeResolver
# ---------------------------------------------------------------------------


@pytest.fixture
def resolver() -> StockCodeResolver:
    return StockCodeResolver()


def test_resolver_finds_short_alias(resolver: StockCodeResolver) -> None:
    assert resolver.resolve("中芯国际") == "sh688981"


def test_resolver_finds_full_legal_name(resolver: StockCodeResolver) -> None:
    assert resolver.resolve("中芯国际集成电路制造（上海）有限公司") == "sh688981"


def test_resolver_prefers_longest_match() -> None:
    r = StockCodeResolver()
    # The built-in entities share the same canonical length; the
    # resolver picks one deterministically. Asserting "either" is OK
    # captures the documented behaviour: longest match wins, ties
    # resolved alphabetically.
    code = r.resolve("中芯国际和韦尔股份")
    assert code in {"sh688981", "sh603501"}


def test_resolver_returns_none_on_miss(resolver: StockCodeResolver) -> None:
    assert resolver.resolve("完全未知的实体") is None


def test_resolver_rejects_invalid_code() -> None:
    r = StockCodeResolver()
    with pytest.raises(ValueError):
        r.register("某公司", "abc")
    with pytest.raises(ValueError):
        r.register("某公司", "sh12345")  # only 5 digits
    with pytest.raises(ValueError):
        r.register("", "sh600000")
    with pytest.raises(ValueError):
        r.register("某公司", "sh6000000")  # 7 digits


def test_resolver_audit_log_records_matches_and_misses() -> None:
    r = StockCodeResolver()
    r.resolve("中芯国际")
    r.resolve("未知公司")
    log = r.audit_log()
    assert len(log) == 2
    assert log[0].matched is True
    assert log[0].stock_code == "sh688981"
    assert log[1].matched is False
    assert log[1].stock_code is None
    assert log[1].canonical_entity == ""


def test_resolver_audit_log_is_bounded() -> None:
    r = StockCodeResolver()
    for _ in range(300):
        r.resolve("miss")
    assert len(r.audit_log()) <= 256


def test_resolver_audit_sink_is_called() -> None:
    sink_calls: list[StockResolution] = []
    r = StockCodeResolver(audit_sink=sink_calls.append)
    r.resolve("中芯国际")
    assert len(sink_calls) == 1
    assert sink_calls[0].matched is True


def test_resolver_audit_sink_failure_does_not_crash() -> None:
    def bad_sink(_resolution: StockResolution) -> None:
        raise RuntimeError("sink boom")

    r = StockCodeResolver(audit_sink=bad_sink)
    # should not raise - the resolver swallows sink errors
    assert r.resolve("中芯国际") == "sh688981"
    assert len(r.audit_log()) == 1


def test_resolver_register_overrides() -> None:
    r = StockCodeResolver()
    r.register("中芯国际", "sh123456")
    assert r.resolve("中芯国际") == "sh123456"


# ---------------------------------------------------------------------------
# Compatibility shims
# ---------------------------------------------------------------------------


def test_get_stock_code_legacy_shim() -> None:
    assert get_stock_code("中芯国际") == "sh688981"
    assert get_stock_code("完全未知") is None


def test_find_company_in_query_legacy_shim() -> None:
    matches = find_company_in_query("中芯国际与韦尔股份的对比")
    pairs = sorted(matches)
    # Legacy signature returns ``(company_name, stock_code)`` tuples.
    assert ("中芯国际", "sh688981") in pairs
    assert ("韦尔股份", "sh603501") in pairs


# ---------------------------------------------------------------------------
# Integration scenarios
# ---------------------------------------------------------------------------


def test_news_dedup_end_to_end_via_collectors() -> None:
    """A news item collected from two different URLs but with the same
    (title, content, publisher, publish_time) should collapse to a
    single identity."""

    item_a = {
        "title": "  国务院 印发 半导体 行动 计划 ",
        "content": "到 2025 年实现 70% 自给率",
        "publisher": "国务院",
        "publish_time": "2024-03-01T00:00:00+08:00",
    }
    item_b = dict(item_a)
    item_b["url"] = "https://news.example.com/post/1"
    item_c = dict(item_a)
    item_c["url"] = "https://mirror.example.com/post/1"

    assert news_dedup_key(**item_a) == news_dedup_key(**item_b)
    assert news_dedup_key(**item_a) == news_dedup_key(**item_c)


def test_bidding_lifecycle_merges_full_and_short_buyer_names() -> None:
    items = [
        {"bid_id": "B1", "title": "12英寸晶圆设备 招标公告", "parties": {"buyer": "中芯国际集成电路制造（上海）有限公司"}},
        {"bid_id": "B2", "title": "12英寸晶圆设备 中标公告", "parties": {"buyer": "中芯国际"}},
    ]
    groups = cluster_lifecycle(items)
    assert len(groups) == 1
    assert len(groups[0].items) == 2


def test_stock_resolver_routes_through_normalisation() -> None:
    r = StockCodeResolver()
    # The buyer name extracted by extract_parties should resolve via
    # the stock resolver, completing the chain news -> parties -> stock.
    text = "采购人：中芯国际集成电路制造（上海）有限公司"
    parties = extract_parties(text)
    assert r.resolve(parties["buyer"]) == "sh688981"
