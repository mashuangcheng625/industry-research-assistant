import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { Modal, Result, Spin, Steps } from 'antd'
import styles from './index.module.scss'

export interface CollectionResult {
  success: boolean
  message: string
  news_collected: number
  bidding_collected: number
  errors: string[]
}

interface CollectionModalProps {
  open: boolean
  collecting: boolean
  result: CollectionResult | null
  industryName: string
  onClose: () => void
}

export default function CollectionModal({
  open,
  collecting,
  result,
  industryName,
  onClose,
}: CollectionModalProps) {
  // 计算当前步骤
  const getCurrentStep = () => {
    if (!collecting && !result) return 0
    if (collecting) return 1
    if (result) return 2
    return 0
  }

  const currentStep = getCurrentStep()

  // 步骤状态
  const getStepStatus = (
    step: number,
  ): 'wait' | 'process' | 'finish' | 'error' => {
    if (step < currentStep) return 'finish'
    if (step === currentStep) {
      if (step === 2 && result && !result.success) return 'error'
      return 'process'
    }
    return 'wait'
  }

  return (
    <Modal
      title={`更新产业数据 · ${industryName}`}
      open={open}
      footer={null}
      closable={!collecting}
      maskClosable={false}
      keyboard={false}
      onCancel={onClose}
      width={500}
      centered
    >
      <div className={styles.container}>
        <Steps
          direction="vertical"
          current={currentStep}
          items={[
            {
              title: '准备更新',
              description: '连接产业数据源',
              status: getStepStatus(0),
              icon:
                currentStep === 0 ? (
                  <LoadingOutlined />
                ) : (
                  <CheckCircleOutlined />
                ),
            },
            {
              title: '正在更新',
              description: collecting ? (
                <div className={styles.collecting}>
                  <Spin size="small" />
                  <span>正在获取最新产业动态和招投标公告...</span>
                </div>
              ) : (
                '从多个产业数据源获取信息'
              ),
              status: getStepStatus(1),
              icon: collecting ? (
                <LoadingOutlined spin />
              ) : currentStep > 1 ? (
                <CheckCircleOutlined />
              ) : undefined,
            },
            {
              title: '更新完成',
              description: result
                ? result.success
                  ? '产业数据已更新'
                  : '部分数据源更新失败'
                : '等待更新结果',
              status: getStepStatus(2),
              icon: result ? (
                result.success ? (
                  <CheckCircleOutlined />
                ) : (
                  <CloseCircleOutlined />
                )
              ) : undefined,
            },
          ]}
        />

        {/* 采集结果 */}
        {result && (
          <div className={styles.result}>
            <Result
              status={result.success ? 'success' : 'warning'}
              title={result.success ? '更新完成' : '部分数据源更新失败'}
              subTitle={
                <div className={styles.stats}>
                  <p>
                    产业动态：<strong>{result.news_collected}</strong> 条
                  </p>
                  <p>
                    招投标公告：<strong>{result.bidding_collected}</strong> 条
                  </p>
                  {result.errors.length > 0 && (
                    <div className={styles.errors}>
                      <p>未完成项：</p>
                      <ul>
                        {result.errors.slice(0, 3).map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                        {result.errors.length > 3 && (
                          <li>另有 {result.errors.length - 3} 项未显示</li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              }
              extra={
                <button className={styles.closeBtn} onClick={onClose}>
                  关闭
                </button>
              }
            />
          </div>
        )}
      </div>
    </Modal>
  )
}
