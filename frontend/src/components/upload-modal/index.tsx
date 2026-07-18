import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  FileOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { Modal, Result, Spin, Steps } from 'antd'
import styles from './index.module.scss'

export interface UploadResult {
  success: boolean
  message: string
  filename: string
  docId?: string
  error?: string
}

interface UploadModalProps {
  open: boolean
  uploading: boolean
  result: UploadResult | null
  filename: string
  onClose: () => void
}

export default function UploadModal({
  open,
  uploading,
  result,
  filename,
  onClose,
}: UploadModalProps) {
  // 计算当前步骤
  const getCurrentStep = () => {
    if (!uploading && !result) return 0
    if (uploading) return 1
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
      title={
        <span>
          <FileOutlined style={{ marginRight: 8 }} />
          上传并解析文档
        </span>
      }
      open={open}
      footer={null}
      closable={!uploading}
      maskClosable={false}
      keyboard={false}
      onCancel={onClose}
      width={480}
      centered
    >
      <div className={styles.container}>
        <div className={styles.filename}>{filename}</div>

        <Steps
          direction="vertical"
          current={currentStep}
          items={[
            {
              title: '准备文件',
              description: '检查文件并创建上传任务',
              status: getStepStatus(0),
              icon:
                currentStep === 0 ? (
                  <LoadingOutlined />
                ) : (
                  <CheckCircleOutlined />
                ),
            },
            {
              title: '上传并解析',
              description: uploading ? (
                <div className={styles.uploading}>
                  <Spin size="small" />
                  <span>正在上传文档并提取可检索内容...</span>
                </div>
              ) : (
                '将文档上传到专业知识库'
              ),
              status: getStepStatus(1),
              icon: uploading ? (
                <LoadingOutlined spin />
              ) : currentStep > 1 ? (
                <CheckCircleOutlined />
              ) : undefined,
            },
            {
              title: '文件上传完成',
              description: result
                ? result.success
                  ? '文档已上传，正在解析内容'
                  : '上传失败'
                : '等待上传',
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

        {/* 上传结果 */}
        {result && (
          <div className={styles.result}>
            <Result
              status={result.success ? 'success' : 'error'}
              title={result.success ? '文件上传完成' : '上传失败'}
              subTitle={
                <div className={styles.resultInfo}>
                  {result.success ? (
                    <p>
                      文档 <strong>{result.filename}</strong>{' '}
                      已上传，解析完成后即可检索。
                    </p>
                  ) : (
                    <p className={styles.errorText}>
                      {result.error || result.message}
                    </p>
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
