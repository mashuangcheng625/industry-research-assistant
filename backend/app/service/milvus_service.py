"""Milvus 向量存储服务"""
import os
import threading
import time
from typing import List, Dict, Any, Optional
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)


class MilvusService:
    """Milvus 向量存储服务"""

    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "localhost")
        self.port = int(os.getenv("MILVUS_PORT", "19530"))
        self.vector_dim = 1024  # text-embedding-v4 维度
        self._chunk_cache: Dict[tuple[str, int], tuple[float, List[Dict[str, Any]]]] = {}
        self._chunk_cache_lock = threading.Lock()
        self._connect()

    def _invalidate_chunk_cache(self, collection_name: str) -> None:
        """集合内容变更后主动失效词法扫描缓存。"""
        with self._chunk_cache_lock:
            keys = [key for key in self._chunk_cache if key[0] == collection_name]
            for key in keys:
                self._chunk_cache.pop(key, None)

    def _connect(self):
        """连接到 Milvus"""
        try:
            uri = os.getenv("MILVUS_URI")
            if uri:
                connections.connect(alias="default", uri=uri)
                print(f"已连接到 Milvus URI: {uri}")
            else:
                connections.connect(
                    alias="default",
                    host=self.host,
                    port=self.port,
                )
                print(f"已连接到 Milvus: {self.host}:{self.port}")
        except Exception as e:
            print(f"连接 Milvus 失败: {e}")
            raise

    def create_collection(self, collection_name: str) -> Collection:
        """
        创建集合（如果不存在）

        Args:
            collection_name: 集合名称

        Returns:
            Collection 对象
        """
        # 检查集合是否存在
        if utility.has_collection(collection_name):
            print(f"集合 {collection_name} 已存在")
            collection = Collection(collection_name)
            collection.load()
            return collection

        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content_hash", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="embedding_provider", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding_version", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
        ]

        schema = CollectionSchema(fields=fields, description=f"Knowledge base: {collection_name}")
        collection = Collection(name=collection_name, schema=schema)

        # 创建索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="vector", index_params=index_params)

        # 加载集合到内存
        collection.load()

        print(f"集合 {collection_name} 创建成功")
        return collection

    def insert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
    ) -> int:
        """
        插入文档

        Args:
            collection_name: 集合名称
            documents: 文档列表，每个文档包含:
                - id: 文档ID
                - doc_id: 原始文档ID
                - kb_id: 知识库ID
                - filename: 文件名
                - content: 文本内容
                - chunk_index: 切片索引
                - vector: 向量

        Returns:
            插入的文档数量
        """
        collection = self.create_collection(collection_name)

        # 按实际 schema 构造行，既兼容旧 Collection，也支持带模型指纹的新 Collection。
        field_names = {
            field.name
            for field in collection.schema.fields
            if not getattr(field, "auto_id", False)
        }
        rows = []
        for document in documents:
            row = {
                "id": document["id"],
                "doc_id": document["doc_id"],
                "kb_id": document["kb_id"],
                "filename": document["filename"],
                "content": document["content"][:65535],
                "chunk_index": document["chunk_index"],
                "content_hash": document.get("content_hash", ""),
                "embedding_provider": document.get("embedding_provider", "legacy"),
                "embedding_model": document.get("embedding_model", "legacy"),
                "embedding_version": document.get("embedding_version", "legacy"),
                "vector": document["vector"],
            }
            rows.append({key: value for key, value in row.items() if key in field_names})
        collection.insert(rows)
        collection.flush()
        self._invalidate_chunk_cache(collection_name)

        print(f"成功插入 {len(documents)} 条文档到 {collection_name}")
        return len(documents)

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        kb_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量搜索

        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            kb_id: 知识库ID（可选，用于过滤）

        Returns:
            搜索结果列表
        """
        if not utility.has_collection(collection_name):
            print(f"集合 {collection_name} 不存在")
            return []

        collection = Collection(collection_name)
        collection.load()

        # 构建过滤表达式
        expr = f'kb_id == "{kb_id}"' if kb_id else None

        # 搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }

        results = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["id", "doc_id", "kb_id", "filename", "content", "chunk_index"],
        )

        # 格式化结果
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit.entity.get("id"),
                    "doc_id": hit.entity.get("doc_id"),
                    "kb_id": hit.entity.get("kb_id"),
                    "filename": hit.entity.get("filename"),
                    "content": hit.entity.get("content"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "score": hit.score,
                })

        return formatted_results

    def delete_by_doc_id(self, collection_name: str, doc_id: str) -> bool:
        """
        根据文档ID删除所有相关切片

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            是否成功
        """
        if not utility.has_collection(collection_name):
            return True

        try:
            collection = Collection(collection_name)
            expr = f'doc_id == "{doc_id}"'
            collection.delete(expr)
            self._invalidate_chunk_cache(collection_name)
            print(f"已删除文档 {doc_id} 的所有切片")
            return True
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """
        删除集合

        Args:
            collection_name: 集合名称

        Returns:
            是否成功
        """
        try:
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                self._invalidate_chunk_cache(collection_name)
                print(f"集合 {collection_name} 已删除")
            return True
        except Exception as e:
            print(f"删除集合失败: {e}")
            return False

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息

        Args:
            collection_name: 集合名称

        Returns:
            统计信息
        """
        if not utility.has_collection(collection_name):
            return {"exists": False}

        collection = Collection(collection_name)
        return {
            "exists": True,
            "name": collection_name,
            "num_entities": collection.num_entities,
        }

    def get_chunks_by_filename(
        self,
        collection_name: str,
        filename: str,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        根据文件名获取所有切片

        Args:
            collection_name: 集合名称
            filename: 文件名
            limit: 最大返回数量

        Returns:
            切片列表
        """
        if not utility.has_collection(collection_name):
            print(f"集合 {collection_name} 不存在")
            return []

        try:
            collection = Collection(collection_name)
            collection.load()
            safe_filename = filename.replace("\\", "\\\\").replace('"', '\\"')
            results = collection.query(
                expr=f'filename == "{safe_filename}"',
                output_fields=[
                    "id", "doc_id", "kb_id", "filename", "content", "chunk_index",
                ],
                limit=limit,
            )
            results.sort(key=lambda item: item.get("chunk_index", 0))
            return results
        except Exception as e:
            print(f"查询切片失败: {e}")
            return []

    def get_neighbor_chunks(
        self,
        collection_name: str,
        doc_id: str,
        chunk_indices: List[int],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """读取同一文档指定索引的切片，不允许跨文档扩展。"""
        if not chunk_indices or not utility.has_collection(collection_name):
            return []
        try:
            collection = Collection(collection_name)
            collection.load()
            safe_doc_id = doc_id.replace("\\", "\\\\").replace('"', '\\"')
            indices = sorted({int(index) for index in chunk_indices if int(index) >= 0})
            expr = f'doc_id == "{safe_doc_id}" and chunk_index in {indices}'
            results = collection.query(
                expr=expr,
                output_fields=["id", "doc_id", "kb_id", "filename", "content", "chunk_index"],
                limit=min(limit, len(indices)),
            )
            results.sort(key=lambda item: item.get("chunk_index", 0))
            return results
        except Exception as e:
            print(f"查询相邻切片失败: {e}")
            return []

    def list_chunks(
        self,
        collection_name: str,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """分页读取集合中的切片，用于关键词候选召回。"""
        if not utility.has_collection(collection_name):
            return []

        try:
            ttl_seconds = max(
                0.0,
                float(os.getenv("RAG_CHUNK_CACHE_TTL_SECONDS", "300")),
            )
            cache_key = (collection_name, limit)
            now = time.monotonic()
            if ttl_seconds > 0:
                with self._chunk_cache_lock:
                    cached = self._chunk_cache.get(cache_key)
                    if cached and now - cached[0] <= ttl_seconds:
                        return cached[1]

            collection = Collection(collection_name)
            collection.load()
            iterator = collection.query_iterator(
                batch_size=min(1000, limit),
                limit=limit,
                expr='id != ""',
                output_fields=["id", "doc_id", "kb_id", "filename", "content", "chunk_index"],
            )
            chunks: List[Dict[str, Any]] = []
            try:
                while len(chunks) < limit:
                    batch = iterator.next()
                    if not batch:
                        break
                    chunks.extend(batch)
            finally:
                iterator.close()
            result = chunks[:limit]
            if ttl_seconds > 0:
                with self._chunk_cache_lock:
                    self._chunk_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            print(f"读取集合切片失败: {e}")
            return []


# 单例实例
_milvus_service: Optional[MilvusService] = None


def get_milvus_service() -> MilvusService:
    """获取 Milvus 服务单例"""
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService()
    return _milvus_service
