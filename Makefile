PYTHON ?= .venv/bin/python
PIP_INDEX_URL ?= https://pypi.org/simple
API_URL ?= http://127.0.0.1:8000/chat/completion
MODEL_MODE ?= local
MAX_LATENCY ?= 20
ANSWER_REPORT ?= reports/semiconductor_rag_answers_regression_working.json
STRUCTURED_PORT ?= 8001
STRUCTURED_ANSWER_REPORT ?= reports/semiconductor_rag_answers_regression_structured_grounding_latest.json
SEMANTIC_PORT ?= 8002
SEMANTIC_ANSWER_REPORT ?= reports/semiconductor_rag_answers_regression_semantic_entailment_latest.json
PROMETHEUS_IMAGE ?= prom/prometheus:v3.13.1
LOAD_CONCURRENCY ?= 2
LOAD_REQUESTS ?= 8
LOAD_WARMUP ?= 1
LOAD_MAX_P95 ?= 30
LOAD_MIN_QUALITY_PASS_RATE ?= 1
LOAD_REPORT ?= reports/chat_load_regression_latest.json
MULTI_SOURCE_FIXTURE ?= sample-data/multi_source_advanced_packaging_fixture.json
MULTI_SOURCE_EVAL ?= sample-data/multi_source_advanced_packaging_eval.json
MULTI_SOURCE_REPORT ?= reports/multi_source_advanced_packaging_latest.json

.PHONY: setup-backend test-backend test-backend-unit test-backend-integration test-evidence-contract check-backend-deps check-backend-import lint-frontend build-frontend build-images validate-compose validate-observability validate-sources validate-baseline smoke-ingest-lite audit-ingestion ablate-retrieval-development evaluate-answers-regression demo-rag load-test-chat stress-context-budget run-backend-structured evaluate-answers-regression-structured run-backend-semantic evaluate-answers-regression-semantic build-eval-public validate-eval validate-eval-private evaluate-multi-source check

setup-backend:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install --index-url $(PIP_INDEX_URL) -r backend/requirements-lock.txt

test-backend:
	cd backend && PYTHONPATH=app timeout 300s ../$(PYTHON) -m pytest -q -W error::DeprecationWarning

test-backend-unit:
	cd backend && PYTHONPATH=app timeout 240s ../$(PYTHON) -m pytest -q -m "not integration" -W error::DeprecationWarning

test-backend-integration:
	cd backend && PYTHONPATH=app timeout 120s ../$(PYTHON) -m pytest -q -m integration -W error::DeprecationWarning

test-evidence-contract:
	cd backend && PYTHONPATH=app ../$(PYTHON) -m pytest test/test_evidence_contract.py -v

check-backend-deps:
	$(PYTHON) -m pip check
	$(PYTHON) -c "import pymilvus; assert pymilvus.__version__ == '2.6.14'"

check-backend-import:
	PYTHONPATH=backend/app $(PYTHON) -W error::DeprecationWarning -c \
		"import app_main; paths = {getattr(route, 'path', '') for route in app_main.app.routes}; assert {'/health/live', '/health/ready', '/metrics'} <= paths"

lint-frontend:
	cd frontend && npm run lint

build-frontend:
	cd frontend && npm run build

build-images:
	docker compose --profile app build backend frontend

validate-compose:
	docker compose config --quiet

validate-observability:
	docker run --rm --entrypoint /bin/promtool \
		-v "$(CURDIR)/docker/prometheus:/etc/prometheus:ro" \
		$(PROMETHEUS_IMAGE) check config /etc/prometheus/prometheus.yml
	docker run --rm --entrypoint /bin/promtool \
		-v "$(CURDIR)/docker/prometheus:/etc/prometheus:ro" \
		$(PROMETHEUS_IMAGE) check rules /etc/prometheus/alerts.yml

validate-sources:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/validate_source_manifest.py \
		data/semiconductor_sources/review/candidates-v2.jsonl \
		--min-approved 15

validate-baseline:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/validate_baseline_manifest.py

smoke-ingest-lite:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/smoke_ingest_corpus_lite.py \
		--queue data/semiconductor_sources/review/candidates-v2.jsonl \
		--chunk-size 1200

audit-ingestion:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/audit_ingestion_consistency.py \
		--username source_pipeline

ablate-retrieval-development:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/run_retrieval_ablation.py \
		--cases ../sample-data/semiconductor_rag_eval_development.json \
		--output-dir ../reports/retrieval_ablation_development_2026-07-17 \
		--top-k 3

