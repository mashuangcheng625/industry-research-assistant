import IconBid from '@/assets/layout/bid.svg'
import IconDatabase from '@/assets/layout/database.svg'
import IconHistory from '@/assets/layout/history.svg'
import IconHome from '@/assets/layout/home.svg'
import IconKnowledge from '@/assets/layout/knowledge.svg'
import IconMemory from '@/assets/layout/memory.svg'
import IconNewChat from '@/assets/layout/newchat.svg'
import IconNews from '@/assets/layout/news.svg'
import { SessionDrawer } from '@/components/session-drawer'
import { industryState, setCurrentIndustry } from '@/store/industry'
import { DownOutlined } from '@ant-design/icons'
import { Dropdown, message } from 'antd'
import React, { useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import { NavItem } from './nav-item'
import './nav.scss'

const IconTasks =
  'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23474946%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4.5h14v15H5z%22/%3E%3Cpath d=%22M8 9h8M8 13h8M8 17h5%22/%3E%3Cpath d=%22M8 4.5V3m8 1.5V3%22/%3E%3C/svg%3E'

const COMPACT_DIRECTION_NAMES: Record<string, string> = {
  chip_design_eda_ip: '芯片设计',
  materials_equipment: '材料设备',
  wafer_fabrication: '前道工艺',
  packaging_testing: '封装测试',
}

export function Nav() {
  const { pathname } = useLocation()
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false)
  const { currentIndustryId, industries } = useSnapshot(industryState)

  const currentIndustry = useMemo(() => {
    const industry = industries.find((i) => i.id === currentIndustryId)
    console.log('[Nav] 当前行业:', industry?.name)
    return industry || industries[0]
  }, [currentIndustryId, industries])

  const industryMenuItems = useMemo(() => {
    return industries.map((industry) => ({
      key: industry.id,
      label: (
        <div className="industry-menu-item">
          <div className="industry-menu-item__name">{industry.name}</div>
          <div className="industry-menu-item__desc">{industry.description}</div>
        </div>
      ),
      onClick: () => {
        console.log('[Nav] 切换行业:', industry.id, industry.name)
        setCurrentIndustry(industry.id)
      },
    }))
  }, [industries])

  const items = useMemo(
    () => [
      {
        key: 'home',
        label: '研究首页',
        icon: IconHome,
        href: '/',
      },
      {
        key: 'newchat',
        label: '发起研究',
        icon: IconNewChat,
        href: '/chat',
      },
      {
        key: 'history',
        label: '研究记录',
        icon: IconHistory,
        href: '#',
        className: 'nav-item--mobile-secondary',
        onClick: () => setSessionDrawerOpen(true),
      },
      {
        key: 'memory',
        label: '研究记忆',
        icon: IconMemory,
        href: '#',
        className: 'nav-item--mobile-secondary',
        onClick: () => message.info('研究记忆功能正在开发中'),
      },
      {
        key: 'tasks',
        label: '任务中心',
        icon: IconTasks,
        href: '/tasks',
      },
      {
        key: 'knowledge',
        label: '专业知识库',
        icon: IconKnowledge,
        href: '/knowledge',
      },
      {
        key: 'database',
        label: '产业数据分析',
        icon: IconDatabase,
        href: '/database',
        className: 'nav-item--mobile-secondary',
      },
      {
        key: 'news',
        label: '产业动态',
        icon: IconNews,
        href: '/news',
        className: 'nav-item--mobile-secondary',
      },
      {
        key: 'bid',
        label: '招投标情报',
        icon: IconBid,
        href: '/bidding',
        className: 'nav-item--mobile-secondary',
      },
      {
        key: 'demo',
        label: '面试演示',
        icon: IconKnowledge,
        href: '/demo',
        className: 'nav-item--mobile-secondary',
      },
      // 暂时隐藏职业规划
      // {
      //   key: 'career',
      //   label: '职业规划',
      //   icon: IconCareer,
      //   href: '#',
      // },
    ],
    [],
  )

  return (
    <>
      {/* 半导体研究方向选择器 */}
      <div className="industry-selector">
        <Dropdown
          menu={{
            items: industryMenuItems,
            style: { backgroundColor: '#fff' },
          }}
          trigger={['click']}
          placement="bottomLeft"
          dropdownRender={(menu) => (
            <div
              style={{
                backgroundColor: '#fff',
                borderRadius: 8,
                boxShadow:
                  '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12)',
                padding: 4,
              }}
            >
              {React.cloneElement(menu as React.ReactElement, {
                style: {
                  backgroundColor: '#fff',
                  boxShadow: 'none',
                },
              })}
            </div>
          )}
        >
          <div className="industry-selector__trigger">
            <span
              className="industry-selector__label"
              title={currentIndustry.name}
            >
              {COMPACT_DIRECTION_NAMES[currentIndustry.id] ||
                currentIndustry.name}
            </span>
            <DownOutlined className="industry-selector__icon" />
          </div>
        </Dropdown>
      </div>

      <div className="base-layout-nav">
        {items.map(({ key, onClick, ...item }) => (
          <NavItem
            key={key}
            {...item}
            active={pathname === item.href}
            onClick={onClick}
          />
        ))}
      </div>
      <SessionDrawer
        open={sessionDrawerOpen}
        onClose={() => setSessionDrawerOpen(false)}
      />
    </>
  )
}
