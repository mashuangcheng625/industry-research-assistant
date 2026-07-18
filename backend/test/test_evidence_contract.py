"""统一证据契约和适配器的单元测试。

覆盖:
- Evidence 创建和校验
- 各适配器的正确转换
- 缺失字段的优雅降级
- 哈希稳定性
- 来源类型枚举
"""

from pathlib import Path
import copy
import json
import sys
import unittest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.evidence_contract import (  # noqa: E402
    Evidence,
    validate_evidence,
    validate_evidence_collection,
    VALID_SOURCE_KINDS,
    VALID_QUALITY_TIERS,
    _compute_hash,
)
from service.evidence_adapters.document_adapter import (  # noqa: E402
    adapt_document_chunk,
    adapt_document_chunks,
)
from service.evidence_adapters.news_adapter import (  # noqa: E402
    adapt_news_item,
    adapt_news_items,
)
from service.evidence_adapters.bidding_adapter import (  # noqa: E402
    adapt_bidding_item,
    adapt_bidding_items,
)
from service.evidence_adapters.sql_row_adapter import (  # noqa: E402
    adapt_sql_row,
    adapt_sql_result,
)
from service.evidence_adapters.market_adapter import (  # noqa: E402
    adapt_stock_quote,
    adapt_stock_data_points,
    adapt_web_search_result,
)


