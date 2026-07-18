"""知识库相关 Schema"""
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ============ 知识库 Schema ============

class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    document_count: int = Field(0, description="文档数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

# ============ 文档 Schema ============

AuthorityLevel = Literal[
    "official",
    "industry_standard",
    "enterprise",
    "academic",
    "media",
    "synthetic",
    "unknown",
]


class DocumentMetadataUpdate(BaseModel):
    """更新文档治理元数据。"""
    source_name: Optional[str] = Field(None, max_length=255, description="来源名称")
    source_url: Optional[str] = Field(None, description="原始来源 URL")
    document_type: Optional[str] = Field(None, max_length=50, description="文档类型")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    document_version: Optional[str] = Field(None, max_length=64, description="文档版本")
    authority_level: Optional[AuthorityLevel] = Field(None, description="来源权威等级")
    is_synthetic: Optional[bool] = Field(None, description="是否为合成演示数据")
    license_name: Optional[str] = Field(None, max_length=255, description="授权或使用条款")
    license_url: Optional[str] = Field(None, description="授权依据 URL")
    doi: Optional[str] = Field(None, max_length=255, description="论文或报告 DOI")
    external_id: Optional[str] = Field(None, max_length=255, description="外部系统标识")
    retrieved_at: Optional[datetime] = Field(None, description="资料获取时间")
    content_hash: Optional[str] = Field(None, max_length=64, description="SHA-256 内容哈希")
    review_status: Optional[Literal["approved", "metadata_only", "pending", "rejected"]] = Field(
        None, description="全文审核状态"
    )
    claim_type: Optional[str] = Field(None, max_length=64, description="证据/声明类型")
    is_open_access: Optional[bool] = Field(None, description="是否开放获取")

class DocumentResponse(BaseModel):
    """文档响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="文档ID")
    knowledge_base_id: str = Field(..., description="知识库ID")
    filename: str = Field(..., description="文件名")
    file_type: Optional[str] = Field(None, description="文件类型")
    file_size: Optional[int] = Field(None, description="文件大小(字节)")
    source_name: Optional[str] = Field(None, description="来源名称")
    source_url: Optional[str] = Field(None, description="原始来源 URL")
    document_type: str = Field("unknown", description="文档类型")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    document_version: Optional[str] = Field(None, description="文档版本")
    authority_level: AuthorityLevel = Field("unknown", description="来源权威等级")
    is_synthetic: bool = Field(False, description="是否为合成演示数据")
    license_name: Optional[str] = Field(None, description="授权或使用条款")
    license_url: Optional[str] = Field(None, description="授权依据 URL")
    doi: Optional[str] = Field(None, description="DOI")
    external_id: Optional[str] = Field(None, description="外部标识")
    retrieved_at: Optional[datetime] = Field(None, description="获取时间")
    content_hash: Optional[str] = Field(None, description="内容哈希")
    review_status: str = Field("pending", description="全文审核状态")
    claim_type: str = Field("unknown", description="证据/声明类型")
    is_open_access: bool = Field(False, description="是否开放获取")
    status: str = Field(..., description="处理状态: pending, processing, completed, failed")
    chunk_count: int = Field(0, description="切片数量")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    status: str = Field(default="success", description="API状态")
    id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    process_status: str = Field(..., description="处理状态")
    message: str = Field(..., description="消息")


class KnowledgeBaseWithDocuments(KnowledgeBaseResponse):
    """带文档列表的知识库响应"""
    documents: List[DocumentResponse] = Field(default_factory=list, description="文档列表")
