# Backend

FastAPI 后端提供知识库、Hybrid RAG、多源证据、Text2SQL 和研究 Agent。
项目唯一受支持的完整启动入口是仓库根目录的 `start-services.sh` 和
`docker-compose.yml`。

## 开发环境

在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
cp backend/.env.example backend/.env
```

只将真实密钥写入 Git 忽略的 `backend/.env`。不要把密钥写入本文档、
Compose 或 shell 历史。

宿主机启动后端：

```bash
cd backend
PYTHONPATH=app ../.venv/bin/python -m uvicorn app_main:app \
  --host 127.0.0.1 --port 8000
```

完整容器演示：

```bash
./start-services.sh app
```

服务启动后可访问：

- OpenAPI：<http://localhost:8000/docs>
- Liveness：<http://localhost:8000/health/live>
- Readiness：<http://localhost:8000/health/ready>
- Metrics：<http://localhost:8000/metrics>

## 验证

```bash
make check
```

资料下载、入库、演示用户和故障处理以根目录
[`README.md`](../README.md) 与 [`docs/DEPLOYMENT_AND_DEMO.md`](../docs/DEPLOYMENT_AND_DEMO.md)
为准，不再维护第二套 Compose 或依赖清单。
