"""Seed a deterministic semiconductor Text2SQL demo fixture.

The numeric values below are synthetic and must not be presented as market or
financial facts.  Real research claims come from governed documents and live
adapters with provenance.
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base, SessionLocal, engine
from models.industry_data import CompanyData, IndustryStats, PolicyData


FIXTURE_SOURCE = "项目演示夹具（合成数据，非真实统计）"


def seed_industry_stats(db) -> None:
    """Insert one synthetic demand index for each semiconductor value-chain area."""
    rows = [
        ("芯片设计", "演示需求指数", 82.0),
        ("半导体材料与设备", "演示需求指数", 88.0),
        ("晶圆制造", "演示需求指数", 85.0),
        ("封装与测试", "演示需求指数", 79.0),
    ]
    for industry_name, metric_name, metric_value in rows:
        db.add(
            IndustryStats(
                industry_name=industry_name,
                metric_name=metric_name,
                metric_value=metric_value,
                unit="指数",
                year=2026,
                region="演示数据集",
                source=FIXTURE_SOURCE,
                notes="仅用于 Text2SQL、排序和证据适配器的可重复演示。",
            )
        )
    db.commit()


def seed_company_data(db) -> None:
    """Insert semiconductor entities without fabricated financial metrics."""
    rows = [
        ("寒武纪", "688256.SH", "芯片设计", "AI 加速芯片"),
        ("北方华创", "002371.SZ", "半导体材料与设备", "半导体设备"),
        ("中微公司", "688012.SH", "半导体材料与设备", "刻蚀与薄膜设备"),
        ("中芯国际", "688981.SH", "晶圆制造", "晶圆代工"),
        ("长电科技", "600584.SH", "封装与测试", "集成电路封测"),
    ]
    for company_name, stock_code, industry, sub_industry in rows:
        db.add(
            CompanyData(
                company_name=company_name,
                stock_code=stock_code,
                industry=industry,
                sub_industry=sub_industry,
                year=2026,
                data_source=FIXTURE_SOURCE,
                extra_data={"fixture": True, "financial_metrics_intentionally_omitted": True},
            )
        )
    db.commit()


def seed_policy_data(db) -> None:
    """Insert two traceable public policy/program records."""
    rows = [
        {
            "policy_name": "新时期促进集成电路产业和软件产业高质量发展的若干政策",
            "policy_number": "国发〔2020〕8号",
            "department": "国务院",
            "level": "国家级",
            "publish_date": date(2020, 7, 27),
            "category": "产业政策",
            "industry": "半导体全产业链",
            "summary": "演示记录：用于展示政策表的条件查询，研究结论应回到官方全文。",
            "full_text_url": "https://www.gov.cn/zhengce/content/2020-08/04/content_5532370.htm",
            "impact_level": "重大",
        },
        {
            "policy_name": "CHIPS and Science Act of 2022",
            "policy_number": "Public Law 117-167",
            "department": "U.S. Congress",
            "level": "国家级",
            "publish_date": date(2022, 8, 9),
            "category": "产业政策",
            "industry": "半导体全产业链",
            "summary": "演示记录：用于展示跨区域政策查询，不代替法律原文解读。",
            "full_text_url": "https://www.congress.gov/117/plaws/publ167/PLAW-117publ167.pdf",
            "impact_level": "重大",
        },
    ]
    for row in rows:
        db.add(PolicyData(**row))
    db.commit()


def main() -> None:
    """Replace the three demo tables with the deterministic fixture."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(IndustryStats).delete()
        db.query(CompanyData).delete()
        db.query(PolicyData).delete()
        db.commit()
        seed_industry_stats(db)
        seed_company_data(db)
        seed_policy_data(db)
        print(
            "半导体演示数据已初始化："
            f"stats={db.query(IndustryStats).count()}, "
            f"companies={db.query(CompanyData).count()}, "
            f"policies={db.query(PolicyData).count()}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
