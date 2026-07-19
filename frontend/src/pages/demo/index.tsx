import {
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  RightOutlined,
  SafetyOutlined,
  SearchOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { request } from '@/api/request'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import styles from './index.module.scss'

const { Title, Text, Paragraph } = Typography

interface Scenario {
  id: string
  title: string
  category: string
  order: number
  question: string
  answer: string
  retrieval_trace: RetrievalTrace[]
  meta: Record<string, unknown>
}

interface RetrievalTrace {
  rank: number
  score: number | null
  rerank_score: number | null
  doc_name: string
  page_or_chunk: string
  snippet: string
  source_kind: string
  routing: string
  rrf_fusion_weight: number | null
  degraded: boolean
  as_of?: string
  table_name?: string
}

interface ReadyCheck {
  overall: string
  checks: Record<
    string,
    { ok: boolean | null; detail: string; latency_ms: number }
  >
}

type ReadyState = 'loading' | 'ready' | 'degraded'

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  检索: <SearchOutlined />,
  安全: <SafetyOutlined />,
  研究: <ExperimentOutlined />,
}

const SOURCE_KIND_LABELS: Record<string, string> = {
  document: '文档',
  policy: '政策',
  news: '新闻',
  bidding: '招投标',
  sql_row: '结构化数据',
  market_quote: '市场行情',
  none: '无命中',
}

function ReadyPanel({
  ready,
  state,
  scenariosLoaded,
}: {
  ready: ReadyCheck | null
  state: ReadyState
  scenariosLoaded: boolean
}) {
  if (state === 'loading') {
    return (
      <section className={styles.readyPanel} aria-label="环境预检">
        <div className={styles.readyHeading}>
          <Text strong>环境预检</Text>
          <Text type="secondary">正在检查可选服务，不影响 fixture 演示加载。
          </Text>
        </div>
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
      </section>
    )
  }

  if (state === 'degraded' || !ready) {
    return (
      <Alert
        className={styles.readyAlert}
        type="warning"
        showIcon
        message="环境预检未完成"
        description={
          scenariosLoaded
            ? '部分依赖暂时不可用或响应超时。已加载的四个冻结场景仍可正常查看。'
            : '部分依赖暂时不可用或响应超时。场景数据将独立加载，预检结果不会阻断请求。'
        }
      />
    )
  }

  const isReady = ready.overall === 'ready'

  return (
    <section className={styles.readyPanel} aria-label="环境预检">
      <div className={styles.readyHeading}>
        <div className={styles.statusTitle}>
          {isReady ? (
            <CheckCircleOutlined className={styles.okIcon} />
          ) : (
            <WarningOutlined className={styles.warnIcon} />
          )}
          <Text strong>环境预检</Text>
          <Tag color={isReady ? 'success' : 'warning'}>
            {isReady ? '就绪' : '部分降级'}
          </Tag>
        </div>
        <Text type="secondary">预检仅说明运行环境，不阻断冻结场景。</Text>
      </div>
      <Descriptions
        className={styles.readyDescriptions}
        size="small"
        column={{ xs: 1, sm: 1, md: 2 }}
        bordered
      >
        {Object.entries(ready.checks).map(([key, value]) => (
          <Descriptions.Item key={key} label={key}>
            <span className={styles.checkValue}>
              {value.ok === true ? (
                <CheckCircleOutlined className={styles.okIcon} />
              ) : value.ok === false ? (
                <CloseCircleOutlined className={styles.errorIcon} />
              ) : (
                <WarningOutlined className={styles.warnIcon} />
              )}
              <span>{value.detail}</span>
              <span className={styles.mono}>{value.latency_ms} ms</span>
            </span>
          </Descriptions.Item>
        ))}
      </Descriptions>
    </section>
  )
}

