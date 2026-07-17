/**
 * Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有
 */

/**
 * 全局行业状态管理
 */
import { proxy, subscribe } from 'valtio'
import { deviceActions } from './device'

// 行业配置类型
export interface IndustryConfig {
  id: string
  name: string
  description: string
  focusAreas: string[]
  recommendedQuestions: string[]
  knowledgeBaseName: string
  // 资讯搜索关键词
  newsKeywords: string[]
  // 招投标搜索关键词
  biddingKeywords: string[]
  // 研究相关关键词
  researchKeywords: string[]
}

// 预定义的行业配置
export const INDUSTRY_CONFIGS: IndustryConfig[] = [
  {
    id: 'chip_design_eda_ip',
    name: '芯片设计与 EDA/IP',
    description:
      '覆盖系统架构、数字与模拟设计、功能验证、物理实现、PPA 优化、EDA 工具链及半导体 IP',
    focusAreas: ['系统架构', '数字/模拟设计', '验证与物理实现', 'EDA/IP'],
    recommendedQuestions: [
      '不同芯片架构如何权衡性能、功耗、面积与开发周期？',
      '先进制程下，设计验证与物理实现面临哪些关键挑战？',
      'EDA 工具与半导体 IP 如何影响芯片研发效率和供应链安全？',
    ],
    knowledgeBaseName: 'semiconductor_chip_design_eda_ip',
    newsKeywords: [
      '芯片设计 架构',
      'EDA 产业',
      'RISC-V 芯片',
      'AI 芯片',
      '芯片 IP',
    ],
    biddingKeywords: ['EDA 软件', '芯片 IP', '集成电路设计服务'],
    researchKeywords: ['芯片设计', '芯片架构', 'RTL', 'EDA', 'PPA'],
  },
  {
    id: 'materials_equipment',
    name: '半导体材料与设备',
    description:
      '覆盖硅片、光刻胶、电子特气、湿电子化学品、靶材及制造与量测设备',
    focusAreas: ['硅片/光刻胶', '特气/化学品/靶材', '制造设备', '量测设备'],
    recommendedQuestions: [
      '先进制程对关键材料与核心设备提出了哪些新要求？',
      '刻蚀、薄膜沉积和量测设备的核心技术壁垒分别是什么？',
      '半导体材料与设备国产化的关键环节和验证难点有哪些？',
    ],
    knowledgeBaseName: 'semiconductor_materials_equipment',
    newsKeywords: [
      '半导体设备',
      '半导体材料',
      '光刻胶',
      '电子气体',
      '刻蚀设备',
      '薄膜沉积设备',
    ],
    biddingKeywords: ['半导体设备', '晶圆制造设备', '半导体材料采购'],
    researchKeywords: ['半导体材料', '半导体设备', '供应链', '国产替代'],
  },
  {
    id: 'wafer_fabrication',
    name: '晶圆制造与前道工艺',
    description:
      '覆盖光刻、刻蚀、薄膜沉积、离子注入、CMP、清洗、工艺集成、SPC/FDC、缺陷分析及良率提升',
    focusAreas: ['光刻/刻蚀', '薄膜/离子注入', 'CMP/清洗/集成', 'SPC/FDC/良率'],
    recommendedQuestions: [
      'ETCH-07 腔体压力异常时，应优先关联哪些设备、工艺和量测数据？',
      '如何结合 SPC、FDC、设备日志和产品量测定位工艺异常？',
      'Recipe 变更后，如何评估缺陷、关键尺寸和良率风险？',
    ],
    knowledgeBaseName: 'semiconductor_process',
    newsKeywords: [
      '晶圆制造',
      '先进制程',
      '光刻工艺',
      '刻蚀工艺',
      '薄膜沉积',
      '半导体良率',
    ],
    biddingKeywords: ['晶圆制造', '工艺设备', '量检测设备'],
    researchKeywords: ['前道工艺', '晶圆制造', 'SPC', 'FDC', '良率'],
  },
  {
    id: 'packaging_testing',
    name: '封装与测试',
    description:
      '覆盖传统封装、先进封装、晶圆级封装、Chiplet、2.5D/3D 集成、键合互连、晶圆测试和成品测试',
    focusAreas: [
      '传统/先进封装',
      '晶圆级封装',
      'Chiplet/2.5D/3D',
      '晶圆/成品测试',
    ],
    recommendedQuestions: [
      '不同封装技术在成本、性能、散热和可靠性方面如何取舍？',
      'Chiplet、2.5D/3D 集成与混合键合分别适用于哪些产品？',
      '晶圆测试、封装测试和系统级测试如何协同定位失效问题？',
    ],
    knowledgeBaseName: 'semiconductor_packaging_testing',
    newsKeywords: [
      '先进封装',
      'Chiplet',
      '2.5D 封装',
      '3D 封装',
      '混合键合',
      'HBM 封装',
    ],
    biddingKeywords: ['封装测试', '先进封装产线', '封装设备'],
    researchKeywords: ['先进封装', 'Chiplet', '2.5D', '3D', '混合键合'],
  },
]

export const DEFAULT_RESEARCH_DIRECTION_ID = 'wafer_fabrication'

// 行业状态
export interface IndustryState {
  currentIndustryId: string
  industries: IndustryConfig[]
}

// 从 localStorage 读取
const getStoredIndustryId = (): string => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('selected_industry_id')
    console.log('[industry store] 从 localStorage 读取行业:', stored)
    return INDUSTRY_CONFIGS.some((item) => item.id === stored)
      ? stored!
      : DEFAULT_RESEARCH_DIRECTION_ID
  }
  return DEFAULT_RESEARCH_DIRECTION_ID
}

// 创建状态
export const industryState = proxy<IndustryState>({
  currentIndustryId: getStoredIndustryId(),
  industries: INDUSTRY_CONFIGS,
})

// 订阅变化，保存到 localStorage
subscribe(industryState, () => {
  if (typeof window !== 'undefined') {
    console.log(
      '[industry store] 保存行业到 localStorage:',
      industryState.currentIndustryId,
    )
    localStorage.setItem(
      'selected_industry_id',
      industryState.currentIndustryId,
    )
  }
})

// 获取当前行业配置
export const getCurrentIndustry = (): IndustryConfig => {
  const industry = industryState.industries.find(
    (i) => i.id === industryState.currentIndustryId,
  )
  console.log('[industry store] 获取当前行业:', industry?.name)
  return industry || INDUSTRY_CONFIGS[0]
}

// 切换行业
export const setCurrentIndustry = (industryId: string) => {
  console.log('[industry store] 切换行业:', industryId)
  industryState.currentIndustryId = industryId
  const direction = INDUSTRY_CONFIGS.find((item) => item.id === industryId)
  if (direction) {
    deviceActions.setKnowledgeBaseName(direction.knowledgeBaseName)
  }
}

// 获取行业列表（用于选择器）
export const getIndustryOptions = () => {
  return industryState.industries.map((i) => ({
    value: i.id,
    label: i.name,
    description: i.description,
  }))
}
