# P0 验收与收尾清单（2026-07-18）

本文档记录 `agent/p0-project-hardening` 分支的 P0 验收结论、收尾动作，以及在仓库转为公开前需要由项目负责人人工勾选的事项。

文档不替代现有 `docs/ENGINEERING_BASELINE.md` 与 `docs/RELEASE_AND_OWNERSHIP_CHECKLIST.md`，
仅作为 P0 关闭时的"快照"，供下一任 Agent 或 README 读者快速了解当前质量门禁与剩余风险。

> **历史快照说明：** 本文中的分支、构建体积、未完成项和发布步骤记录 2026-07-18
> 当时的状态，不作为当前项目事实来源。当前状态以 `README.md`、
> `docs/ENGINEERING_BASELINE.md` 和最新 GitHub Actions 为准。

## 一、P0 验收结论（自动可验证）

| 项目 | 期望 | 实际 | 备注 |
| --- | --- | --- | --- |
| 后端单元 + 集成测试 | 全绿 | 480 项（461 unit + 19 integration） | `make test-backend-unit` / `make test-backend-integration` |
| Evidence 契约测试 | 全绿 | 48/48 | `make test-evidence-contract` |
| 前端 ESLint | 0 error / 0 warning | 0/0 | `make lint-frontend` |
| 前端生产构建 | 通过 | 通过，dist 2.56 MB | `make build-frontend` |
| Compose 配置 | `docker compose config --quiet` 通过 | 通过 | `make validate-compose`；本地 WSL `/usr/bin/docker` 失效时使用 `DOCKER=/mnt/e/env/docker/resources/bin/docker.exe make validate-compose` |
| 外部语料注册表校验 | ≥15 份允许全文入库 | 15 份允许 / 2 份仅元数据 / 0 错误 | `make validate-sources` |
| 评测集结构 + 关联文档校验 | 通过 | 通过 | `make validate-eval` |
| 基线 manifest 一致性 | 通过 | 通过 | `make validate-baseline` |
| 多源联合评测夹具门禁 | 12/12 | 12/12 | `make evaluate-multi-source`，产物 `/tmp/industry-research-multi-source-report.json`，不再污染仓库内历史报告 |
| GitHub Actions | backend / frontend / images 三段全绿 | 全绿 | 见最近一次 Run 29645070772 |
| 历史中是否曾提交过 `.env` | 不应有 | 无 | `git log --all -- .env` 为空，仅 `backend/.env.example` 被跟踪 |
| 模型状态接口是否泄漏密钥或内部地址 | 不应 | 未泄漏 | 由 `security_boundaries` 测试保证 |

### 模型路由（自动验证）

- 路由模式：`MODEL_ROUTING_MODE=auto`，实际生成路由解析为 `cloud`。
- 云端生成：阿里云百炼 `deepseek-v4-flash`。
- 本地备用：Ollama `industry-qwen3:4b`。
- 查询 Embedding：`cloud`，百炼 `text-embedding-v4`，1024 维。
- 入库 Embedding：`hybrid`（云端 + 本地 `bge-m3`，1024 维，双 Collection 隔离）。
- Rerank：启用，百炼 `qwen3-rerank`。

设计文档：`docs/EMBEDDING_ROUTING_DESIGN.md`。

## 二、本地复跑 `make check`（2026-07-18 实测）

执行命令（在仓库根目录，WSL Ubuntu）：

```bash
# 后端 + 评测：直接 make
.venv/bin/python -m pip install --upgrade pip
make check-backend-deps check-backend-import \
     test-backend-unit test-backend-integration test-evidence-contract \
     validate-sources validate-baseline validate-eval evaluate-multi-source

# 前端：通过 nvm 切换到 Linux Node 22/24 再跑，避免 WSL↔Windows npm 跨边界
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 22
cd frontend && npm ci && npm run lint && npm run build

# Docker Compose：使用 Windows 端 docker.exe，避开 WSL Docker Desktop IO 错误
DOCKER=/mnt/e/env/docker/resources/bin/docker.exe make validate-compose
```

