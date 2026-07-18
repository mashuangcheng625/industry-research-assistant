import IconBg from '@/assets/index/bg.png'
import IconSearch from '@/assets/index/search.svg'
import { INDUSTRY_CONFIGS, setCurrentIndustry } from '@/store/industry'
import {
  ArrowRightOutlined,
  CodeOutlined,
  DeploymentUnitOutlined,
  ExperimentOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Input } from 'antd'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './index.module.scss'

// 行业卡片颜色配置
const INDUSTRY_COLORS: Record<string, { color: string; bgColor: string }> = {
  chip_design_eda_ip: { color: '#2347A5', bgColor: '#EEF3FF' },
  materials_equipment: { color: '#6C3EB8', bgColor: '#F5F0FF' },
  wafer_fabrication: { color: '#087E6D', bgColor: '#EAF8F5' },
  packaging_testing: { color: '#B45C12', bgColor: '#FFF4E8' },
}

const DIRECTION_ICONS = {
  chip_design_eda_ip: <CodeOutlined />,
  materials_equipment: <ExperimentOutlined />,
  wafer_fabrication: <SettingOutlined />,
  packaging_testing: <DeploymentUnitOutlined />,
}

const DIRECTION_CODES = {
  chip_design_eda_ip: 'DESIGN / EDA',
  materials_equipment: 'MATERIALS / EQUIPMENT',
  wafer_fabrication: 'WAFER FAB',
  packaging_testing: 'PACKAGING / TEST',
}

export default function Index() {
  const navigate = useNavigate()
  const [searchKeyword, setSearchKeyword] = useState('')

  const cardList = useMemo(
    () =>
      INDUSTRY_CONFIGS.map((industry) => ({
        id: industry.id,
        code: DIRECTION_CODES[industry.id as keyof typeof DIRECTION_CODES],
        title: industry.name,
        icon: DIRECTION_ICONS[industry.id as keyof typeof DIRECTION_ICONS],
        desc: industry.description,
        focusAreas: industry.focusAreas,
        color: INDUSTRY_COLORS[industry.id]?.color || '#333',
        bgColor: INDUSTRY_COLORS[industry.id]?.bgColor || '#f5f5f5',
      })),
    [],
  )

  // 根据搜索关键词过滤卡片
  const filteredCardList = useMemo(() => {
    if (!searchKeyword.trim()) return cardList
    const keyword = searchKeyword.toLowerCase()
    return cardList.filter(
      (item) =>
        item.title.toLowerCase().includes(keyword) ||
        item.desc.toLowerCase().includes(keyword),
    )
  }, [cardList, searchKeyword])

  // 点击卡片，切换行业并跳转到聊天页
  const handleCardClick = (industryId: string, title: string) => {
    console.log('[Index] 点击行业卡片:', industryId, title)
    setCurrentIndustry(industryId)
    navigate(`/chat?title=${encodeURIComponent(title)}`)
  }

  return (
    <div className={styles['index-page']}>
      <div className={styles.header}>
        <img className={styles.bg} src={IconBg} alt="" />
        <div className={styles.eyebrow}>EVIDENCE-DRIVEN INDUSTRY RESEARCH</div>
        <h1 className={styles.title}>证据驱动行业研究平台</h1>
        <p className={styles.desc}>
          统一编排专业知识库、产业数据、新闻政策与招投标情报，以半导体全产业链为深度垂直示范，支持技术路线研判、工艺问题分析、供应链研究与可溯源报告生成。
        </p>
        <div className={styles.capabilities}>
          <span>多源研究工具</span>
          <span>结构化数据分析</span>
          <span>证据与引用可追溯</span>
          <span>半导体垂直示范</span>
        </div>
      </div>

      <div className={styles['search-bar']}>
        <div className={styles['section-heading']}>
          <span>产业链研究板块</span>
          <strong>选择产业链研究方向</strong>
        </div>

        <div className={styles['search-bar__input']}>
          <Input
            prefix={<img src={IconSearch} />}
            placeholder="搜索技术、工艺、材料、设备或产业链主题"
            aria-label="搜索技术、工艺、材料、设备或产业链主题"
            size="large"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            allowClear
          />
        </div>
      </div>

      <div className={styles['card-list']}>
        {filteredCardList.length === 0 ? (
          <div className={styles['empty-state']} role="status">
            没有找到相关研究方向。可尝试搜索“芯片”“刻蚀”“材料”或“封装”。
          </div>
        ) : (
          filteredCardList.map((item) => (
            <button
              type="button"
              className={styles['card-item']}
              key={item.id}
              style={{
                backgroundColor: item.bgColor,
                color: item.color,
                cursor: 'pointer',
              }}
              onClick={() => handleCardClick(item.id, item.title)}
            >
              <div className={styles['card-item__top']}>
                <div
                  className={styles['card-item__icon']}
                  style={{ borderColor: item.color, color: item.color }}
                >
                  {item.icon}
                </div>
                <span className={styles['card-item__code']}>{item.code}</span>
              </div>

              <div className={styles['card-item__title']}>{item.title}</div>
              <div className={styles['card-item__desc']}>{item.desc}</div>
              <div className={styles['card-item__tags']}>
                {item.focusAreas.map((area) => (
                  <span key={area}>{area}</span>
                ))}
              </div>
              <div className={styles['card-item__action']}>
                发起研究 <ArrowRightOutlined />
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
