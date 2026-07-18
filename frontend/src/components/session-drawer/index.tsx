import { Session } from '@/api/session'
import { authState } from '@/store/auth'
import { sessionActions, sessionState } from '@/store/session'
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import {
  Button,
  Drawer,
  Empty,
  Input,
  List,
  Popconfirm,
  Spin,
  Typography,
  message,
} from 'antd'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import './index.scss'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const { Text } = Typography

interface SessionDrawerProps {
  open: boolean
  onClose: () => void
}

export function SessionDrawer({ open, onClose }: SessionDrawerProps) {
  const navigate = useNavigate()
  const { sessions, loading } = useSnapshot(sessionState)
  const { isLoggedIn } = useSnapshot(authState)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  useEffect(() => {
    if (open && isLoggedIn) {
      sessionActions.fetchSessions()
    }
  }, [open, isLoggedIn])

  const handleSessionClick = async (session: Session) => {
    // 先关闭抽屉，然后导航
    onClose()
    // 预加载会话数据到 store
    try {
      await sessionActions.loadSession(session.id)
    } catch (e) {
      // 即使预加载失败也继续导航，页面会自己重新加载
      console.log('预加载会话失败，继续导航', e)
    }
    navigate(`/chat/${session.id}`)
  }

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await sessionActions.removeSession(sessionId)
      message.success('研究记录已删除')
    } catch {
      message.error('研究记录删除失败，请重试')
    }
  }

  const handleStartEdit = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  const handleSaveEdit = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!editTitle.trim()) {
      message.warning('请输入研究记录标题')
      return
    }
    try {
      await sessionActions.renameSession(sessionId, editTitle.trim())
      message.success('研究记录标题已更新')
      setEditingId(null)
    } catch {
      message.error('标题更新失败，请重试')
    }
  }

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(null)
  }

  if (!isLoggedIn) {
    return (
      <Drawer
        title="研究记录"
        placement="left"
        onClose={onClose}
        open={open}
        width={320}
        className="session-drawer"
      >
        <Empty description="请先登录" />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="primary" onClick={() => navigate('/login')}>
            去登录
          </Button>
        </div>
      </Drawer>
    )
  }

  return (
    <Drawer
      title="研究记录"
      placement="left"
      onClose={onClose}
      open={open}
      width={320}
      className="session-drawer"
    >
      <Spin spinning={loading}>
        {sessions.length === 0 ? (
          <Empty description="还没有研究记录，发起研究后会显示在这里。" />
        ) : (
          <List
            dataSource={sessions as Session[]}
            renderItem={(session) => (
              <List.Item
                className="session-item"
                onClick={() => handleSessionClick(session)}
                actions={
                  editingId === session.id
                    ? [
                        <Button
                          key="save"
                          type="text"
                          size="small"
                          icon={<CheckOutlined />}
                          onClick={(e) => handleSaveEdit(session.id, e)}
                        />,
                        <Button
                          key="cancel"
                          type="text"
                          size="small"
                          icon={<CloseOutlined />}
                          onClick={handleCancelEdit}
                        />,
                      ]
                    : [
                        <Button
                          key="edit"
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={(e) => handleStartEdit(session, e)}
                        />,
                        <Popconfirm
                          key="delete"
                          title="删除这条研究记录？"
                          onConfirm={(e) =>
                            handleDelete(session.id, e as React.MouseEvent)
                          }
                          onCancel={(e) => e?.stopPropagation()}
                        >
                          <Button
                            type="text"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Popconfirm>,
                      ]
                }
              >
                <List.Item.Meta
                  avatar={
                    <MessageOutlined
                      style={{ fontSize: 20, color: '#1890ff' }}
                    />
                  }
                  title={
                    editingId === session.id ? (
                      <Input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onPressEnter={(e) =>
                          handleSaveEdit(
                            session.id,
                            e as unknown as React.MouseEvent,
                          )
                        }
                        size="small"
                        autoFocus
                      />
                    ) : (
                      <Text ellipsis={{ tooltip: session.title }}>
                        {session.title}
                      </Text>
                    )
                  }
                  description={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs(session.updated_at).fromNow()} ·{' '}
                      {session.message_count} 条消息
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>
    </Drawer>
  )
}