实测结果：

- 后端 + 评测：全部通过，单次脚本耗时约 40 秒。
- 前端：lint 0 error / 0 warning，build 通过；已完成路由级拆分，
  ECharts chunk 为 690.01 kB（gzip 235.05 kB），仍需继续降低首屏预加载体积。
- `validate-compose`：1 秒内通过（Docker v29.6.1 + Compose v5.2.0）。

## 三、收尾动作（本会话内完成）

1. **本地 `make check` 三段对齐**——见上节。
2. **加固 `.gitignore`**：
   - 把 `data/evaluation-private/` 同时声明为 `**/evaluation-private/`，防御未来在子目录误建私有评测库。
   - 在 `sample-data/` 与 `reports/` 下追加 `_private_*` / `_answers_*` / `_master.json` / `*_test_answers*` / `*_hidden_answers*` 等命名规则，防止日后新增私有 split 时被跟踪。
   - 增加注释指向 `sample-data/semiconductor_rag_eval_manifest.json` 的 `label_visibility` 作为唯一真相来源。
3. **新增本文档** —— 沉淀 P0 验收结论 + 公开前人工确认清单。
4. **Fast-forward 合并** `agent/p0-project-hardening` → `main`（不动 `origin/main`，详见第 6 节）。

## 四、变更文件概览（自上一合并点 `2546de9` 起）

`git diff --stat 2546de9..HEAD` 共 263 文件，+13307/-7992 行，分类摘要：

- 模型路由：`backend/app/service/embedding_router.py`（新增）、`embedding_service.py`、`retrieval_service.py`、`llm_router.py`、`rerank_service.py`、`text2sql_service.py` 等。
- 证据契约：`service/evidence_contract.py`、`evidence_adapters/*`（5 个适配器）、`multi_source_research.py`。
- 上传安全：`backend/app/core/upload_security.py`、`core/rate_limit.py`、`core/security.py` 增强。
- 测试：`test_evidence_contract.py`（48 项）、`test_embedding_routing.py`、`test_security_boundaries.py`、`test_baseline_manifest.py` 等。
- 旧系统清理：`document_router.py`、`document_service.py`、`chat_service_v2.py`、`schemas/document.py`、`docker-compose-base.yml`、`backend/app/requirements.txt` 等删除；前端 mock 数据被替换为半导体示例。
- 文档：`docs/EMBEDDING_ROUTING_DESIGN.md`、`docs/MULTI_SOURCE_RESEARCH_PLATFORM.md`、`docs/NEXT_MODEL_HANDOFF.md`、`docs/SECURITY.md`、`docs/RELEASE_AND_OWNERSHIP_CHECKLIST.md` 等新增或增强；`README.md`、`backend/README.md`、`docs/ENGINEERING_BASELINE.md`、`docs/LEARNING_AND_INTERVIEW_GUIDE.md`、`docs/PORTFOLIO_AND_RESUME.md`、`docs/PROJECT_CLOSURE_ROADMAP.md` 修订。
- CI：`.github/workflows/ci.yml` 升级到 Node 24 对应 actions 镜像，剔除 Node 20 弃用警告。
- 前端：`frontend/mock/data/{chat,deepsearch}`、`mock/session.ts` 替换为半导体示例；`pages/index/index.tsx`、`pages/auth/login.tsx`、`pages/chat/component/news.tsx` 等微小文案/配置更新。
- 数据集与报告：`reports/baseline-manifest.json`、`reports/multi_source_advanced_packaging_*.json`、`reports/rag_model_comparison_local4b_vs_v4pro.md`、`reports/semiconductor_rag_answers_regression_*.json` 等。

完整列表见 `git diff --name-only 2546de9..HEAD`。

## 五、未在 P0 范围内处理的事项（P1+）

按上一任 Agent 的交接建议：

