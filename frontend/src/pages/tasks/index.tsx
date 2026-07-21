import {
  TaskRecord,
  TaskStatus,
  cancelTask,
  getTasks,
} from '@/api/tasks'
import {
  CheckOutlined,
  CloseOutlined,
  ExclamationOutlined,
  LoadingOutlined,
  PauseOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { Alert, Button, Modal, Skeleton, message } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import styles from './index.module.scss'

const NON_TERMINAL = new Set<TaskStatus>(['queued', 'running', 'retrying'])

const STATUS_META: Record<
  TaskStatus,
  { label: string; description: string; icon: React.ReactNode }
> = {
  queued: {
    label: '已入队',
    description: '等待 Worker 领取',
    icon: <PauseOutlined />,
  },
  running: {
    label: '执行中',
    description: '正在处理研究或文档',
    icon: <LoadingOutlined />,
  },
  retrying: {
    label: '重试中',
    description: '等待下一次执行',
    icon: <SyncOutlined />,
  },
  succeeded: {
    label: '已完成',
    description: '结果已写入',
    icon: <CheckOutlined />,
  },
  failed: {
    label: '失败',
    description: '需要检查错误记录',
    icon: <ExclamationOutlined />,
  },
  cancelled: {
    label: '已取消',
    description: '任务已停止',
    icon: <CloseOutlined />,
  },
}

const TASK_TYPE_LABELS: Record<string, string> = {
  'research.run': '深度研究',
  'document.process': '知识库文档入库',
  'attachment.process': '研究附件解析',
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null) {
    const candidate = error as {
      message?: string
      response?: { data?: { detail?: string } }
    }
    return candidate.response?.data?.detail || candidate.message
  }
  return undefined
}