function TraceItem({ trace }: { trace: RetrievalTrace }) {
  return (
    <article className={styles.traceItem}>
      <div className={styles.traceRail} aria-hidden="true">
        <span>{trace.rank || '—'}</span>
      </div>
      <div className={styles.traceBody}>
        <div className={styles.traceHeader}>
          <div>
            <Text className={styles.sourceType}>
              {SOURCE_KIND_LABELS[trace.source_kind] ?? trace.source_kind}
            </Text>
            <Title level={5}>{trace.doc_name}</Title>
          </div>
          {trace.degraded && <Tag color="error">降级证据</Tag>}
        </div>

        <Descriptions
          className={styles.traceDescriptions}
          size="small"
          column={{ xs: 1, sm: 2, md: 3 }}
          bordered
        >
          <Descriptions.Item label="定位">{trace.page_or_chunk}</Descriptions.Item>
          <Descriptions.Item label="路由">
            <span className={styles.mono}>{trace.routing}</span>
          </Descriptions.Item>
          <Descriptions.Item label="检索 / Rerank">
            <span className={styles.mono}>
              {trace.score?.toFixed(3) ?? '—'} /{' '}
              {trace.rerank_score?.toFixed(3) ?? '—'}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="RRF 权重">
            <span className={styles.mono}>
              {trace.rrf_fusion_weight?.toFixed(2) ?? '—'}
            </span>
          </Descriptions.Item>
          {trace.table_name && (
            <Descriptions.Item label="表名">
              <span className={styles.mono}>{trace.table_name}</span>
            </Descriptions.Item>
          )}
          {trace.as_of && (
            <Descriptions.Item label="数据时点">
              <span className={styles.mono}>{trace.as_of}</span>
            </Descriptions.Item>
          )}
        </Descriptions>

        <div className={styles.evidenceSnippet}>
          <Text className={styles.evidenceLabel}>证据片段</Text>
          <blockquote>{trace.snippet}</blockquote>
        </div>
      </div>
    </article>
  )
}

function ScenarioCard({
  scenario,
  expanded,
  onToggle,
}: {
  scenario: Scenario
  expanded: boolean
  onToggle: () => void
}) {
  const detailsId = `scenario-${scenario.id}`

  return (
    <Card className={styles.scenarioCard}>
      <div className={styles.scenarioHeader}>
        <div className={styles.scenarioIdentity}>
          <span className={styles.categoryIcon} aria-hidden="true">
            {CATEGORY_ICONS[scenario.category] ?? <ApiOutlined />}
          </span>
          <div>
            <div className={styles.scenarioMeta}>
              <Tag>{scenario.category}</Tag>
              <span className={styles.fixtureLabel}>FIXTURE · {scenario.id}</span>
            </div>
            <Title level={4}>{scenario.title}</Title>
          </div>
        </div>
        <Button
          type={expanded ? 'default' : 'primary'}
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={detailsId}
        >
          {expanded ? '收起证据' : '查看证据'}
        </Button>
      </div>

      <div className={styles.questionPreview}>
        <Text className={styles.pathLabel}>问题</Text>
        <Paragraph>{scenario.question}</Paragraph>
      </div>

      {expanded && (
        <div id={detailsId} className={styles.evidencePath}>
          <section className={styles.pathSection}>
            <div className={styles.pathMarker} aria-hidden="true">
              <span />
              <RightOutlined />
            </div>
            <div className={styles.pathContent}>
              <div className={styles.sectionHeading}>
                <Text className={styles.pathLabel}>来源</Text>
                <Text type="secondary">
                  {scenario.retrieval_trace.length} 条可追溯记录
                </Text>
              </div>
              <div className={styles.traceList}>
                {scenario.retrieval_trace.map((trace, index) => (
                  <TraceItem
                    key={`${trace.rank}-${trace.doc_name}-${index}`}
                    trace={trace}
                  />
                ))}
              </div>
            </div>
          </section>

          <section className={styles.pathSection}>
            <div className={styles.pathMarker} aria-hidden="true">
              <span />
              <CheckCircleOutlined />
            </div>
            <div className={`${styles.pathContent} ${styles.conclusion}`}>
              <Text className={styles.pathLabel}>结论</Text>
              <div className={styles.answerText}>{scenario.answer}</div>
            </div>
          </section>
        </div>
      )}
    </Card>
  )
}

