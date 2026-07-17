# PDF 结构化入库 v2

旧链路直接保存 `pdftotext -layout` 输出，双栏页面会把左右两栏逐行拼接，并保留页眉、页码、
目录点线和换行断词。v2 使用内容流顺序抽取，并执行确定性的页边噪声清理、软连字符修复、
列表合并和保守标题识别，不调用模型补写原文。

## 旁路生成

```bash
PYTHONPATH=backend/app python backend/app/scripts/renormalize_pdf_sources.py \
  --queue data/semiconductor_sources/review/candidates.jsonl \
  --output-queue data/semiconductor_sources/review/candidates-v2.jsonl \
  --report reports/pdf_normalization_v2_2026-07-17.json
```

命令写入 `normalized-v2`，不会覆盖 raw PDF、v1 Markdown 或原审核队列。必须先查看质量报告并
抽样比对正文顺序，再使用新队列强制重建索引。

## 可恢复入库

完整替换：

```bash
PYTHONPATH=backend/app python backend/app/scripts/ingest_approved_sources.py \
  --username USERNAME --queue data/semiconductor_sources/review/candidates-v2.jsonl \
  --force --chunk-size 1200
```

中断后只恢复未完成文档：

```bash
PYTHONPATH=backend/app python backend/app/scripts/ingest_approved_sources.py \
  --username USERNAME --queue data/semiconductor_sources/review/candidates-v2.jsonl \
  --retry-incomplete --chunk-size 1200
```

嵌入批量大小、重试次数和进度频率分别由 `EMBEDDING_BATCH_SIZE`、
`EMBEDDING_MAX_RETRIES`、`EMBEDDING_PROGRESS_EVERY_BATCHES` 控制。

