import { useCallback, useEffect, useState } from "react"
import { Alert, Badge, Button, Card, Descriptions, Divider, Empty, Space, Spin, Tag, Typography } from "antd"
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ExperimentOutlined,
  SearchOutlined,
  SafetyOutlined,
  ApiOutlined,
  ClusterOutlined,
} from "@ant-design/icons"
import styles from "./index.module.scss"

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
  checks: Record<string, { ok: boolean | null; detail: string; latency_ms: number }>
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  "检索": <SearchOutlined />,
  "安全": <SafetyOutlined />,
  "研究": <ExperimentOutlined />,
}

const SOURCE_KIND_LABELS: Record<string, string> = {
  document: "📄 文档",
  policy: "🏛️ 政策",
  news: "📰 新闻",
  bidding: "📋 招投标",
  sql_row: "🗂️ 结构化数据",
  market_quote: "📈 市场行情",
  none: "—",
}

function ReadyPanel({ ready }: { ready: ReadyCheck | null }) {
  if (!ready) return <Spin />

  const statusIcon = (ok: boolean | null) => {
    if (ok === true) return <CheckCircleOutlined style={{ color: "#52c41a" }} />
    if (ok === false) return <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
    return <ExclamationCircleOutlined style={{ color: "#faad14" }} />
  }

  return (
    <div className={styles.readyPanel}>
      <Title level={5}>
        环境预检{" "}
        <Badge status={ready.overall === "ready" ? "success" : "warning"} text={ready.overall === "ready" ? "就绪" : "部分降级"} />
      </Title>
      <Descriptions size="small" column={2} bordered>
        {Object.entries(ready.checks).map(([key, value]) => (
          <Descriptions.Item key={key} label={key}>
            {statusIcon(value.ok)} {value.detail}{" "}
            <Text type="secondary">({value.latency_ms}ms)</Text>
          </Descriptions.Item>
        ))}
      </Descriptions>
    </div>
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
  return (
    <Card
      className={styles.scenarioCard}
      title={
        <Space>
          {CATEGORY_ICONS[scenario.category] ?? <ApiOutlined />}
          <Text strong>{scenario.title}</Text>
          <Tag color="blue">{scenario.category}</Tag>
        </Space>
      }
      extra={
        <Button type={expanded ? "default" : "primary"} size="small" onClick={onToggle}>
          {expanded ? "收起" : "查看详情"}
        </Button>
      }
    >
      <Paragraph>
        <Text type="secondary">Q:</Text> {scenario.question}
      </Paragraph>

      {expanded && (
        <>
          <Divider />
          <div className={styles.answer}>
            <Title level={5}>答案</Title>
            <Paragraph style={{ whiteSpace: "pre-wrap" }}>{scenario.answer}</Paragraph>
          </div>

          <Divider>检索追踪</Divider>
          <div className={styles.traceList}>
            {scenario.retrieval_trace.map((trace, idx) => (
              <Card
                key={idx}
                size="small"
                className={styles.traceItem}
                type="inner"
                title={
                  <Space>
                    <Badge count={trace.rank} style={{ backgroundColor: "#1677ff" }} />
                    <Text strong>{trace.doc_name}</Text>
                    {trace.degraded && <Tag color="red">降级</Tag>}
                  </Space>
                }
              >
                <Descriptions size="small" column={2} bordered>
                  <Descriptions.Item label="来源类型">
                    {SOURCE_KIND_LABELS[trace.source_kind] ?? trace.source_kind}
                  </Descriptions.Item>
                  <Descriptions.Item label="路由">{trace.routing}</Descriptions.Item>
                  <Descriptions.Item label="检索分">{trace.score?.toFixed(3) ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="Rerank 分">{trace.rerank_score?.toFixed(3) ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="RRF 融合权重">
                    {trace.rrf_fusion_weight?.toFixed(2) ?? "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="定位">{trace.page_or_chunk}</Descriptions.Item>
                  {trace.table_name && (
                    <Descriptions.Item label="表名">{trace.table_name}</Descriptions.Item>
                  )}
                  {trace.as_of && (
                    <Descriptions.Item label="时点">{trace.as_of}</Descriptions.Item>
                  )}
                </Descriptions>
                <Paragraph style={{ marginTop: 8 }}>
                  <Text type="secondary">证据片段：</Text>
                  <Text code>{trace.snippet}</Text>
                </Paragraph>
              </Card>
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

export default function DemoPage() {
  const [ready, setReady] = useState<ReadyCheck | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchReady = useCallback(async () => {
    try {
      const resp = await fetch("/demo/ready")
      if (!resp.ok) return
      setReady((await resp.json()) as ReadyCheck)
    } catch {
      // preflight is best-effort; backend may not have all services
    }
  }, [])

  const fetchScenarios = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const resp = await fetch("/demo/scenarios")
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setScenarios(data.scenarios ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load demo scenarios")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchReady()
    fetchScenarios()
  }, [fetchReady, fetchScenarios])

  const toggle = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const expandAll = () => {
    const all: Record<string, boolean> = {}
    scenarios.forEach((s) => (all[s.id] = true))
    setExpanded(all)
  }

  const collapseAll = () => setExpanded({})

  return (
    <div className={styles.demoPage}>
      <Title level={3}>
        <ClusterOutlined /> 面试演示 —— 半导体行业研究助手
      </Title>
      <Paragraph type="secondary">
        本页面展示项目的四大核心能力：Hybrid 检索、证据拒答、Research Agent 管线与多源联合研究。
        所有数据来自 pre-baked 场景 fixture，不依赖实时 API 调用。
      </Paragraph>

      <ReadyPanel ready={ready} />

      <Divider />

      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button onClick={expandAll}>全部展开</Button>
          <Button onClick={collapseAll}>全部收起</Button>
          <Button onClick={fetchScenarios} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {error && (
        <Alert message="加载失败" description={error} type="error" showIcon closable style={{ marginBottom: 16 }} />
      )}

      {loading ? (
        <Spin size="large" style={{ display: "block", margin: "40px auto" }} />
      ) : scenarios.length === 0 ? (
        <Empty description="暂无演示场景" />
      ) : (
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {scenarios.map((s) => (
            <ScenarioCard
              key={s.id}
              scenario={s}
              expanded={!!expanded[s.id]}
              onToggle={() => toggle(s.id)}
            />
          ))}
        </Space>
      )}
    </div>
  )
}
