# Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有

"""
半导体产业研究方向配置。

每个方向共享同一套 RAG 和 Deep Research 能力，但使用独立的知识库、
搜索词和推荐问题，避免不同产业环节的语料相互污染。
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndustryConfig:
    """半导体研究方向配置。"""

    id: str
    name: str
    description: str
    knowledge_base_name: str
    focus_areas: List[str]
    recommended_questions: List[str]
    news_keywords: List[str]
    bidding_keywords: List[str]
    research_keywords: List[str]


INDUSTRY_CONFIGS: Dict[str, IndustryConfig] = {
    "chip_design_eda_ip": IndustryConfig(
        id="chip_design_eda_ip",
        name="芯片设计与 EDA/IP",
        description="覆盖架构、数字/模拟设计、验证、PPA、EDA 工具与半导体 IP",
        knowledge_base_name="semiconductor_chip_design_eda_ip",
        focus_areas=["芯片架构", "数字/模拟设计", "验证与 PPA", "EDA/IP"],
        recommended_questions=[
            "芯片架构设计中如何权衡性能、功耗与面积？",
            "先进制程下数字芯片验证面临哪些关键挑战？",
            "EDA 工具与半导体 IP 在芯片设计流程中如何协同？",
        ],
        news_keywords=["芯片设计", "EDA 产业", "RISC-V 芯片", "AI 芯片", "芯片 IP"],
        bidding_keywords=["EDA 软件", "芯片 IP", "集成电路设计服务"],
        research_keywords=["芯片设计", "芯片架构", "RTL", "EDA", "PPA"],
    ),
    "materials_equipment": IndustryConfig(
        id="materials_equipment",
        name="半导体材料与设备",
        description="覆盖硅片、光刻胶、电子气体、靶材及制造与量测设备",
        knowledge_base_name="semiconductor_materials_equipment",
        focus_areas=["硅片/光刻胶", "电子气体/靶材", "制造设备", "量测设备"],
        recommended_questions=[
            "先进制程依赖哪些关键半导体材料与设备？",
            "刻蚀设备的核心技术壁垒主要体现在哪里？",
            "半导体材料与设备国产替代的关键环节有哪些？",
        ],
        news_keywords=["半导体设备", "半导体材料", "光刻胶", "电子气体", "刻蚀设备", "薄膜沉积设备"],
        bidding_keywords=["半导体设备", "晶圆制造设备", "半导体材料采购"],
        research_keywords=["半导体材料", "半导体设备", "供应链", "国产替代"],
    ),
    "wafer_fabrication": IndustryConfig(
        id="wafer_fabrication",
        name="晶圆制造与前道工艺",
        description="覆盖光刻、刻蚀、沉积、注入、CMP、清洗、SPC/FDC 与良率",
        knowledge_base_name="semiconductor_process",
        focus_areas=["光刻/刻蚀", "沉积/离子注入", "CMP/清洗", "SPC/FDC/良率"],
        recommended_questions=[
            "ETCH-07 腔体压力异常时应优先关联哪些数据？",
            "如何结合 SPC、FDC 与设备日志定位工艺异常？",
            "Recipe 变更后应如何评估良率与缺陷风险？",
        ],
        news_keywords=["晶圆制造", "先进制程", "光刻工艺", "刻蚀工艺", "薄膜沉积", "半导体良率"],
        bidding_keywords=["晶圆制造", "工艺设备", "量检测设备"],
        research_keywords=["前道工艺", "晶圆制造", "SPC", "FDC", "良率"],
    ),
    "packaging_testing": IndustryConfig(
        id="packaging_testing",
        name="封装与测试",
        description="覆盖传统/先进封装、Chiplet、2.5D/3D、TSV、混合键合与测试",
        knowledge_base_name="semiconductor_packaging_testing",
        focus_areas=["传统/先进封装", "Chiplet", "2.5D/3D/TSV", "晶圆/成品测试"],
        recommended_questions=[
            "传统封装与先进封装的技术边界和应用场景有何差异？",
            "2.5D、3D 与混合键合技术有哪些主要差异？",
            "晶圆测试与成品测试分别关注哪些关键指标？",
        ],
        news_keywords=["先进封装", "Chiplet", "2.5D 封装", "3D 封装", "混合键合", "HBM 封装"],
        bidding_keywords=["封装测试", "先进封装产线", "封装设备"],
        research_keywords=["先进封装", "Chiplet", "2.5D", "3D", "混合键合"],
    ),
}

DEFAULT_INDUSTRY_ID = "wafer_fabrication"


def get_industry_config(industry_id: Optional[str] = None) -> IndustryConfig:
    """获取研究方向配置；未知 ID 回退到晶圆制造与前道工艺。"""

    selected_id = industry_id or DEFAULT_INDUSTRY_ID
    config = INDUSTRY_CONFIGS.get(selected_id)
    if not config:
        logger.warning("[industry_config] 未找到研究方向: %s, 使用默认方向", selected_id)
        config = INDUSTRY_CONFIGS[DEFAULT_INDUSTRY_ID]

    logger.info("[industry_config] 获取研究方向: %s (%s)", config.name, config.id)
    return config


def get_all_industries() -> List[Dict]:
    """返回可供客户端使用的全部研究方向。"""

    return [
        {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "knowledge_base_name": config.knowledge_base_name,
            "focus_areas": config.focus_areas,
            "recommended_questions": config.recommended_questions,
        }
        for config in INDUSTRY_CONFIGS.values()
    ]
