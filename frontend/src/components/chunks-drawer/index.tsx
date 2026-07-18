import type { ChunkInfo } from '@/api/knowledge'
import * as knowledgeApi from '@/api/knowledge'
import { FileTextOutlined } from '@ant-design/icons'
import { Drawer, Empty, Spin, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import styles from './index.module.scss'

const { Text, Paragraph } = Typography

interface ChunksDrawerProps {
  open: boolean
  kbId: string
  docId: string
  filename: string
  onClose: () => void
}

export default function ChunksDrawer({
  open,
  kbId,
  docId,
  filename,
  onClose,
}: ChunksDrawerProps) {
  const [loading, setLoading] = useState(false)
  const [chunks, setChunks] = useState<ChunkInfo[]>([])
  const [totalCount, setTotalCount] = useState(0)

  const fetchChunks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await knowledgeApi.getDocumentChunks(kbId, docId)
      setChunks(res.data.chunks)
      setTotalCount(res.data.chunk_count)
    } catch (error: any) {
      message.error(
        error?.response?.data?.detail || '文本切片加载失败，请稍后重试',
      )
      setChunks([])
    } finally {
      setLoading(false)
    }
  }, [docId, kbId])

  useEffect(() => {
    if (open && kbId && docId) {
      fetchChunks()
    }
  }, [docId, fetchChunks, kbId, open])

  const handleClose = () => {
    setChunks([])
    setTotalCount(0)
    onClose()
  }

  return (
    <Drawer
      title={
        <div className={styles.title}>
          <FileTextOutlined />
          <span className={styles.filename}>{filename}</span>
          <Tag color="blue">{totalCount} 个文本切片</Tag>
        </div>
      }
      placement="right"
      width={600}
      open={open}
      onClose={handleClose}
      className={styles.drawer}
    >
      {loading ? (
        <div className={styles.loading}>
          <Spin size="large" />
          <Text type="secondary">正在加载文本切片...</Text>
        </div>
      ) : chunks.length === 0 ? (
        <Empty description="该文档还没有可查看的文本切片" />
      ) : (
        <div className={styles.chunkList}>
          {chunks.map((chunk) => (
            <div key={chunk.index} className={styles.chunkItem}>
              <div className={styles.chunkHeader}>
                <Tag color="purple">#{chunk.index + 1}</Tag>
                <Text type="secondary" className={styles.charCount}>
                  {chunk.content.length} 字符
                </Text>
              </div>
              <Paragraph
                className={styles.chunkContent}
                ellipsis={{ rows: 6, expandable: true, symbol: '展开全文' }}
              >
                {chunk.content}
              </Paragraph>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  )
}