- **P1-1 Text2SQL 安全**：只读账户、SQL AST 解析、表/列白名单、`SELECT`-only、最大返回行数、statement timeout、失败测试。**当前唯一公开前必须解决的实质风险**。
- **P1-2 多源 Provider 可靠性**：契约测试、超时、有限重试、失败降级、来源时间字段、禁止失败后编造结果。
- **P1-3 数据治理增强**：新闻按 URL/标题/正文哈希去重、招投标实体归一、公告生命周期合并、股票代码映射改为可审计实体解析。
- **P1-4 Critic 增强**：来源时效、数字口径与单位、时间点、来源冲突、跨源推断标记、缺失关键来源拒答。
- **P1-5 模型实测**：百炼 `deepseek-v4-flash` 生成冒烟、`text-embedding-v4` Embedding 冒烟、`qwen3-rerank` 重排冒烟、固定小样本 cloud/local/hybrid 对比。

P1-1 之前**不要**把 `EMBEDDING_ROUTING_MODE` 直接切到 `hybrid`（已通过 hackathon 完成双索引重建）。

## 六、合并与发布

- 本地合并策略：`git merge --ff-only origin/agent/p0-project-hardening`（要求 `main` 没有新推进）。
- 推送策略：合并本身不动 `origin/main`，由项目负责人手动 push；push 后 GitHub Actions 会再跑一次 `CI`，需保持三段全绿。
- 已公开仓库（MIT License），`docs/RELEASE_AND_OWNERSHIP_CHECKLIST.md` 中的 5 项人工确认已于 2026-07-18 全部清零。

## 七、给项目负责人的人工确认清单（公开前必勾）

下表对应 `docs/RELEASE_AND_OWNERSHIP_CHECKLIST.md` 的尚未由项目负责人勾选的事项。本文件无法替你确认，必须由你逐项答复 / 打勾。完成前请保持仓库 Private，并保留 P0 验收产物不被覆盖。

| # | 事项 | 答复位置 |
| --- | --- | --- |
| 1 | 项目内是否有文件（代码、文档、截图、mock、报告）产生于公司设备、公司工作时间或公司项目？若是，是否已剥离或得到对外授权？ | 在本文档 / `RELEASE_AND_OWNERSHIP_CHECKLIST.md` 标注。 |
| 2 | `frontend/src/assets`、`frontend/mock/*`、`.codex/visual-reviews/baseline/*.png`、AMIS 截图、Ant Design 图标等 UI 素材/截图/图标/字体，是否拥有再分发权？是否需要替换为自有或开源等同品？ | 同上。 |
| 3 | `reports/*.md`、`reports/*.json` 中的样例报告是否包含公司秘密或客户信息？若有，是否已脱敏或剥离？ | 同上。 |
| 4 | 重新做一次干净 clone + 完整 `git log -p` 复核，确认 `.env`、原始 PDF、私有答案 (`data/evaluation-private/`)、运行时数据从未进入历史 commit。 | 推荐执行：`git clone … && git log -p -- .env`、`git grep -nE 'sk-[A-Za-z0-9]{16,}\|AKID[A-Z0-9]{16,}' $(git rev-list --all)`。 |
| 5 | 百炼密钥、未来其它第三方 API Key 是否仍仅存在于本地 `.env`、`GitHub Actions secrets` 与本地密钥管理器，未被明文写入文档或截图？ | 确认后打勾。 |

完成上述 5 项后，仍建议保留仓库 Private 到第二轮回访（公开前后的曝光应被控制），再视需要决定是否切换到 Public。

## 八、操作注意事项（再次提醒）

- 禁止提交或打印 `backend/.env` 真实内容。
- 禁止在未备份并取得项目负责人确认的情况下删除旧 Milvus 数据卷。
- 禁止直接将 `EMBEDDING_ROUTING_MODE` 切到 `hybrid` 而不完成双索引重建与 cloud/local/hybrid 对比评测。
- 禁止提交 `.env` 真实内容到仓库（仓库现为公开 MIT License）。
- 禁止把固定回归集 20/20 表述成"真实业务准确率 100%"——它只是公开带答案的回放用例，不是产品实际业务指标。
- 修改后请按上文第二节命令复跑本地三段，再 push 触发 CI。
