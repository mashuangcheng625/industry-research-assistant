# 本地部署、架构与演示手册

## 1. 可复现范围

项目提供两种本地运行方式：

- `./start-services.sh core`：只启动 PostgreSQL、Redis、etcd、MinIO 和
  Milvus，适合在宿主机运行后端与前端；
- `./start-services.sh app`：构建并启动中间件、后端容器和前端 Nginx
  容器，通过健康检查后才返回成功。

`app` 是本地演示 profile，不是生产 Kubernetes/HA 方案。它依赖宿主机
Ollama，默认模型为 `industry-qwen3:4b` 和 `bge-m3`。

## 2. 运行时架构

```mermaid
flowchart LR
    U["研究员 / 浏览器"] --> F["React + Nginx :5173"]
    F --> B["FastAPI :8000"]
    B --> PG["PostgreSQL<br/>用户、会话、文档、checkpoint"]
    B --> R["Redis<br/>取消、运行锁、缓存"]
    B --> M["Milvus<br/>密集向量与切片"]
    B --> O["Ollama / OpenAI-compatible<br/>生成与 Embedding"]
    B --> P["/metrics"]
    P --> PM["Prometheus :9090<br/>可选 observability profile"]
    PM --> G["Grafana :3000<br/>研究运行看板"]
    M --> E["etcd"]
    M --> S["MinIO"]
```

资料不从上传直接跳到模型，而是经过另一条可审计数据链：

```text
来源注册表（URL / 发布方 / 许可 / SHA-256）
  -> raw PDF
  -> normalized Markdown + frontmatter
  -> 稳定分块 + 页码/标题定位
  -> Embedding + Milvus collection
  -> 数量/哈希/重复 ID 对账
```

## 3. 首次启动

### 3.1 准备模型

```bash
ollama list
# 必须能看到 industry-qwen3:4b 和 bge-m3（bge-m3:latest 也可）
```

### 3.2 完整容器演示

```bash
./start-services.sh app
```

就绪标准不是固定 sleep，而是：

- PostgreSQL `pg_isready` 成功；
- Redis `PING` 成功；
- Milvus `/healthz` 成功；
- 后端 `/health/ready` 同时验证三个存储与两个配置模型；
- Nginx 能返回前端页面。

访问：

- 前端：`http://localhost:5173`
- OpenAPI：`http://localhost:8000/docs`
- 存活检查：`http://localhost:8000/health/live`
- 就绪检查：`http://localhost:8000/health/ready`

### 3.3 宿主机开发方式

```bash
./start-services.sh core
make setup-backend
cd frontend && npm ci --legacy-peer-deps && cd ..

cd backend
cp .env.example .env
PYTHONPATH=app ../.venv/bin/python -m uvicorn app_main:app --host 127.0.0.1 --port 8000
```

新终端中运行：

```bash
cd frontend
npm run dev
```

## 4. 资料与索引复现

原始 PDF 因体积和许可边界不进 Git，但来源 URL、许可决策和哈希都保留。
在宿为后端环境中：

```bash
make validate-sources
PYTHONPATH=backend/app .venv/bin/python \
  backend/app/scripts/collect_semiconductor_sources.py --download-approved

# 无外部模型的全语料结构/入库 smoke
make smoke-ingest-lite
```

独立 Milvus 2.6 的重建和故障处理见 `docs/MILVUS_REBUILD_RUNBOOK.md`。

## 5. 三步演示脚本

后端已就绪且公开语料已入库后：

```bash
make demo-rag API_URL=http://127.0.0.1:8000/chat/completion
```

该命令不依赖人工“看起来不错”，而是对三类行为执行可机读门槛：

1. `design-flow-001`：多阶段事实回答与引用覆盖；
2. `packaging-ucie-018`：互操作性综合分析；
3. `packaging-negative-020`：虚构型号无证据拒答。

结果写入 `reports/demo_rag_latest.json`。演示时还应手动点开回答的证据切片，
说明“引用编号合法”与“证据真正支持论断”的差异。

## 6. Agent 失败演示

真实本地模型完整运行曾经过规划、研究、分析、写作和审核，最终因
1 个 critical 和 2 个 major 未解决问题进入 `review_failed`，而不是被迭代上限
伪装成 `completed`。该案例用于展示：

- LLM 原始文本 verdict 为 pass 也不能绕过确定性严重问题否决；
- phase 和 `last_completed_phase` 分离，中途取消后可从安全游标恢复；
- 终态、分数、未解决问题、阶段耗时和 token 用量可审计。

详细实验与故障注入见 `docs/AGENT_RELIABILITY.md`。

## 7. 停止、观测与恢复

```bash
./start-services.sh status
./start-services.sh logs backend
./start-services.sh observability
./start-services.sh stop
```

`stop` 保留数据卷。`clean` 会二次确认后删除数据卷，不应用于故障排查的
第一步。Milvus 向量可从受审 Markdown 重建；PostgreSQL 提供手动
`make db-backup` / `make db-restore FILE=...`，并在 CI 中执行隔离库破坏—恢复演练；
尚未实现定时备份和异地保存。

迁移往返验收会执行全量降级并删除应用表，因此只接受库名以
`_migration_test` 结尾的专用空 PostgreSQL 数据库：

```bash
MIGRATION_TEST_DATABASE_URL=postgresql://user:password@host/industry_assistant_migration_test \
  make validate-migrations
```

备份恢复演练会先用 Alembic 创建 schema，写入哨兵数据，执行 `pg_dump`，
主动删除数据和表，再用 `pg_restore` 恢复并校验 schema drift、表数和行数。
它只接受 `_backup_test` 结尾的专用空库：

```bash
BACKUP_TEST_DATABASE_URL=postgresql://user:password@host/industry_assistant_backup_test \
  make validate-backup-restore
```

如果本地 PostgreSQL 数据卷来自旧版手写初始化 SQL，库中会有应用表但没有
`alembic_version`。`migrate` 服务会失败关闭，不会擅自 `stamp head`。先执行备份，
再根据是否需要保留本地数据选择显式迁移，或用 `./start-services.sh clean`
二次确认后重建纯演示数据卷。

## 8. 已知部署边界

- 容器已在干净 Python 3.12 / Node 22 基础镜像上真实构建并通过一次性 smoke；
- 后端镜像约 344 MB，基础镜像固定为 Debian Bookworm，并内置与服务端同主版本的
  PostgreSQL 15 客户端用于容器内备份恢复；当前锁文件仍包含测试、绘图和 Milvus Lite
  等非最小运行依赖；
- 前端生产依赖 `npm audit --omit=dev` 为 0 漏洞，开发依赖仍有 audit 项；
- 前端已完成路由级代码分割与 `echarts/core` 按需引入；修复 vendor 循环依赖后的
  ECharts chunk 为 690.01 kB（gzip 235.05 kB）；
- 已有覆盖 15 张表的 Alembic 迁移链和 upgrade/downgrade 命令；Compose 的一次性
  `migrate` 服务成功后后端才启动，默认不再调用 SQLAlchemy `create_all`；
- CI 门禁会在两个专用 PostgreSQL 库上分别验证往返迁移、ORM schema drift
  和备份破坏—恢复；尚未验证生产数据量下的无停机 schema 升级；
- 已支持单容器内 Prometheus multiprocess 聚合和 Grafana 自动装配；多实例由
  Prometheus 分别 scrape 后求和，不共享 mmap 目录；
- 未实现 TLS、生产级密钥托管、定时异地备份、多副本和滚动发布。
