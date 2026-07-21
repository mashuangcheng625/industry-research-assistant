# 可复现工程基线

日期：2026-07-17

## 支持环境

- Python 3.12
- Node.js 22
- Docker 29 / Docker Compose v5

## 本地验证

安装后端开发依赖：

```bash
make setup-backend
```

网络受限时可以切换镜像，但依赖版本约束不随镜像改变：

```bash
make setup-backend PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

前端首次安装：

```bash
cd frontend
npm ci --legacy-peer-deps
cd ..
```

运行完整静态检查：

```bash
make check
```

运行公开评测质量闸门（40 题有标签开发集 + 40 题无标签问题集）：

```bash
make validate-eval
```

评测维护者可在拥有 Git 忽略的私有答案键时额外运行：

```bash
make validate-eval-private
```

运行资料治理闸门（许可、SHA-256、可移植路径、frontmatter 一致性）：

```bash
make validate-sources
```

## 冻结基线

| 检查项 | 结果 |
| --- | ---: |
| 后端测试 | 469 项（459 unit + 10 integration，含 Redis 持久队列故障恢复） |
| 全语料 Milvus Lite smoke | 15 份资料 / 36 任务 / 5256 切片，4/4 库对账通过 |
| Python 编译检查 | 通过 |
| Python 依赖一致性 | `pip check` 通过 |
| SQLAlchemy/Pydantic 弃用警告 | 0 |
| 前端 ESLint | 0 error / 0 warning |
| 前端生产构建 | 通过 |
| 干净后端/前端容器构建 | 通过 |
| 容器 readiness（存储 + 生成模型 + Embedding + Task Worker） | 通过 |

前端已完成路由级代码分割和 `echarts/core` 按需注册。2026-07-20 最终生产构建中 ECharts
vendor chunk 为 690.01 kB（gzip 235.05 kB），较原始全量 chunk 减少约 39%；仍高于 500 kB 提示线，
不能把“构建通过”等同于“前端性能达标”。

后端日常安装使用 `requirements-lock.txt` 中的 Python 3.12 传递依赖锁定；
`requirements.txt` 保留人工维护的顶层约束。根据官方发布兼容表，项目固定
Milvus 2.6.17 + PyMilvus 2.6.14。Compose 使用独立的 v2.6 etcd/MinIO/Milvus 数据卷，
不会用新服务端直接打开历史 2.3 存储；向量库由受审 Markdown 重建。

全语料 smoke 使用确定性非语义向量，验证真实解析、分块、Milvus schema/
索引、写入、数量对账和检索链路，不用它声称语义检索质量。

## 仓库边界

以下内容已从 Git 候选文件中排除：

- 后端与前端 `.env`；
- Python 虚拟环境、Node 依赖和前端构建产物；
- `data/evaluation-private` 中的 80 题主集和 test/hidden 答案；
- 历史上暴露 test/hidden 标签的聚合数据与标签派生报告；
- 可由受审来源注册表重新下载的 `data/semiconductor_sources/raw` 原始二进制文件；
- 与半导体演示闭环无关的历史研报、Excel 和截图样本；
- 本地数据库、覆盖率和测试缓存。

原始 PDF 不进 Git 不代表数据来源不可追溯：版本库保留来源 URL、许可信息、
内容哈希、本地路径和处理状态，下载后通过哈希校验再进入解析流程。

仓库已公开并采用 MIT License；代码归属与 5 项公开前人工复核已于 2026-07-18
由项目负责人确认。原始 PDF、私有答案、密钥和运行时数据继续保持 Git 忽略。