class EvidenceContractTests(unittest.TestCase):
    """Evidence 基础契约测试。"""

    def test_create_generates_stable_id(self):
        """相同内容产生相同 evidence_id。"""
        e1 = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Test content for hash stability test.",
        )
        e2 = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Test content for hash stability test.",
        )
        self.assertEqual(e1.evidence_id, e2.evidence_id)
        self.assertEqual(e1.content_hash, e2.content_hash)

    def test_create_different_content_produces_different_id(self):
        """不同内容产生不同 evidence_id。"""
        e1 = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Content A.",
        )
        e2 = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Content B.",
        )
        self.assertNotEqual(e1.evidence_id, e2.evidence_id)

    def test_missing_evidence_id_is_invalid(self):
        """evidence_id 为空字符串时校验失败。"""
        e = Evidence(
            evidence_id="", source_kind="document", title="Title",
            publisher="Publisher", url=None, published_at=None,
            retrieved_at="2026-01-01T00:00:00Z", as_of=None, locator={},
            content="Content.", content_hash=_compute_hash("Content."),
            quality_tier="primary", license_or_terms="not_assessed",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("evidence_id" in err for err in errors))

    def test_invalid_source_kind_is_rejected(self):
        """非法的 source_kind 被校验拦截。"""
        e = Evidence.create(
            source_kind="invalid_kind", title="Test", publisher="TestOrg",
            content="Content.",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("source_kind" in err for err in errors))

    def test_all_valid_source_kinds_pass(self):
        """所有合法 source_kind 通过校验。"""
        for kind in sorted(VALID_SOURCE_KINDS):
            e = Evidence.create(
                source_kind=kind, title=f"Test {kind}",
                publisher="TestOrg", content="Content.",
                locator={"page": 1} if kind == "document"
                else {"notice_id": "123"} if kind == "bidding"
                else {},
                as_of="2026-01-01T00:00:00Z" if kind == "market_quote" else None,
            )
            errors = validate_evidence(e)
            self.assertEqual(errors, [], f"source_kind={kind} 应该合法")

    def test_invalid_quality_tier_is_rejected(self):
        """非法的 quality_tier 被校验拦截。"""
        e = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Content.", quality_tier="invalid_tier",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("quality_tier" in err for err in errors))

    def test_all_valid_quality_tiers_pass(self):
        """所有合法 quality_tier 通过校验。"""
        for tier in sorted(VALID_QUALITY_TIERS):
            e = Evidence.create(
                source_kind="document", title=f"Test {tier}",
                publisher="TestOrg", content="Content.",
                quality_tier=tier, locator={"page": 1},
            )
            errors = validate_evidence(e)
            self.assertEqual(errors, [], f"quality_tier={tier} 应该合法")

    def test_content_hash_mismatch_detected(self):
        """篡改 content 后 content_hash 不匹配被检测到。"""
        e = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Original content.",
        )
        # 使用 object.__setattr__ 绕过 frozen
        object.__setattr__(e, "content", "Tampered content.")
        errors = validate_evidence(e)
        self.assertTrue(any("content_hash" in err for err in errors))

    def test_empty_title_is_invalid(self):
        """空标题被校验拦截。"""
        e = Evidence.create(
            source_kind="document", title="   ", publisher="TestOrg",
            content="Content.",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("title" in err for err in errors))

    def test_empty_publisher_is_invalid(self):
        """空发布方被校验拦截。"""
        e = Evidence.create(
            source_kind="document", title="Title", publisher="   ",
            content="Content.",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("publisher" in err for err in errors))

    def test_empty_content_is_invalid(self):
        """空内容被校验拦截。"""
        e = Evidence.create(
            source_kind="document", title="Title", publisher="Publisher",
            content="   ",
        )
        errors = validate_evidence(e)
        self.assertTrue(any("content" in err for err in errors))

    def test_document_without_page_or_chunk_index_flagged(self):
        """document 类型缺少 page/chunk_index 被提示。"""
        e = Evidence.create(
            source_kind="document", title="Title", publisher="Publisher",
            content="Content.", locator={"kb_name": "test_kb", "doc_id": "doc-1"},
        )
        errors = validate_evidence(e)
        self.assertTrue(any("chunk_index" in err for err in errors))

    def test_document_with_empty_locator_is_not_flagged(self):
        """document 类型 locator 完全为空时不触发错误（无信息可验证）。"""
        e = Evidence.create(
            source_kind="document", title="Title", publisher="Publisher",
            content="Content.", locator={},
        )
        errors = validate_evidence(e)
        self.assertFalse(any("chunk_index" in err for err in errors))

    def test_bidding_without_notice_id_flagged(self):
        """bidding 类型缺少 notice_id 被提示。"""
        e = Evidence.create(
            source_kind="bidding", title="Title", publisher="Publisher",
            content="Content.", locator={},
        )
        errors = validate_evidence(e)
        self.assertTrue(any("notice_id" in err for err in errors))

    def test_market_quote_without_as_of_warns(self):
        """market_quote 缺少 as_of 产生警告。"""
        e = Evidence.create(
            source_kind="market_quote", title="Title", publisher="Publisher",
            content="Content.", as_of=None,
        )
        errors = validate_evidence(e)
        self.assertTrue(any("as_of" in err for err in errors))

    def test_is_timely_detects_timeliness(self):
        """is_timely 正确判断时效性。"""
        timely = Evidence.create(
            source_kind="document", title="T", publisher="P",
            content="C.", published_at="2026-01-01T00:00:00Z",
        )
        untimely = Evidence.create(
            source_kind="document", title="T", publisher="P",
            content="C.",
        )
        self.assertTrue(timely.is_timely)
        self.assertFalse(untimely.is_timely)

    def test_can_locate_detects_locatability(self):
        """can_locate 正确判断可定位性。"""
        locatable = Evidence.create(
            source_kind="document", title="T", publisher="P",
            content="C.", locator={"page": 5},
        )
        not_locatable = Evidence.create(
            source_kind="web_search", title="T", publisher="P",
            content="C.", locator={},
        )
        self.assertTrue(locatable.can_locate)
        self.assertFalse(not_locatable.can_locate)

    def test_short_ref_includes_publisher_and_date(self):
        """short_ref 包含发布方和年份。"""
        e = Evidence.create(
            source_kind="document", title="Test Title", publisher="TestOrg",
            content="Content.", published_at="2025-06-15T00:00:00Z",
        )
        ref = e.short_ref
        self.assertIn("TestOrg", ref)
        self.assertIn("2025", ref)

    def test_to_dict_and_json_round_trip(self):
        """to_dict() 和 to_json() 输出一致性。"""
        e = Evidence.create(
            source_kind="document", title="Test", publisher="TestOrg",
            content="Content.", url="https://example.org/doc",
            published_at="2026-01-01T00:00:00Z",
            locator={"page": 3, "chunk_index": 1},
        )
        d = e.to_dict()
        self.assertEqual(d["source_kind"], "document")
        self.assertEqual(d["title"], "Test")

        j = e.to_json()
        back = json.loads(j)
        self.assertEqual(back["evidence_id"], e.evidence_id)

    def test_validate_evidence_collection_produces_report(self):
        """validate_evidence_collection 生成正确汇总。"""
        good = Evidence.create(
            source_kind="document", title="G", publisher="P",
            content="C.", locator={"page": 1},
        )
        bad = Evidence.create(
            source_kind="invalid_kind", title="B", publisher="P",
            content="C.",
        )
        report = validate_evidence_collection([good, bad])
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["valid"], 1)
        self.assertEqual(report["invalid"], 1)

    def test_source_kind_labels_complete(self):
        """所有 source_kind 都有对应标签。"""
        from service.evidence_contract import SOURCE_KIND_LABELS
        for kind in VALID_SOURCE_KINDS:
            self.assertIn(kind, SOURCE_KIND_LABELS,
                          f"source_kind '{kind}' 缺少标签")

    def test_quality_tier_labels_complete(self):
        """所有 quality_tier 都有对应标签。"""
        from service.evidence_contract import QUALITY_TIER_LABELS
        for tier in VALID_QUALITY_TIERS:
            self.assertIn(tier, QUALITY_TIER_LABELS,
                          f"quality_tier '{tier}' 缺少标签")


