"""聊天附件路由"""
import os
from pathlib import Path
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from core.database import get_db
from core.async_tasks import get_task_queue
from models.chat import ChatAttachment, ChatSession
from models.user import User
from router.auth_router import get_current_user_required
from schemas.chat import AttachmentResponse, AttachmentListResponse
from core.rate_limit import enforce_standard_rate_limit

router = APIRouter(
    prefix="/attachments",
    tags=["聊天附件"],
    dependencies=[Depends(enforce_standard_rate_limit)],
)

# 文件上传目录
UPLOAD_DIR = os.getenv("ATTACHMENT_UPLOAD_DIR", "/tmp/chat_attachments")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_ATTACHMENT_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))

# 支持的文件类型
ALLOWED_EXTENSIONS = {
    # 文档类型
    '.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.xlsx', '.xls', '.pptx', '.ppt',
    # 图片类型
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
    # 代码类型
    '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.xml', '.csv',
}


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(filename)[1].lower()


def attachment_to_response(att: ChatAttachment) -> AttachmentResponse:
    """将附件模型转换为响应"""
    return AttachmentResponse(
        id=str(att.id),
        session_id=str(att.session_id),
        message_id=str(att.message_id) if att.message_id else None,
        filename=att.filename,
        file_type=att.file_type,
        file_size=att.file_size,
        status=att.status,
        error_message=att.error_message,
        created_at=att.created_at,
    )


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """上传聊天附件"""
    # 解析 session_id
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的会话ID格式"
        )

    # 验证会话存在
    session = db.query(ChatSession).filter(
        ChatSession.id == session_uuid,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 验证文件类型
    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {ext}，支持的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 生成唯一文件名
    import uuid
    safe_filename = Path(file.filename or "upload").name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 保存文件
    try:
        total_bytes = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件超过 {MAX_ATTACHMENT_BYTES} bytes",
                    )
                buffer.write(chunk)
        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不允许上传空文件",
            )
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败: {str(e)}"
        )

    # 获取文件大小
    file_size = os.path.getsize(file_path)

    # 创建附件记录
    att = ChatAttachment(
        session_id=session_uuid,
        user_id=current_user.id,
        filename=safe_filename,
        file_type=ext[1:] if ext else "unknown",
        file_size=file_size,
        file_path=file_path,
        status="pending",
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    try:
        task_id = await get_task_queue().enqueue(
            "attachment.process",
            {"attachment_id": str(att.id), "file_path": file_path},
            owner_id=str(current_user.id),
            max_retries=2,
            timeout_seconds=int(os.getenv("ATTACHMENT_TASK_TIMEOUT_SECONDS", "300")),
        )
    except (RedisError, ValueError) as exc:
        att.status = "failed"
        att.error_message = "持久化任务队列不可用"
        db.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="附件已拒绝接收：持久化任务队列不可用",
        ) from exc

    response = attachment_to_response(att)
    response.task_id = task_id
    return response


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """获取附件详情"""
    try:
        att_uuid = UUID(attachment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的附件ID格式"
        )

    att = db.query(ChatAttachment).filter(
        ChatAttachment.id == att_uuid,
        ChatAttachment.user_id == current_user.id,
    ).first()
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="附件不存在"
        )

    return attachment_to_response(att)


@router.get("/session/{session_id}", response_model=AttachmentListResponse)
async def get_session_attachments(
    session_id: str,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """获取会话的所有附件"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的会话ID格式"
        )

    # 验证会话存在
    session = db.query(ChatSession).filter(
        ChatSession.id == session_uuid,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    attachments = db.query(ChatAttachment).filter(
        ChatAttachment.session_id == session_uuid,
        ChatAttachment.user_id == current_user.id,
    ).order_by(ChatAttachment.created_at.desc()).all()

    return AttachmentListResponse(
        attachments=[attachment_to_response(att) for att in attachments],
        total=len(attachments),
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """删除附件"""
    try:
        att_uuid = UUID(attachment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的附件ID格式"
        )

    att = db.query(ChatAttachment).filter(
        ChatAttachment.id == att_uuid,
        ChatAttachment.user_id == current_user.id,
    ).first()
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="附件不存在"
        )

    # 删除文件
    if att.file_path and os.path.exists(att.file_path):
        try:
            os.remove(att.file_path)
        except Exception:
            pass  # 忽略文件删除错误

    db.delete(att)
    db.commit()
    return None
