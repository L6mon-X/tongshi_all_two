"""Student notification routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.response import success
from app.core.security import require_role
from app.db.session import get_db
from app.schemas.common import AuthUser
from app.services.notification_service import list_notifications, mark_read, unread_count

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", summary="学生通知列表")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("student")),
):
    return success(list_notifications(db, current_user.id))


@router.get("/unread-count", summary="学生未读通知数")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("student")),
):
    return success({"count": unread_count(db, current_user.id)})


@router.post("/{notification_id}/read", summary="标记学生通知已读")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("student")),
):
    item = mark_read(db, notification_id, current_user.id)
    if not item:
        raise BusinessException(404, "通知不存在")
    return success()
