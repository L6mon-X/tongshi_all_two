"""Announcement routes"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.core.response import success
from app.core.exceptions import BusinessException
from app.schemas.common import AuthUser
from app.services.announcement_service import (
    list_announcements, create_announcement, delete_announcement,
    unread_count, mark_read, get_announcement,
)
from app.services.task_service import mark_completed, completion_report

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("")
def get_list(db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    return success(list_announcements(db, current_user))


@router.post("")
def create(data: dict, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("teacher"))):
    ann = create_announcement(db, current_user.id, data)
    return success({"id": ann.id})


@router.delete("/{announcement_id}")
def remove(announcement_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("teacher"))):
    ann = delete_announcement(db, announcement_id, current_user.id)
    if not ann:
        raise BusinessException(404, "公告不存在")
    return success()


@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("student"))):
    return success({"count": unread_count(db, current_user.id)})


@router.post("/{announcement_id}/read")
def read(announcement_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("student"))):
    ann = mark_read(db, current_user.id, announcement_id)
    if not ann:
        raise BusinessException(404, "公告不存在")
    return success()


@router.get("/{announcement_id}")
def detail(announcement_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    ann = get_announcement(db, announcement_id, current_user)
    if not ann:
        raise BusinessException(404, "公告不存在")
    return success(ann)


@router.post("/{announcement_id}/complete")
def complete(announcement_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("student"))):
    completion = mark_completed(db, current_user.id, announcement_id)
    if not completion:
        raise BusinessException(404, "公告不存在")
    return success()


@router.get("/{announcement_id}/completion-report")
def report(announcement_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(require_role("teacher"))):
    data = completion_report(db, announcement_id)
    if not data:
        raise BusinessException(404, "公告不存在")
    return success(data)
