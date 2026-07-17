# Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有

"""知识库相关模型"""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, String, Text, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class KnowledgeBase(Base):
    """知识库模型"""
    __tablename__ = "knowledge_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    document_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    """文档模型"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(BigInteger)
    file_path = Column(String(500))
    source_name = Column(String(255))
    source_url = Column(Text)
    document_type = Column(String(50), default="unknown", nullable=False)
    published_at = Column(DateTime)
    document_version = Column(String(64))
    authority_level = Column(String(32), default="unknown", nullable=False)
    is_synthetic = Column(Boolean, default=False, nullable=False)
    license_name = Column(String(255))
    license_url = Column(Text)
    doi = Column(String(255))
    external_id = Column(String(255))
    retrieved_at = Column(DateTime)
    content_hash = Column(String(64))
    review_status = Column(String(32), default="pending", nullable=False)
    claim_type = Column(String(64), default="unknown", nullable=False)
    is_open_access = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    user = relationship("User", back_populates="documents")
