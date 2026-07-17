# 半导体真实公开资料管线

该管线将“发现资料”和“进入 RAG”分成两个阶段。只有白名单中标记为
`fulltext_allowed` 且审核状态为 `approved` 的文档，才会下载和生成
可入库 Markdown。

## 目录

- 资料源白名单：`backend/app/config/semiconductor_sources.yaml`
- 审核队列：`data/semiconductor_sources/review/candidates.jsonl`
- 人类可读报告：`data/semiconductor_sources/review/SUMMARY.md`
- 原始 PDF/Markdown：`data/semiconductor_sources/raw/`
- 待入库 Markdown：`data/semiconductor_sources/normalized/`

## 采集

在项目根目录执行：

```bash
cd backend
python app/scripts/collect_semiconductor_sources.py --download-approved
```

默认还会通过 Crossref 发现近年论文，但这些论文仅保存 DOI 和元数据。
如需完全可重现的白名单采集：

```bash
python app/scripts/collect_semiconductor_sources.py --offline --download-approved
```

审核队列中的本地文件路径相对于 `data/semiconductor_sources`保存，不依赖
某台机器的工作目录。仓库已有规范化 Markdown 时，采集器默认复用缓存；
如需从官方原始文件完整重建并重算 SHA-256，执行：

```bash
python app/scripts/collect_semiconductor_sources.py \
  --offline --download-approved --refresh-approved
```

## 入库

先执行幂等数据库迁移，再导入已批准资料：

```bash
cd backend
python app/scripts/migrate_document_metadata.py
python app/scripts/ingest_approved_sources.py \
  --username xiaoma_dev \
  --queue ../data/semiconductor_sources/review/candidates.jsonl
```

真实长文档默认使用 1200 字符切片，可通过 `--chunk-size` 调整。
Markdown 文档会按标题层级切分，并将“文档位置”标题路径写入每个切片。
检索默认返回主召回切片及其同文档相邻切片，避免只命中局部段落而
丢失上下文。可通过 `RAG_NEIGHBOR_WINDOW` 和 `RAG_MAX_NEIGHBOR_CHUNKS`
调整，或用 `RAG_NEIGHBOR_ENABLED=false` 关闭。
对包含多个专业概念的中文问题，检索器会使用可审计的领域词表生成最多
5 路查询，批量向量化后为每个子查询保留证据席位。该机制不调用生成模型，
可通过 `RAG_MULTI_QUERY_ENABLED=false` 关闭。

## 新增资料源的规则

1. 必须填写原始 HTTPS 来源、文档版本和日期。
2. 必须记录许可条款链接，不能以“可下载”替代“可处理全文”。
3. 公司新闻稿、年报和投资者文件必须标记为一手机构声明，不得伪装成中立结论。
4. 付费论文、SEMI/JEDEC/UCIe 受限规范默认只保存元数据和链接。
5. 更新文档时保留旧版本，使用 DOI、外部编号和 SHA-256 去重。

## 去哪里找语料

按下面的优先级采集，越靠前越适合作为报告中的核心事实依据：

1. 政府和国家实验室原始出版物：NIST CHIPS、NIST Technical Series、
   DOE/OSTI、NASA、EPA、USGS。优先选择带 DOI、报告编号、发布日期和
   官方 PDF 的材料。
2. 开放标准组织：RISC-V 等明确采用 CC-BY、Apache、BSD 等许可的规范。
   规范版本必须单独保存，不能只抓取“最新版本”入口。
3. 开源 EDA/IP 项目：OpenROAD、OpenTitan、lowRISC 等项目的官方仓库和
   文档。入库前必须固定 commit/tag，并保存仓库许可证；采集器支持精选的
   单文件 Markdown，但不会递归抓取整个仓库或自动跟随相对链接。
4. 开放获取论文：通过 Crossref、OpenAlex、Unpaywall 或 PubMed Central
   找到 DOI 和开放许可，再从出版机构或开放仓储下载全文。仅有 DOI 或摘要
   时只保存元数据。
5. 企业一手资料：设备/材料厂商技术白皮书、产品手册、年报和投资者材料。
   只能证明该机构自己的参数或观点，不能直接当作中立行业结论；权利不明确
   时只保存标题、日期和原始链接。

以下来源默认不能自动全文入库：SEMI、JEDEC、IEEE 付费标准、UCIe 需要
接受协议的规范、付费数据库、券商报告和来源不明的转载 PDF。它们可以进入
元数据索引，回答时引导用户访问原始页面，但不能绕过许可做本地全文库。

## 当前资料覆盖

- 审核候选：17 份。
- 获批公开全文：15 份。
- 仅元数据：2 份（UCIe 2.0、IEEE IRDS More Moore）。
- 2026-07-17 对运行中 Milvus 2.3.3 的实时审计为 5395 个切片：
  芯片设计 3397、材料设备 627、封装测试 679、晶圆制造 692。
- PostgreSQL 与 v2 可重现管道的应有数量为 5256：芯片设计 3258，其他三库
  与上述旧库相同。只读审计定位到旧设计库 `nist-ir-8577.md` 存在 138 个
  重复 `(doc_id, chunk_index)`，以及 1 个仅在实体统计中可见的差异。
- 无密钥全语料 Milvus Lite smoke 已对 15 份资料、36 个文档领域任务、5256 切片
  完成 4/4 库数量对账、0 重复 chunk ID 和 exact Top-1 基础设施探针。
- Milvus 2.6.17 使用独立数据卷，全量重建后必须重新导出计数和检索报告；
  不得沿用 5507 这一历史口径。
- 半导体四方向新增检索评测：4/4 通过。
- OpenROAD EDA 专项检索评测：3/3 通过（Top-5 主召回）。
- 四方向 20 题原始证据级基线：13/20；保留该报告用于消融对比。
- 多查询与证据覆盖精排后：20/20；正例 16/16，无证据拒绝 4/4，
  人工标注来源命中 16/16。
- 2026-07-16 历史评测报告中，本地 4B 模型端到端回答：20/20；
  平均 7.33 秒，P95 13.22 秒，
  核心金标文档引用 15/16。

上述评测值是特定语料、索引、模型与参数组合的历史运行结果，不是当前代码的
无条件性能承诺。只有重建后的新报告才能作为新基线。

20 题检索基线的运行方式：

```bash
cd backend
python app/scripts/evaluate_rag_retrieval.py \
  --cases ../sample-data/semiconductor_rag_eval_20.json \
  --top-k 5 \
  --output ../reports/semiconductor_rag_eval_20_baseline_2026-07-16.json
```

端到端回答评测（需先启动后端）：

```bash
cd backend
python app/scripts/evaluate_rag_answers.py \
  --cases ../sample-data/semiconductor_rag_eval_20.json \
  --model-mode local \
  --max-latency 90 \
  --output ../reports/semiconductor_rag_answers_20_local_final_2026-07-16.json
```