class DocumentAdapterTests(unittest.TestCase):
    """文档 RAG 适配器测试。"""

    def test_single_chunk_conversion(self):
        """标准 RAG 块正确转换。"""
        chunk = {
            "content_with_weight": "Advanced packaging uses TSV and microbumps.",
            "document_name": "Advanced Packaging Handbook",
            "chunk_index": 2,
            "page": 45,
            "doc_id": "doc-001",
            "kb_name": "semiconductor_packaging_testing",
            "score": 0.92,
        }
        evidence = adapt_document_chunk(chunk)
        self.assertEqual(evidence.source_kind, "document")
        self.assertEqual(evidence.title, "Advanced Packaging Handbook")
        self.assertIn("TSV", evidence.content)
        self.assertEqual(evidence.locator["page"], 45)
        self.assertEqual(evidence.locator["chunk_index"], 2)
        self.assertEqual(evidence.locator["doc_id"], "doc-001")
        self.assertEqual(evidence.locator["kb_name"], "semiconductor_packaging_testing")

    def test_chunk_with_minimal_fields(self):
        """最小字段的块仍能转换。"""
        chunk = {
            "content": "Minimal content.",
            "document_name": "Short Doc",
        }
        evidence = adapt_document_chunk(chunk)
        self.assertEqual(evidence.source_kind, "document")
        self.assertEqual(evidence.title, "Short Doc")
        self.assertEqual(evidence.content, "Minimal content.")
        self.assertEqual(len(evidence.locator), 0)

    def test_batch_conversion(self):
        """批量转换正确。"""
        chunks = [
            {"content": "A", "document_name": "Doc A"},
            {"content": "B", "document_name": "Doc B"},
        ]
        evidences = adapt_document_chunks(chunks)
        self.assertEqual(len(evidences), 2)
        self.assertEqual(evidences[0].title, "Doc A")
        self.assertEqual(evidences[1].title, "Doc B")

    def test_standards_publisher_gets_official_tier(self):
        """SEMI/IEEE/NIST 等来源获得 official 质量层级。"""
        chunk = {
            "content": "Standard content.",
            "document_name": "JEDEC Standard JESD79",
            "url": "https://www.jedec.org/standard/jesd79",
        }
        evidence = adapt_document_chunk(chunk)
        self.assertEqual(evidence.quality_tier, "official")

    def test_generic_publisher_gets_primary_tier(self):
        """通用文档获得 primary 质量层级。"""
        chunk = {
            "content": "Generic content.",
            "document_name": "Some Report",
        }
        evidence = adapt_document_chunk(chunk)
        self.assertEqual(evidence.quality_tier, "primary")

    def test_url_is_preserved(self):
        """URL 正确保留。"""
        chunk = {
            "content": "Content.", "document_name": "Doc",
            "source_url": "https://example.org/doc.pdf",
        }
        evidence = adapt_document_chunk(chunk)
        self.assertEqual(evidence.url, "https://example.org/doc.pdf")