evaluate-answers-regression:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/evaluate_rag_answers.py \
		--cases ../sample-data/semiconductor_rag_eval_regression.json \
		--api-url $(API_URL) --model-mode $(MODEL_MODE) \
		--timeout 120 --max-latency $(MAX_LATENCY) \
		--output ../$(ANSWER_REPORT)

demo-rag:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/evaluate_rag_answers.py \
		--cases ../sample-data/semiconductor_rag_eval_regression.json \
		--api-url $(API_URL) --model-mode $(MODEL_MODE) \
		--timeout 120 --max-latency $(MAX_LATENCY) \
		--case-id design-flow-001 --case-id packaging-ucie-018 \
		--case-id packaging-negative-020 \
		--output ../reports/demo_rag_latest.json

load-test-chat:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/load_test_chat.py \
		--cases ../sample-data/semiconductor_rag_eval_regression.json \
		--api-url $(API_URL) --model-mode $(MODEL_MODE) \
		--concurrency $(LOAD_CONCURRENCY) --requests $(LOAD_REQUESTS) \
		--warmup $(LOAD_WARMUP) --timeout 180 --max-latency $(MAX_LATENCY) \
		--max-p95 $(LOAD_MAX_P95) --min-quality-pass-rate $(LOAD_MIN_QUALITY_PASS_RATE) \
		--output ../$(LOAD_REPORT)

stress-context-budget:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/stress_context_budget.py \
		--documents 200 --repetitions-per-document 500 --budget 6000 \
		--output ../reports/context_budget_stress_2026-07-17.json

run-backend-structured:
	cd backend && RAG_STRUCTURED_GROUNDING_ENABLED=true PYTHONPATH=app ../$(PYTHON) \
		-m uvicorn app_main:app --host 127.0.0.1 --port $(STRUCTURED_PORT)

evaluate-answers-regression-structured:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/evaluate_rag_answers.py \
		--cases ../sample-data/semiconductor_rag_eval_regression.json \
		--api-url http://127.0.0.1:$(STRUCTURED_PORT)/chat/completion \
		--model-mode $(MODEL_MODE) --timeout 120 --max-latency $(MAX_LATENCY) \
		--output ../$(STRUCTURED_ANSWER_REPORT)

run-backend-semantic:
	cd backend && RAG_STRUCTURED_GROUNDING_ENABLED=true \
		RAG_SEMANTIC_ENTAILMENT_ENABLED=true PYTHONPATH=app ../$(PYTHON) \
		-m uvicorn app_main:app --host 127.0.0.1 --port $(SEMANTIC_PORT)

evaluate-answers-regression-semantic:
	cd backend && PYTHONPATH=app ../$(PYTHON) app/scripts/evaluate_rag_answers.py \
		--cases ../sample-data/semiconductor_rag_eval_regression.json \
		--api-url http://127.0.0.1:$(SEMANTIC_PORT)/chat/completion \
		--model-mode $(MODEL_MODE) --timeout 180 --max-latency $(MAX_LATENCY) \
		--output ../$(SEMANTIC_ANSWER_REPORT)

validate-eval:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/validate_rag_eval_dataset.py \
		sample-data/semiconductor_rag_eval_regression.json \
		sample-data/semiconductor_rag_eval_development.json \
		--min-cases 40 --require-balanced \
		--corpus-dir data/semiconductor_sources/normalized-v2 \
		--corpus-dir data/semiconductor_sources/normalized
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/validate_rag_eval_dataset.py \
		sample-data/semiconductor_rag_eval_test_questions.json \
		sample-data/semiconductor_rag_eval_hidden_questions.json \
		--questions-only --min-cases 40 --require-balanced

build-eval-public:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/build_semiconductor_eval_80.py

validate-eval-private:
	test -f data/evaluation-private/semiconductor_rag_eval_master.json
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/validate_rag_eval_dataset.py \
		data/evaluation-private/semiconductor_rag_eval_master.json \
		--min-cases 80 --require-balanced \
		--corpus-dir data/semiconductor_sources/normalized-v2 \
		--corpus-dir data/semiconductor_sources/normalized

check: check-backend-deps test-backend-unit test-backend-integration test-evidence-contract check-backend-import lint-frontend build-frontend validate-compose validate-sources validate-eval validate-baseline evaluate-multi-source

evaluate-multi-source:
	PYTHONPATH=backend/app $(PYTHON) backend/app/scripts/evaluate_multi_source_joint.py