function formatDate(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.round(seconds / 60)} 分钟`
}

function formatResult(result: unknown) {
  if (typeof result === 'string') return result
  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
}

function canCancel(task: TaskRecord) {
  if (task.cancel_requested) return false
  return (
    task.status === 'queued' ||
    task.status === 'retrying' ||
    (task.status === 'running' && task.task_type === 'research.run')
  )
}

function ProcessTrace({ status }: { status: TaskStatus }) {
  const activeIndex =
    status === 'queued'
      ? 0
      : status === 'running' || status === 'retrying'
        ? 1
        : 3
  const labels = ['入队', '执行', '校验', '终态']

  return (
    <ol className={styles.processTrace} aria-label={`工艺路径：${STATUS_META[status].label}`}>
      {labels.map((label, index) => (
        <li
          key={label}
          className={
            index < activeIndex
              ? styles.traceComplete
              : index === activeIndex
                ? styles[`trace_${status}`]
                : undefined
          }
        >
          <span className={styles.traceNode} aria-hidden="true" />
          <span>{label}</span>
        </li>
      ))}
    </ol>
  )
}

function TaskRow({
  task,
  onCancel,
}: {
  task: TaskRecord
  onCancel: (task: TaskRecord) => void
}) {
  const result = task.has_result ? formatResult(task.result) : ''
  const meta = STATUS_META[task.status]
  const isRunningDocument =
    task.status === 'running' && task.task_type !== 'research.run'

  return (
    <article className={styles.taskRow} aria-labelledby={`task-${task.task_id}`}>
      <div className={styles.taskIdentity}>
        <div className={styles.taskHeading}>
          <span className={`${styles.statusMark} ${styles[`status_${task.status}`]}`}>
            {meta.icon}
          </span>
          <div>
            <h2 id={`task-${task.task_id}`}>
              {TASK_TYPE_LABELS[task.task_type] || task.task_type}
            </h2>
            <code title={task.task_id}>{task.task_id}</code>
          </div>
        </div>
        <span className={`${styles.statusBadge} ${styles[`status_${task.status}`]}`}>
          {task.cancel_requested ? '取消中' : meta.label}
        </span>
      </div>

      <ProcessTrace status={task.status} />

      <dl className={styles.taskMetadata}>
        <div>
          <dt>提交</dt>
          <dd>{formatDate(task.created_at)}</dd>
        </div>
        <div>
          <dt>尝试</dt>
          <dd>
            {task.attempts} / {task.max_retries + 1}
          </dd>
        </div>
        <div>
          <dt>超时阈值</dt>
          <dd>{formatDuration(task.timeout_seconds)}</dd>
        </div>
        <div>
          <dt>{task.finished_at ? '结束' : '启动'}</dt>
          <dd>{formatDate(task.finished_at || task.started_at)}</dd>
        </div>
      </dl>

      {(task.error || result) && (
        <details
          className={`${styles.taskPayload} ${task.error ? styles.payloadError : ''}`}
          open={task.status === 'failed'}
        >
          <summary>{task.error ? '查看错误记录' : '查看任务结果'}</summary>
          <pre>{task.error || result}</pre>
        </details>
      )}

      <div className={styles.taskFooter}>
        <span>
          {task.cancel_requested
            ? '取消请求已写入，等待安全停止'
            : isRunningDocument
              ? '文档已进入解析，为避免中间结果不一致，当前不可取消'
              : meta.description}
        </span>
        {canCancel(task) && (
          <Button danger onClick={() => onCancel(task)}>
            取消任务
          </Button>
        )}
      </div>
    </article>
  )
}

function LoadingLedger() {
  return (
    <div className={styles.loadingLedger} aria-label="正在读取任务" aria-busy="true">
      {[0, 1, 2].map((item) => (
        <div className={styles.loadingRow} key={item}>
          <Skeleton active title={{ width: '34%' }} paragraph={{ rows: 3 }} />
        </div>
      ))}
    </div>
  )
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<TaskRecord | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const requestInFlight = useRef(false)

  const loadTasks = useCallback(async (mode: 'initial' | 'refresh' | 'poll') => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    if (mode === 'refresh') setRefreshing(true)
    try {
      const response = await getTasks()
      setTasks(response.tasks)
      setError(null)
    } catch (loadError) {
      setError(
        getErrorMessage(loadError) ||
          '任务运行记录暂时无法读取，请检查网络后重试。',
      )
    } finally {
      requestInFlight.current = false
      if (mode === 'refresh') setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadTasks('initial')
  }, [loadTasks])

  const hasActiveTasks = Boolean(
    tasks?.some((task) => NON_TERMINAL.has(task.status)),
  )

  useEffect(() => {
    if (!hasActiveTasks) return
    const timer = window.setInterval(() => {
      void loadTasks('poll')
    }, 4000)
    return () => window.clearInterval(timer)
  }, [hasActiveTasks, loadTasks])

  const counts = useMemo(() => {
    const next = {
      total: tasks?.length || 0,
      queued: 0,
      active: 0,
      succeeded: 0,
      failed: 0,
      cancelled: 0,
    }
    tasks?.forEach((task) => {
      if (task.status === 'queued') next.queued += 1
      if (task.status === 'running' || task.status === 'retrying') next.active += 1
      if (task.status === 'succeeded') next.succeeded += 1
      if (task.status === 'failed') next.failed += 1
      if (task.status === 'cancelled') next.cancelled += 1
    })
    return next
  }, [tasks])

  const confirmCancel = async () => {
    if (!cancelTarget) return
    setCancelling(true)
    setCancelError(null)
    try {
      const updated = await cancelTask(cancelTarget.task_id)
      setTasks((current) =>
        current?.map((task) =>
          task.task_id === updated.task_id ? updated : task,
        ) || null,
      )
      message.success('取消请求已受理')
      setCancelTarget(null)
    } catch (cancelRequestError) {
      setCancelError(
        getErrorMessage(cancelRequestError) ||
          '取消请求未写入，请稍后再试。',
      )
    } finally {
      setCancelling(false)
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.workspace}>
        <header className={styles.pageHeader}>
          <div>
            <span className={styles.eyebrow}>研究运行账本</span>
            <h1>任务中心</h1>
            <p>
              跟踪深度研究、知识库文档和附件的持久化执行状态。
            </p>
          </div>
          <Button
            icon={<SyncOutlined spin={refreshing} />}
            onClick={() => void loadTasks('refresh')}
            loading={refreshing}
            disabled={tasks === null}
          >
            刷新记录
          </Button>
        </header>

        <section className={styles.calibrationStrip} aria-label="任务状态校准带">
          {[
            ['全部', counts.total],
            ['待调度', counts.queued],
            ['执行 / 重试', counts.active],
            ['已完成', counts.succeeded],
            ['失败', counts.failed],
            ['已取消', counts.cancelled],
          ].map(([label, count]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{count}</strong>
            </div>
          ))}
        </section>

        {error && tasks !== null && (
          <Alert
            className={styles.staleAlert}
            type="warning"
            showIcon
            message="自动更新已中断"
            description={error}
            action={
              <Button size="small" onClick={() => void loadTasks('refresh')}>
                重试
              </Button>
            }
          />
        )}

        <section className={styles.ledger} aria-label="任务运行记录">
          <div className={styles.ledgerHeader}>
            <span>最近任务</span>
            <span aria-live="polite">
              {hasActiveTasks ? '正在持续校准非终态任务' : '当前无需轮询'}
            </span>
          </div>

          {tasks === null && !error && <LoadingLedger />}

          {tasks === null && error && (
            <div className={styles.statePanel} role="alert">
              <ExclamationOutlined />
              <h2>无法读取任务账本</h2>
              <p>{error}</p>
              <Button type="primary" onClick={() => void loadTasks('refresh')}>
                重新读取
              </Button>
            </div>
          )}

          {tasks?.length === 0 && (
            <div className={styles.statePanel}>
              <span className={styles.emptyTrace} aria-hidden="true">
                <i />
                <i />
                <i />
                <i />
              </span>
              <h2>还没有持久化任务</h2>
              <p>
                发起深度研究、向专业知识库上传文档，或在研究中添加附件后，运行记录会出现在这里。
              </p>
            </div>
          )}

          {tasks?.map((task) => (
            <TaskRow key={task.task_id} task={task} onCancel={setCancelTarget} />
          ))}
        </section>
      </section>

      <Modal
        title="确认取消任务"
        open={Boolean(cancelTarget)}
        okText="确认取消"
        cancelText="保留任务"
        okButtonProps={{ danger: true }}
        confirmLoading={cancelling}
        closable={!cancelling}
        maskClosable={!cancelling}
        onOk={() => void confirmCancel()}
        onCancel={() => {
          if (!cancelling) {
            setCancelTarget(null)
            setCancelError(null)
          }
        }}
      >
        <p className={styles.modalCopy}>
          将向执行队列写入取消标记。已进入不可中断处理的文档任务不会被误报为已取消。
        </p>
        {cancelTarget && <code>{cancelTarget.task_id}</code>}
        {cancelError && (
          <Alert className={styles.modalAlert} type="error" showIcon message={cancelError} />
        )}
      </Modal>
    </main>
  )
}