class NewsAdapterTests(unittest.TestCase):
    """新闻适配器测试。"""

    def test_news_item_conversion(self):
        """标准新闻条目正确转换。"""
        news = {
            "id": "news-001",
            "title": "先进封装设备国产化取得突破",
            "content": "国内某企业成功研发先进封装用键合机...",
            "source": "工信部",
            "source_url": "https://example.gov.cn/news/001",
            "category": "新闻",
            "department": "工信部",
            "publish_time": "2026-03-15T10:00:00Z",
            "collected_at": "2026-07-18T09:00:00Z",
        }
        evidence = adapt_news_item(news)
        self.assertEqual(evidence.source_kind, "news")
        self.assertEqual(evidence.title, "先进封装设备国产化取得突破")
        self.assertEqual(evidence.publisher, "工信部")
        self.assertEqual(evidence.published_at, "2026-03-15T10:00:00Z")
        self.assertEqual(evidence.retrieved_at, "2026-07-18T09:00:00Z")
        self.assertIn("news-001", evidence.locator["news_id"])

    def test_policy_category_becomes_policy_kind(self):
        """政策分类映射为 policy source_kind。"""
        news = {
            "id": "policy-001",
            "title": "关于促进集成电路产业高质量发展的指导意见",
            "content": "...",
            "source": "国务院",
            "category": "政策",
            "department": "国务院",
            "publish_time": "2025-12-01T00:00:00Z",
        }
        evidence = adapt_news_item(news)
        self.assertEqual(evidence.source_kind, "policy")
        self.assertEqual(evidence.quality_tier, "official")

    def test_government_source_gets_official_tier(self):
        """政府来源获得 official 质量层级。"""
        news = {
            "id": "n-001", "title": "T", "content": "C",
            "source": "国家发展改革委", "category": "新闻",
        }
        evidence = adapt_news_item(news)
        self.assertEqual(evidence.quality_tier, "official")

    def test_unknown_source_gets_unknown_tier(self):
        """未知来源获得 unknown 质量层级。"""
        news = {
            "id": "n-001", "title": "T", "content": "C",
            "source": "某博客", "category": "新闻",
        }
        evidence = adapt_news_item(news)
        self.assertEqual(evidence.quality_tier, "unknown")

    def test_missing_fields_graceful_degradation(self):
        """缺失字段时优雅降级。"""
        news = {
            "id": "n-001",
            "title": "T",
        }
        evidence = adapt_news_item(news)
        self.assertEqual(evidence.source_kind, "news")
        self.assertEqual(evidence.title, "T")
        self.assertEqual(evidence.content, "")
        self.assertIsNone(evidence.published_at)
        self.assertIsNone(evidence.url)

    def test_batch_conversion(self):
        """批量转换正确。"""
        items = [
            {"id": "1", "title": "A"},
            {"id": "2", "title": "B"},
        ]
        evidences = adapt_news_items(items)
        self.assertEqual(len(evidences), 2)


class BiddingAdapterTests(unittest.TestCase):
    """招投标适配器测试。"""

    def test_bidding_item_conversion(self):
        """标准招投标条目正确转换。"""
        bidding = {
            "id": "bid-001",
            "bid_id": "LN2026-GK-001",
            "title": "先进封装生产线设备采购招标公告",
            "notice_type": "招标",
            "province": "辽宁省",
            "city": "沈阳市",
            "content": "采购先进封装键合机5台...",
            "publish_time": "2026-06-01T00:00:00Z",
            "source": "81api",
            "collected_at": "2026-07-18T09:00:00Z",
        }
        evidence = adapt_bidding_item(bidding)
        self.assertEqual(evidence.source_kind, "bidding")
        self.assertEqual(evidence.locator["notice_id"], "LN2026-GK-001")
        self.assertEqual(evidence.locator["notice_type"], "招标")
        self.assertEqual(evidence.locator["province"], "辽宁省")
        self.assertEqual(evidence.quality_tier, "primary")

    def test_win_bid_quality(self):
        """中标公告为 primary 层级。"""
        bidding = {
            "id": "bid-002", "bid_id": "BJ2026-ZB-002",
            "title": "封装设备中标公告",
            "notice_type": "中标结果",
            "source": "81api",
        }
        evidence = adapt_bidding_item(bidding)
        self.assertEqual(evidence.quality_tier, "primary")

    def test_publisher_includes_location(self):
        """发布方包含地区信息。"""
        bidding = {
            "id": "b-1", "bid_id": "SH-001",
            "title": "T",
            "notice_type": "招标",
            "province": "上海市", "city": "",
            "source": "81api",
        }
        evidence = adapt_bidding_item(bidding)
        self.assertIn("上海市", evidence.publisher)

    def test_batch_conversion(self):
        """批量转换正确。"""
        items = [
            {"id": "1", "bid_id": "A", "title": "A", "notice_type": "招标", "source": "81api"},
            {"id": "2", "bid_id": "B", "title": "B", "notice_type": "中标", "source": "81api"},
        ]
        evidences = adapt_bidding_items(items)
        self.assertEqual(len(evidences), 2)


