"""OpenAI-compatible cloud/local Embedding generation."""

import os
import time
from typing import List, Optional
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()


def generate_embedding(
    text: str | List[str],
    api_key: str = None,
    base_url: str = None,
    model_name: str = None,
    dimensions: int = None,
    encoding_format: str = "float",
    max_batch_size: int | None = None,
    max_retries: int | None = None,
) -> Optional[List[float] | List[List[float]]]:
    """
    生成文本的向量嵌入（使用阿里 text-embedding-v4）

    Args:
        text: 单个文本或文本列表
        api_key: API密钥（默认从环境变量获取）
        base_url: API基础URL（默认从环境变量获取）
        model_name: 模型名称
        dimensions: 向量维度（默认1024）
        encoding_format: 编码格式
        max_batch_size: 最大批量大小（阿里云限制为10）

    Returns:
        单个文本时返回向量，文本列表时返回向量列表
    """
    api_key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    base_url = (
        base_url
        or os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )
    model_name = model_name or os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    dimensions = dimensions or int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
    max_batch_size = max_batch_size or int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
    max_batch_size = max(1, max_batch_size)
    max_retries = (
        int(os.getenv("EMBEDDING_MAX_RETRIES", "2"))
        if max_retries is None else max(0, max_retries)
    )

    if not api_key:
        print("错误: 缺少 EMBEDDING_API_KEY 或 DASHSCOPE_API_KEY 环境变量")
        return None

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"初始化 OpenAI 客户端失败: {e}")
        return None

    # 单个文本
    if isinstance(text, str):
        try:
            completion = client.embeddings.create(
                model=model_name,
                input=text,
                dimensions=dimensions,
                encoding_format=encoding_format
            )
            return completion.data[0].embedding
        except Exception as e:
            print(f"Embedding 请求失败: {e}")
            return None

    # 文本列表 - 分批处理
    if isinstance(text, list):
        all_embeddings = []

        total_batches = (len(text) + max_batch_size - 1) // max_batch_size
        progress_every = max(1, int(os.getenv("EMBEDDING_PROGRESS_EVERY_BATCHES", "10")))
        for i in range(0, len(text), max_batch_size):
            batch = text[i:i + max_batch_size]
            batch_number = i // max_batch_size + 1
            for attempt in range(max_retries + 1):
                try:
                    completion = client.embeddings.create(
                        model=model_name,
                        input=batch,
                        dimensions=dimensions,
                        encoding_format=encoding_format
                    )
                    batch_embeddings = [item.embedding for item in completion.data]
                    if len(batch_embeddings) != len(batch):
                        raise ValueError(
                            f"返回数量 {len(batch_embeddings)}，请求数量 {len(batch)}"
                        )
                    all_embeddings.extend(batch_embeddings)
                    break
                except Exception as e:
                    if attempt >= max_retries:
                        print(
                            f"Embedding 批量请求失败 "
                            f"(batch {batch_number}/{total_batches}): {e}"
                        )
                        all_embeddings.extend([None] * len(batch))
                    else:
                        delay = min(2 ** attempt, 4)
                        print(
                            f"Embedding 批次 {batch_number}/{total_batches} "
                            f"失败，第 {attempt + 1} 次重试，等待 {delay}s"
                        )
                        time.sleep(delay)
            if batch_number % progress_every == 0 or batch_number == total_batches:
                print(f"Embedding 进度: {batch_number}/{total_batches} 批")

        return all_embeddings

    return None
