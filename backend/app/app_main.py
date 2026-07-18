from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from dotenv import load_dotenv
import logging
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# 加载环境变量
from pathlib import Path as _Path
_env_file = _Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=str(_env_file))

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from router import document_router, search_router, chat_router, research_router
from router.auth_router import router as auth_router
from router.session_router import router as session_router
from router.knowledge_router import router as knowledge_router
from router.attachment_router import router as attachment_router
from router.memory_router import router as memory_router
from router.database_router import router as database_router
from router.news_router import router as news_router
from core.database import engine, Base
from core.health import check_readiness
from core.runtime_config import cors_origins, env_bool
from core.security import validate_security_config
# 导入所有模型以确保它们被注册
from models import (
    User, ChatSession, ChatMessage, ChatAttachment, LongTermMemory,
    KnowledgeBase, Document, IndustryStats, CompanyData, PolicyData,
    ResearchCheckpoint, IndustryNews, BiddingInfo, NewsCollectionTask
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("应用启动中...")

    validate_security_config()

    if env_bool("AUTO_CREATE_TABLES", True):
        Base.metadata.create_all(bind=engine)

    # 初始化定时任务调度器并检查数据
    if env_bool("ENABLE_SCHEDULER", True):
        try:
            from service.scheduler_service import init_scheduler_and_check_data
            await init_scheduler_and_check_data()
            logger.info("定时任务调度器启动成功")
        except Exception as e:
            logger.error(f"定时任务调度器启动失败: {e}")

    yield

    # 关闭时执行
    logger.info("应用关闭中...")
    if env_bool("ENABLE_SCHEDULER", True):
        try:
            from service.scheduler_service import get_scheduler_service
            scheduler = get_scheduler_service()
            scheduler.stop()
        except Exception as e:
            logger.error(f"定时任务调度器关闭失败: {e}")


app = FastAPI(
    title="证据驱动行业研究平台 API",
    description="统一知识库、产业数据与公开情报，并以半导体全产业链为垂直示范的证据驱动研究系统",
    version="2.0.0",
    lifespan=lifespan
)

allowed_origins = cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(knowledge_router)
app.include_router(attachment_router)
app.include_router(memory_router)
app.include_router(database_router)
app.include_router(document_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(research_router)
app.include_router(news_router)

@app.get("/hello")
async def hello_world():
    """
    Simple hello world endpoint for network verification
    """
    return {
        "status": "success",
        "message": "Hello World! The API is working correctly."
    }


@app.get("/health/live", tags=["health"])
async def liveness():
    """Process-level probe; it never checks external dependencies."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness():
    """Dependency-level probe for PostgreSQL, Redis, and Milvus."""
    result = await run_in_threadpool(check_readiness)
    return JSONResponse(result, status_code=200 if result["status"] == "ready" else 503)


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Expose process-local Prometheus metrics without application data labels."""
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