class SqlRowAdapterTests(unittest.TestCase):
    """SQL 行适配器测试。"""

    def test_single_row_conversion(self):
        """标准 SQL 行正确转换。"""
        row = {
            "company_name": "长电科技",
            "revenue": 359.5,
            "net_profit": 32.8,
            "market_share": 11.5,
            "year": 2024,
        }
        columns = ["company_name", "revenue", "net_profit", "market_share", "year"]
        evidence = adapt_sql_row(
            row, table_name="company_data", columns=columns,
            sql="SELECT * FROM company_data WHERE company_name='长电科技'",
        )
        self.assertEqual(evidence.source_kind, "sql_row")
        self.assertIn("长电科技", evidence.title)
        self.assertIn("revenue=359.5", evidence.content)
        self.assertIn("row_id", evidence.locator)
        self.assertIn("table_name", evidence.locator)
        self.assertEqual(evidence.locator["table_name"], "company_data")

    def test_row_hash_stability(self):
        """相同行产生相同 row_id。"""
        row = {"col": "value", "year": 2024}
        e1 = adapt_sql_row(row, columns=["col", "year"])
        e2 = adapt_sql_row(row, columns=["col", "year"])
        self.assertEqual(e1.locator["row_id"], e2.locator["row_id"])

    def test_as_of_inference(self):
        """从行数据中推断统计时点。"""
        row = {"metric_value": 100, "year": 2025, "quarter": 2}
        evidence = adapt_sql_row(row, columns=["metric_value", "year", "quarter"])
        self.assertIsNotNone(evidence.as_of)
        self.assertIn("year=2025", evidence.as_of)

    def test_complete_result_conversion(self):
        """完整 Text2SQL 结果正确转换。"""
        result = {
            "data": [
                {"company_name": "A", "revenue": 100},
                {"company_name": "B", "revenue": 200},
            ],
            "columns": ["company_name", "revenue"],
            "sql": "SELECT company_name, revenue FROM company_data",
        }
        evidences = adapt_sql_result(result, table_name="company_data")
        self.assertEqual(len(evidences), 2)
        self.assertEqual(evidences[0].source_kind, "sql_row")
        self.assertEqual(evidences[1].source_kind, "sql_row")


