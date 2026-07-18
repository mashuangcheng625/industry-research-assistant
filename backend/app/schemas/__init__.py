from .search import (
    WebSearchRequest,
    SearchResultItem,
    WebSearchResponse
)

from .chat import (
    ChatRequest,
    RetrievedDocument,
    ChatResponse,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionWithMessagesResponse,
    MessageCreate,
    MessageResponse,
    LegacySessionResponse,
    AttachmentResponse,
    AttachmentListResponse,
    ChatWithAttachmentsRequest,
)

from .knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseWithDocuments,
    DocumentResponse as KBDocumentResponse,
    DocumentUploadResponse as KBDocumentUploadResponse,
    DocumentMetadataUpdate,
)


__all__ = [
    # Search schemas
    'WebSearchRequest',
    'SearchResultItem',
    'WebSearchResponse',

    # Chat schemas
    'ChatRequest',
    'RetrievedDocument',
    'ChatResponse',
    'SessionCreate',
    'SessionUpdate',
    'SessionResponse',
    'SessionWithMessagesResponse',
    'MessageCreate',
    'MessageResponse',
    'LegacySessionResponse',
    'AttachmentResponse',
    'AttachmentListResponse',
    'ChatWithAttachmentsRequest',

    # Knowledge Base schemas
    'KnowledgeBaseCreate',
    'KnowledgeBaseUpdate',
    'KnowledgeBaseResponse',
    'KnowledgeBaseWithDocuments',
    'KBDocumentResponse',
    'KBDocumentUploadResponse',
    'DocumentMetadataUpdate',
]
