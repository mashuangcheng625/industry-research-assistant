# Milvus 2.6 重建运行手册

更新日期：2026-07-17

## 目标与边界

- 服务端固定 Milvus 2.6.17，Python SDK 固定 PyMilvus 2.6.14。
- v2.6 使用 `etcd_v26_data` / `minio_v26_data` / `milvus_v26_data` 独立卷。
- 不让 2.6 服务端直接打开 2.3 数据卷；向量索引由受审 Markdown 全量重建。
- PostgreSQL 中的用户、知识库和文档元数据保留，入库时使用 `--force` 更新状态。

## 切换前证据

2026-07-17 对旧 Milvus 2.3.3 运行库的只读审计：

| Collection | 切片数 |
| --- | ---: |
| `kb_semiconductor_chip_design_eda_ip` | 3397 |
| `kb_semiconductor_materials_equipment` | 627 |
| `kb_semiconductor_packaging_testing` | 679 |
| `kb_semiconductor_process` | 692 |
| 合计 | 5395 |

这些数字是旧库快照，不是新库必须完全相等的金标。规范化、切片或语料
发生合理变更时，数量可以变，但必须能由新入库报告解释。

## 前置闸门

```bash
make check-backend-deps
make test-backend
make validate-compose
make validate-sources
make validate-eval
```

无密钥运行全语料解析、分块、Milvus Lite 写入、数量对账与检索 smoke：

```bash
make smoke-ingest-lite
```

smoke 使用确定性非语义测试向量，所以它验证基础设施链路，不代表检索质量。
WSL 下 Milvus Lite 依赖 Unix socket，脚本默认使用 Linux `/tmp`；如需替换，
设置为支持 Unix socket 的 `MILVUS_LITE_TEMP_DIR`，不要指向 `/mnt/c`。

必须看到：

- PyMilvus 版本校验通过；
- 62 条测试通过，其中 Milvus Lite 完成真实建库、写入和检索；
- 资料治理为 17 个候选、15 个获批全文、2 个仅元数据、0 错误；
- 全语料 smoke 为 15 份资料、36 个文档领域任务、5256 切片、4/4 库对账通过；
- 40 题有标签开发集语料契约为 0 错误，40 题 test/hidden 公开文件为 0 标签泄漏。

## 拉取与切换

```bash
docker compose pull etcd minio milvus
docker compose up -d etcd minio milvus
docker compose ps etcd minio milvus
```

如果镜像拉取失败，不要执行数据卷清理。先确认旧容器仍健康，再重试下载。

等待就绪：

```bash
curl --fail http://localhost:9091/healthz
```

## 全量重建

```bash
cd backend
PYTHONPATH=app ../.venv/bin/python app/scripts/migrate_document_metadata.py
PYTHONPATH=app ../.venv/bin/python app/scripts/ingest_approved_sources.py \
  --username source_pipeline \
  --queue ../data/semiconductor_sources/review/candidates-v2.jsonl \
  --force \
  --chunk-size 1200
```

入库必须使用 `candidates-v2.jsonl`：12 份 PDF 指向 `normalized-v2`，3 份 OpenROAD
Markdown 继续指向 `normalized`。路径相对于 `data/semiconductor_sources` 解析。

## 重建后验收

1. 运行 `make audit-ingestion`，对账 PostgreSQL 状态/切片数与四个 collection 的
   实体数、文档数、重复 chunk ID、重复 `(doc_id, chunk_index)` 和异常 `doc_id`。
2. 查验 PostgreSQL 中每个获批文档均为 `completed`，不存在长期 `processing`。
3. 先运行 20 题 regression 检索，再运行 development/test；不根据 hidden 失败调参。
4. 运行端到端回答评测，分别报告检索命中、引用命中、拒答、平均延迟和 P95。
5. 新报告写入 `reports/`，并在 README 中用报告文件名限定口径。

## 2026-07-17 未完成项

Docker Hub 连续出现 TLS handshake timeout，Quay 返回 EOF，Milvus、MinIO 和 etcd
新镜像未全部拉取完成。旧 2.3.3 容器仍健康运行，未切换数据卷，未执行全量重建。

旧库读取审计还显示：PostgreSQL 对四库登记的切片数是 `3258 / 627 / 679 / 692`，
旧 Milvus 实体数是 `3397 / 627 / 679 / 692`。设计库多 139 块，所以切换前
`make audit-ingestion` 应当失败；这是需要全量重建的证据，不得手工改报告绕过。
