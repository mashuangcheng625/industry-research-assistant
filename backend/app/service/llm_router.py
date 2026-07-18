"""聊天生成模型路由：本地、云端与自动选择。"""
import os
from dataclasses import dataclass
from typing import Optional


VALID_MODEL_MODES = {"local", "cloud", "auto"}


class ModelRoutingError(ValueError):
    """请求的模型路由不可用。"""


@dataclass(frozen=True)
class LLMEndpoint:
    mode: str
    provider: str
    api_key: str
    base_url: str
    model: str

    def public_info(self) -> dict:
        """返回可以安全暴露给前端的模型信息。

        API Key 和 Base URL 只用于后端请求，避免泄露密钥或内部服务拓扑。
        """
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
        }


def _local_endpoint() -> LLMEndpoint:
    return LLMEndpoint(
        mode="local",
        provider=os.getenv("LOCAL_LLM_PROVIDER", "ollama"),
        api_key=os.getenv("LOCAL_LLM_API_KEY", "ollama"),
        base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
        model=os.getenv("LOCAL_LLM_MODEL", "qwen3:0.6b"),
    )


def _cloud_endpoint() -> LLMEndpoint:
    return LLMEndpoint(
        mode="cloud",
        provider=os.getenv("CLOUD_LLM_PROVIDER", "openai-compatible"),
        api_key=os.getenv("CLOUD_LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", ""),
        base_url=os.getenv("CLOUD_LLM_BASE_URL", ""),
        model=os.getenv("CLOUD_LLM_MODEL", ""),
    )


def is_cloud_configured() -> bool:
    endpoint = _cloud_endpoint()
    return bool(endpoint.api_key and endpoint.base_url and endpoint.model)


def resolve_llm_endpoint(requested_mode: Optional[str] = None) -> LLMEndpoint:
    """解析请求级模式；auto 仅在云端配置完整时选云端。"""
    mode = (requested_mode or os.getenv("MODEL_ROUTING_MODE", "local")).lower()
    if mode not in VALID_MODEL_MODES:
        raise ModelRoutingError(f"不支持的模型模式: {mode}")
    if mode == "local":
        return _local_endpoint()
    if mode == "cloud":
        if not is_cloud_configured():
            raise ModelRoutingError("云端模型未完整配置")
        return _cloud_endpoint()
    return _cloud_endpoint() if is_cloud_configured() else _local_endpoint()


def get_model_routing_status() -> dict:
    """返回不含密钥的模型路由状态。"""
    local = _local_endpoint()
    cloud = _cloud_endpoint()
    default_mode = os.getenv("MODEL_ROUTING_MODE", "local").lower()
    resolved = resolve_llm_endpoint(default_mode)
    return {
        "default_mode": default_mode,
        "resolved_mode": resolved.mode,
        "local": {
            **local.public_info(),
            "configured": bool(local.base_url and local.model),
        },
        "cloud": {
            **cloud.public_info(),
            "configured": is_cloud_configured(),
        },
        "available_modes": sorted(VALID_MODEL_MODES),
    }