export default function DemoPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [ready, setReady] = useState<ReadyCheck | null>(null)
  const [readyState, setReadyState] = useState<ReadyState>('loading')
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const updateScenarioParam = useCallback(
    (id?: string) => {
      const next = new URLSearchParams(searchParams)
      if (id) next.set('scenario', id)
      else next.delete('scenario')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const fetchReady = useCallback(async () => {
    setReadyState('loading')
    try {
      const { data } = await request.get<ReadyCheck>('/demo/ready', {
        timeout: 4000,
        loading: false,
        errorToast: false,
      })
      setReady(data)
      setReadyState('ready')
    } catch {
      setReady(null)
      setReadyState('degraded')
    }
  }, [])

  const fetchScenarios = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const { data } = await request.get<{ scenarios?: Scenario[] }>(
        '/demo/scenarios',
        { timeout: 6000, loading: false, errorToast: false },
      )
      const nextScenarios = data.scenarios ?? []
      const linkedId = new URLSearchParams(window.location.search).get(
        'scenario',
      )
      setScenarios(nextScenarios)
      setExpanded((previous) => {
        if (linkedId && nextScenarios.some(({ id }) => id === linkedId)) {
          return { [linkedId]: true }
        }
        return Object.fromEntries(
          nextScenarios
            .filter(({ id }) => previous[id])
            .map(({ id }) => [id, true]),
        )
      })
    } catch {
      setError(
        '场景服务请求失败或 6 秒内未响应。请检查 API 服务后重试。',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchReady()
    void fetchScenarios()
  }, [fetchReady, fetchScenarios])

  const toggle = (id: string) => {
    if (expanded[id]) {
      setExpanded({})
      updateScenarioParam()
    } else {
      setExpanded({ [id]: true })
      updateScenarioParam(id)
    }
  }

  const expandAll = () => {
    setExpanded(Object.fromEntries(scenarios.map(({ id }) => [id, true])))
    updateScenarioParam()
  }

  const collapseAll = () => {
    setExpanded({})
    updateScenarioParam()
  }

  return (
    <main className={styles.demoPage}>
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <Text className={styles.eyebrow}>公开演示 · 冻结证据集</Text>
          <Title level={1}>半导体行业研究助手</Title>
          <Paragraph>
            选择一个预置问题，检查检索来源、路由与结论如何形成可追溯链路。
          </Paragraph>
        </div>
        <div className={styles.heroScope} aria-label="演示范围">
          <Text className={styles.scopeLabel}>研究范围</Text>
          <Text>芯片设计 · 材料设备 · 晶圆制造 · 封装测试</Text>
        </div>
      </header>

      <ReadyPanel
        ready={ready}
        state={readyState}
        scenariosLoaded={scenarios.length > 0}
      />

      <section className={styles.workspace} aria-labelledby="scenario-heading">
        <div className={styles.workspaceHeader}>
          <div>
            <Text className={styles.eyebrow}>证据追踪工作区</Text>
            <Title id="scenario-heading" level={2}>
              四个可复现场景
            </Title>
          </div>
          <Space wrap className={styles.actions}>
            <Button onClick={expandAll} disabled={!scenarios.length}>
              全部展开
            </Button>
            <Button onClick={collapseAll} disabled={!scenarios.length}>
              全部收起
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => void fetchScenarios()}
              loading={loading}
            >
              刷新场景
            </Button>
          </Space>
        </div>

        {error && (
          <Alert
            className={styles.loadAlert}
            message="场景加载失败"
            description={error}
            type="error"
            showIcon
            action={
              <Button size="small" onClick={() => void fetchScenarios()}>
                重试
              </Button>
            }
          />
        )}

        {loading && scenarios.length === 0 ? (
          <div className={styles.loadingList} aria-label="正在加载场景">
            <Skeleton active paragraph={{ rows: 2 }} />
            <Skeleton active paragraph={{ rows: 2 }} />
          </div>
        ) : scenarios.length === 0 ? (
          <Empty description="暂无可用的演示场景" />
        ) : (
          <div className={styles.scenarioList}>
            {scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                expanded={!!expanded[scenario.id]}
                onToggle={() => toggle(scenario.id)}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
