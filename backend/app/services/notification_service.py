"""Student notification service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.timezone_utils import to_beijing_iso
from app.models.entities import Project, StudentNotification


def _format_notification(item: StudentNotification) -> dict:
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "content": item.content or "",
        "project_id": item.project_id,
        "is_read": bool(item.is_read),
        "created_at": to_beijing_iso(item.created_at),
    }


def list_notifications(db: Session, user_id: str) -> list[dict]:
    items = (
        db.query(StudentNotification)
        .filter(StudentNotification.user_id == user_id)
        .order_by(StudentNotification.created_at.desc(), StudentNotification.id.desc())
        .all()
    )
    return [_format_notification(item) for item in items]


def unread_count(db: Session, user_id: str) -> int:
    return (
        db.query(StudentNotification)
        .filter(StudentNotification.user_id == user_id, StudentNotification.is_read.is_(False))
        .count()
    )


def mark_read(db: Session, notification_id: int, user_id: str) -> StudentNotification | None:
    item = (
        db.query(StudentNotification)
        .filter(StudentNotification.id == notification_id, StudentNotification.user_id == user_id)
        .first()
    )
    if not item:
        return None
    if not item.is_read:
        item.is_read = True
        db.commit()
        db.refresh(item)
    return item


def create_project_review_notification(db: Session, project: Project, approved: bool, reason: str = "") -> None:
    status_text = "审核通过" if approved else "审核驳回"
    title = f"作品《{project.title}》{status_text}"
    if approved:
        content = "你的作品已通过教师审核，可以在作品展示中查看。"
    else:
        detail = reason.strip() if reason else "请根据教师反馈修改后重新提交。"
        content = f"你的作品未通过审核，驳回原因：{detail}"

    db.add(StudentNotification(
        user_id=project.author_id,
        type="project_review",
        title=title,
        content=content,
        project_id=project.id,
    ))
