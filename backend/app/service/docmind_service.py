"""DocMind 文档智能解析服务"""
import os
import re
import time
import hashlib
from typing import List, Dict, Any, Optional, Callable
from alibabacloud_docmind_api20220711.client import Client as DocMindClient
from alibabacloud_docmind_api20220711 import models as docmind_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from service.embedding_service import generate_embedding
from service.embedding_router import (
    collection_name_for_route,
    routes_for_ingestion,
)
from service.milvus_service import get_milvus_service, lexical_collection_name


LOCAL_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".py", ".js", ".ts",
}


def extract_text_locally(file_path: str, file_name: str) -> Optional[str]:
    """Parse plain-text formats locally so basic RAG does not require DocMind."""
    extension = os.path.splitext(file_name)[1].lower()
    if extension not in LOCAL_TEXT_EXTENSIONS:
        return None

    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


class DocMindService:
    """DocMind 文档解析服务"""

    def __init__(self):
        self.access_key_id = os.getenv("DOCMIND_ACCESS_KEY_ID")
        self.access_key_secret = os.getenv("DOCMIND_ACCESS_KEY_SECRET")
        self.endpoint = "docmind-api.cn-hangzhou.aliyuncs.com"
        self.client = self._create_client()

    def _create_client(self) -> DocMindClient:
        """创建 DocMind 客户端"""
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
        )
        config.endpoint = self.endpoint
        return DocMindClient(config)

    def submit_job(self, file_path: str, file_name: str) -> Optional[str]:
        """
        提交文档解析任务

        Args:
            file_path: 文件路径
            file_name: 文件名

        Returns:
            任务 ID，失败返回 None
        """
        try:
            request = docmind_models.SubmitDocParserJobAdvanceRequest(
                file_url_object=open(file_path, "rb"),
                file_name=file_name,
                file_name_extension=file_name.split('.')[-1] if '.' in file_name else None,
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.submit_doc_parser_job_advance(request, runtime)

            if response.body and response.body.data:
                task_id = response.body.data.id
                print(f"任务已提交，任务ID: {task_id}")
                return task_id
            return None

        except Exception as e:
            print(f"提交任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def query_status(self, task_id: str) -> Optional[Dict]:
        """
        查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        try:
            request = docmind_models.QueryDocParserStatusRequest(id=task_id)
            response = self.client.query_doc_parser_status(request)
            if response.body and response.body.data:
                return response.body.data.to_map()
            return None
        except Exception as e:
            print(f"查询状态失败: {e}")
            return None

    def wait_for_completion(self, task_id: str, poll_interval: int = 5, max_wait: int = 300) -> bool:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）

        Returns:
            任务是否成功完成
        """
        print("开始轮询任务状态...")
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_data = self.query_status(task_id)
            if not status_data:
                print("查询状态失败")
                return False

            status = status_data.get('Status', '').lower()
            print(f"当前状态: {status}")

            if status == 'success':
                print("任务已成功完成")
                return True
            elif status == 'failed':
                print("任务执行失败")
                return False
            else:
                # 任务仍在处理中
                time.sleep(poll_interval)

        print("等待超时")
        return False

    def get_result(self, task_id: str, layout_num: int = 0, layout_step_size: int = 10) -> Optional[Any]:
        """
        获取文档解析结果（支持增量获取）

        Args:
            task_id: 任务ID
            layout_num: 起始布局编号
            layout_step_size: 步长

        Returns:
            解析结果
        """
        try:
            request = docmind_models.GetDocParserResultRequest(
                id=task_id,
                layout_step_size=layout_step_size,
                layout_num=layout_num
            )
            response = self.client.get_doc_parser_result(request)
            return response.body.data if response.body.data else None
        except Exception as e:
            print(f"获取结果失败: {e}")
            return None

    def collect_all_results(self, task_id: str, layout_step_size: int = 10) -> str:
        """
        收集所有解析结果

        Args:
            task_id: 任务ID
            layout_step_size: 步长

        Returns:
            完整的文本内容
        """
        all_text = ""
        layout_num = 0

        while True:
            result_data = self.get_result(task_id, layout_num, layout_step_size)
            if not result_data:
                break

            # 尝试获取 layouts
            layouts = None
            if hasattr(result_data, 'layouts'):
                layouts = result_data.layouts
            elif isinstance(result_data, dict):
                layouts = result_data.get('layouts', [])

            if not layouts:
                break

            print(f"获取到 {len(layouts)} 个布局块 (从 {layout_num} 开始)")

            # 提取文本
            for layout in layouts:
                # 优先使用 markdownContent
                if hasattr(layout, 'markdown_content') and layout.markdown_content:
                    all_text += layout.markdown_content + "\n"
                elif hasattr(layout, 'markdownContent') and layout.markdownContent:
                    all_text += layout.markdownContent + "\n"
                elif isinstance(layout, dict):
                    if layout.get('markdownContent'):
                        all_text += layout['markdownContent'] + "\n"
                    elif layout.get('text'):
                        all_text += layout['text'] + "\n"
                # 尝试 text 属性
                elif hasattr(layout, 'text') and layout.text:
                    all_text += layout.text + "\n"

            # 更新下次获取的起始位置
            layout_num += len(layouts)

            # 如果获取到的数量小于步长，说明已经获取完所有内容
            if len(layouts) < layout_step_size:
                break

        return all_text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    将文本切分成块

    Args:
        text: 原始文本
        chunk_size: 每块大小
        overlap: 重叠大小

    Returns:
        文本块列表
    """
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # 尝试在句子边界切分
        if end < len(text):
            for sep in ['。', '！', '？', '.', '!', '?', '\n']:
                last_sep = chunk.rfind(sep)
                if last_sep > chunk_size // 2:
                    chunk = chunk[:last_sep + 1]
                    end = start + last_sep + 1
                    break

        if chunk.strip():
            chunks.append(chunk.strip())

        next_start = max(end - overlap, start + 1)

        # 重叠区不从英文单词或中文分句中间开始。前一个切片已
        # 覆盖这段内容，因此可以向后移动到最近的可读边界，不会丢失原文。
        boundary_end = min(len(text), end, next_start + max(overlap * 2, 100))
        boundary_found = False
        for boundary_index in range(next_start, boundary_end):
            if text[boundary_index] in "。！？\n；;，,":
                candidate = boundary_index + 1
                while candidate < len(text) and text[candidate].isspace():
                    candidate += 1
                if candidate < end:
                    next_start = candidate
                    boundary_found = True
                    break

        if not boundary_found:
            while (
                next_start > start + 1
                and next_start < len(text)
                and text[next_start - 1].isascii()
                and text[next_start - 1].isalnum()
                and text[next_start].isascii()
                and text[next_start].isalnum()
            ):
                next_start -= 1

        start = next_start

    return chunks


MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def chunk_markdown(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """按 Markdown 标题分段，并为每个切片保留标题路径。"""
    if not text:
        return []

    sections: List[tuple[list[str], str]] = []
    heading_stack: list[str] = []
    body_lines: list[str] = []

    def flush_section() -> None:
        body = "\n".join(body_lines).strip()
        if body:
            sections.append((heading_stack.copy(), body))

    for line in text.splitlines():
        match = MARKDOWN_HEADING_PATTERN.match(line)
        if not match:
            body_lines.append(line)
            continue

        flush_section()
        body_lines = []
        level = len(match.group(1))
        title = match.group(2).strip()
        heading_stack = heading_stack[:level - 1]
        while len(heading_stack) < level - 1:
            heading_stack.append("")
        heading_stack.append(title)

    flush_section()

    chunks: List[str] = []
    for headings, body in sections:
        breadcrumb = " > ".join(heading for heading in headings if heading)
        prefix = f"文档位置：{breadcrumb}" if breadcrumb else ""
        body_chunk_size = max(200, chunk_size - len(prefix) - 2)
        for body_chunk in chunk_text(body, chunk_size=body_chunk_size, overlap=overlap):
            chunks.append(f"{prefix}\n\n{body_chunk}" if prefix else body_chunk)
    return chunks


def process_document_with_docmind(
    file_path: str,
    file_name: str,
    index_name: str,
    chunk_size: int = 500,
    embedding_fn: Callable[[List[str]], List[List[float]]] | None = None,
    milvus_service: Any | None = None,
) -> Dict[str, Any]:
    """
    使用 DocMind 处理文档

    Args:
        file_path: 文件路径
        file_name: 文件名
        index_name: ES 索引名
        chunk_size: 切片大小

    Returns:
        处理结果
    """
    result = {
        "success": False,
        "message": "",
        "document_count": 0,
    }

    try:
        print(f"开始处理文档: {file_name}")

        # 1. 文本类文件优先本地解析；复杂版式文件才使用可选的 DocMind。
        text = extract_text_locally(file_path, file_name)
        if text is not None:
            print("使用本地文本解析器")
        else:
            if not os.getenv("DOCMIND_ACCESS_KEY_ID") or not os.getenv("DOCMIND_ACCESS_KEY_SECRET"):
                result["message"] = (
                    "当前文件类型需要 DocMind，或请先转换为 txt/markdown/csv/json 等本地支持格式"
                )
                print(result["message"])
                return result

            service = DocMindService()
            task_id = service.submit_job(file_path, file_name)

            if not task_id:
                result["message"] = "文档提交失败"
                print(result["message"])
                return result

            if not service.wait_for_completion(task_id):
                result["message"] = "文档解析任务失败或超时"
                print(result["message"])
                return result

            print("开始收集解析结果...")
            text = service.collect_all_results(task_id)

        if not text or not text.strip():
            result["message"] = "文档内容为空"
            print(result["message"])
            return result

        print(f"解析到文本长度: {len(text)}")

        # 4. 文本切分
        if os.path.splitext(file_name)[1].lower() == ".md":
            chunks = chunk_markdown(text, chunk_size=chunk_size)
        else:
            chunks = chunk_text(text, chunk_size=chunk_size)

        if not chunks:
            result["message"] = "文档切分失败"
            print(result["message"])
            return result

        print(f"文档切分完成，共 {len(chunks)} 个切片")

        # 5. 为所有路由生成向量。测试注入 embedding_fn 时保持单索引兼容。
        routes = routes_for_ingestion() if embedding_fn is None else ()
        doc_id = hashlib.md5(file_name.encode()).hexdigest()
        milvus = milvus_service or get_milvus_service()
        inserted_routes: list[str] = []
        lexical_documents: list[dict[str, Any]] = []

        if embedding_fn is not None:
            route_jobs = [(None, index_name, embedding_fn(chunks))]
        else:
            route_jobs = []
            for route in routes:
                print(f"开始生成 {route.name} 向量: {route.model}")
                embeddings = generate_embedding(
                    chunks,
                    api_key=route.api_key,
                    base_url=route.base_url,
                    model_name=route.model,
                    dimensions=route.dimensions,
                )
                route_jobs.append((
                    route,
                    collection_name_for_route(index_name, route),
                    embeddings,
                ))

        for route, target_collection, embeddings in route_jobs:
            if not embeddings or len(embeddings) != len(chunks):
                raise RuntimeError(
                    f"{getattr(route, 'name', 'legacy')} 向量生成失败或数量不匹配"
                )
            if any(embedding is None for embedding in embeddings):
                failed_count = sum(embedding is None for embedding in embeddings)
                raise RuntimeError(
                    f"{getattr(route, 'name', 'legacy')} 有 {failed_count} 个切片向量生成失败"
                )

            documents = []
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = hashlib.md5(
                    f"{file_name}_{index}_{chunk[:50]}".encode()
                ).hexdigest()
                documents.append({
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "kb_id": index_name,
                    "filename": file_name,
                    "content": chunk,
                    "chunk_index": index,
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest(),
                    "embedding_provider": getattr(route, "provider", "legacy"),
                    "embedding_model": getattr(route, "model", "legacy"),
                    "embedding_version": getattr(route, "version", "legacy"),
                    "vector": embedding,
                })
            print(f"开始插入 Milvus，集合: {target_collection}")
            milvus.insert_documents(target_collection, documents)
            inserted_routes.append(getattr(route, "name", "legacy"))
            if not lexical_documents:
                lexical_documents = [
                    {key: value for key, value in document.items() if key != "vector"}
                    for document in documents
                ]

        lexical_target = None
        if (
            embedding_fn is None
            and os.getenv("RAG_LEXICAL_BACKEND", "auto").strip().lower() != "scan"
        ):
            lexical_target = lexical_collection_name(index_name)
            print(f"开始写入 Milvus BM25，集合: {lexical_target}")
            milvus.insert_lexical_documents(lexical_target, lexical_documents)

        result["success"] = True
        result["message"] = (
            f"成功处理 {len(chunks)} 个切片，"
            f"写入路由: {', '.join(inserted_routes)}"
        )
        result["document_count"] = len(chunks)
        result["embedding_routes"] = inserted_routes
        result["lexical_index"] = lexical_target

        print(f"文档处理完成: {result['message']}")

    except Exception as e:
        result["message"] = f"处理失败: {str(e)}"
        print(f"文档处理异常: {e}")
        import traceback
        traceback.print_exc()

    return result
