"""为指定用户创建四个半导体研究方向的知识库记录。

脚本是幂等的：已存在的同名知识库会被跳过，不会删除文档或向量数据。
Milvus collection 仍在首份文档处理时按需创建。
"""
import argparse

from config.industry_config import INDUSTRY_CONFIGS
from core.database import SessionLocal
from models.knowledge import KnowledgeBase
from models.user import User


def seed_knowledge_bases(username: str) -> tuple[list[str], list[str]]:
    """创建缺失的知识库，返回（新建名称，已存在名称）。"""

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"用户不存在: {username}")

        created: list[str] = []
        existing: list[str] = []

        for config in INDUSTRY_CONFIGS.values():
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.user_id == user.id,
                KnowledgeBase.name == config.knowledge_base_name,
            ).first()
            if kb:
                existing.append(config.knowledge_base_name)
                continue

            db.add(
                KnowledgeBase(
                    user_id=user.id,
                    name=config.knowledge_base_name,
                    description=f"{config.name}：{config.description}",
                )
            )
            created.append(config.knowledge_base_name)

        db.commit()
        return created, existing
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="创建半导体研究方向知识库")
    parser.add_argument("--username", required=True, help="知识库所属用户名")
    args = parser.parse_args()

    created, existing = seed_knowledge_bases(args.username)
    print("新建知识库:", ", ".join(created) if created else "无")
    print("已存在知识库:", ", ".join(existing) if existing else "无")


if __name__ == "__main__":
    main()