class MarketAdapterTests(unittest.TestCase):
    """市场行情适配器测试。"""

    def test_stock_quote_conversion(self):
        """标准股票行情正确转换。"""
        quote = {
            "name": "长电科技",
            "gid": "sh600584",
            "nowPri": "38.50",
            "increase": "1.20",
            "increPer": "3.22",
            "todayStartPri": "37.30",
            "yestodEndPri": "37.30",
            "todayMax": "39.10",
            "todayMin": "37.10",
            "traAmount": "12500000",
            "traNumber": "480000000",
        }
        evidence = adapt_stock_quote(quote)
        self.assertEqual(evidence.source_kind, "market_quote")
        self.assertIn("长电科技", evidence.title)
        self.assertIn("38.50", evidence.content)
        self.assertEqual(evidence.locator["stock_code"], "sh600584")
        self.assertIsNotNone(evidence.as_of)
        self.assertEqual(evidence.quality_tier, "secondary")

    def test_data_points_conversion(self):
        """data_points 正确转换。"""
        dps = [
            {"name": "长电科技当前股价", "value": 38.50, "unit": "元",
             "source": "聚合数据股票API", "source_type": "realtime"},
            {"name": "长电科技涨跌幅", "value": "3.22", "unit": "%",
             "source": "聚合数据股票API", "source_type": "realtime"},
        ]
        evidences = adapt_stock_data_points(dps)
        self.assertEqual(len(evidences), 2)
        self.assertEqual(evidences[0].source_kind, "market_quote")

    def test_web_search_result_conversion(self):
        """网络搜索结果正确转换。"""
        result = {
            "url": "https://example.com/article",
            "title": "先进封装市场分析",
            "summary": "全球先进封装市场规模预计2028年达到786亿美元...",
            "site_name": "前瞻产业研究院",
            "date": "2026-05-15",
        }
        evidence = adapt_web_search_result(result)
        self.assertEqual(evidence.source_kind, "web_search")
        self.assertEqual(evidence.title, "先进封装市场分析")
        self.assertEqual(evidence.url, "https://example.com/article")
        self.assertEqual(evidence.published_at, "2026-05-15")
        self.assertEqual(evidence.quality_tier, "unknown")

    def test_web_search_with_bocha_format(self):
        """Bocha 格式的搜索结果也能正确转换。"""
        result = {
            "url": "https://example.com/news",
            "name": "半导体产业政策解读",
            "summary": "国务院发布集成电路产业扶持政策...",
            "siteName": "中国政府网",
            "datePublished": "2026-06-01",
        }
        evidence = adapt_web_search_result(result)
        self.assertEqual(evidence.title, "半导体产业政策解读")
        self.assertIn("国务院", evidence.content)


class CrossAdapterIntegrationTests(unittest.TestCase):
    """跨适配器集成测试。"""

    def test_all_adapters_produce_valid_evidence(self):
        """所有适配器输出通过 validate_evidence 校验。"""
        # 文档
        doc_evidence = adapt_document_chunk({
            "content": "Test doc content with sufficient length.",
            "document_name": "Test Document",
            "chunk_index": 1,
            "page": 10,
        })
        # 新闻
        news_evidence = adapt_news_item({
            "id": "n-1", "title": "News Title",
            "content": "News content.",
            "source": "工信部", "category": "新闻",
        })
        # 招投标
        bid_evidence = adapt_bidding_item({
            "id": "b-1", "bid_id": "BID-001",
            "title": "Bidding Title",
            "notice_type": "招标",
            "source": "81api",
        })
        # SQL 行
        sql_evidence = adapt_sql_row(
            {"col": "val"}, columns=["col"], table_name="test",
        )
        # 行情
        market_evidence = adapt_stock_quote({
            "name": "TestStock", "gid": "sh600000",
            "nowPri": "10.00",
        })

        all_evidence = [doc_evidence, news_evidence, bid_evidence,
                        sql_evidence, market_evidence]
        report = validate_evidence_collection(all_evidence)
        self.assertEqual(report["valid"], len(all_evidence),
                         f"有证据未通过校验: {report['details']}")

    def test_evidence_collection_mixed_sources(self):
        """混合来源的证据集合可以统一校验。"""
        sources = [
            adapt_document_chunk({"content": "A", "document_name": "D", "page": 1}),
            adapt_news_item({"id": "n", "title": "N", "content": "C", "source": "S"}),
            adapt_bidding_item({"id": "b", "bid_id": "B", "title": "T", "notice_type": "招标", "source": "S"}),
            adapt_sql_row({"c": "v"}, columns=["c"], table_name="t"),
            adapt_stock_quote({"name": "S", "gid": "sh000001", "nowPri": "1"}),
            adapt_web_search_result({"title": "W", "summary": "C", "url": "http://e.com", "site_name": "E"}),
        ]
        kinds = {e.source_kind for e in sources}
        self.assertEqual(kinds, {"document", "news", "bidding", "sql_row",
                                 "market_quote", "web_search"})

        report = validate_evidence_collection(sources)
        self.assertEqual(report["valid"], len(sources))


if __name__ == "__main__":
    unittest.main()
