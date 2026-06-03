"""管理员公共课程路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.response import success
from app.core.security import require_role
from app.db.session import get_db
from app.schemas.common import (
    AdminMaterialUpdate,
    AdminPublicCourseCreate,
    AdminPublicCourseUpdate,
    AdminQuestionCreate,
    AdminQuestionUpdate,
    AuthUser,
)
from app.services import admin_public_course_service as service

router = APIRouter(prefix="/public-courses", tags=["admin-public-courses"])


def _format_course(course) -> dict:
    return {
        "id": course.id,
        "name": course.name,
        "created_at": course.created_at.isoformat() if course.created_at else "",
        "created_by": course.created_by,
        "is_public": bool(course.is_public),
        "material_count": len(course.materials),
        "question_count": len(course.questions),
    }


def _format_material(material) -> dict:
    return {
        "id": material.id,
        "course_id": material.course_id,
        "course_name": material.course.name if material.course else "",
        "type": material.type,
        "title": material.title,
        "url": material.url,
        "duration": material.duration,
        "pages": material.pages,
        "size": material.size,
        "date": material.date,
        "file_id": material.file_id,
        "source_material_id": material.source_material_id,
        "is_synced": bool(material.source_material_id),
    }


def _format_question(question) -> dict:
    return {
        "id": question.id,
        "type": question.type,
        "course_id": question.course_id,
        "course_name": question.course.name if question.course else "",
        "stem": question.stem,
        "options": question.options or [],
        "answer": question.answer,
        "explanation": question.explanation or "",
        "source_question_id": question.source_question_id,
        "is_synced": bool(question.source_question_id),
    }


@router.get("", summary="公共课程列表", description="管理员：获取所有公共课程")
def get_public_courses(
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    return success([_format_course(course) for course in service.list_public_courses(db)])


@router.post("", summary="创建公共课程", description="管理员：创建公共课程")
def add_public_course(
    data: AdminPublicCourseCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("admin")),
):
    course = service.create_public_course(db, data.name.strip(), current_user.id)
    return success(_format_course(course))


@router.put("/{course_id}", summary="编辑公共课程", description="管理员：修改公共课程名称并同步教师副本")
def edit_public_course(
    course_id: int,
    data: AdminPublicCourseUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    course = service.update_public_course(db, course_id, data.name.strip())
    if not course:
        raise BusinessException(404, "公共课程不存在")
    return success(_format_course(course))


@router.delete("/{course_id}", summary="删除公共课程", description="管理员：删除公共课程")
def remove_public_course(
    course_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    if not service.delete_public_course(db, course_id):
        raise BusinessException(404, "公共课程不存在")
    return success()


@router.get("/{course_id}/materials", summary="公共课程资料列表", description="管理员：获取公共课程资料")
def get_public_materials(
    course_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    return success([_format_material(material) for material in service.list_public_materials(db, course_id)])


@router.post("/{course_id}/materials", summary="新增公共课程资料", description="管理员：新增资料并同步教师副本")
def add_public_material(
    course_id: int,
    data: AdminMaterialUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    material = service.create_public_material(db, course_id, data.model_dump())
    return success(_format_material(material))


@router.put("/{course_id}/materials/{material_id}", summary="编辑公共课程资料", description="管理员：修改资料并同步教师副本")
def edit_public_material(
    course_id: int,
    material_id: int,
    data: AdminMaterialUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    material = service.update_public_material(material_id=material_id, db=db, data=data.model_dump())
    if not material or material.course_id != course_id:
        raise BusinessException(404, "公共资料不存在")
    return success(_format_material(material))


@router.delete("/{course_id}/materials/{material_id}", summary="删除公共课程资料", description="管理员：删除资料并同步删除教师副本")
def remove_public_material(
    course_id: int,
    material_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    material = service.update_public_material(material_id=material_id, db=db, data={})
    if not material or material.course_id != course_id:
        raise BusinessException(404, "公共资料不存在")
    if not service.delete_public_material(db, material_id):
        raise BusinessException(404, "公共资料不存在")
    return success()


@router.get("/{course_id}/questions", summary="公共课程题库列表", description="管理员：获取公共课程题目")
def get_public_questions(
    course_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    return success([_format_question(question) for question in service.list_public_questions(db, course_id)])


@router.post("/{course_id}/questions", summary="新增公共课程题目", description="管理员：新增题目并同步教师副本")
def add_public_question(
    course_id: int,
    data: AdminQuestionCreate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    question = service.create_public_question(db, course_id, data.model_dump())
    return success(_format_question(question))


@router.put("/{course_id}/questions/{question_id}", summary="编辑公共课程题目", description="管理员：修改题目并同步教师副本")
def edit_public_question(
    course_id: int,
    question_id: int,
    data: AdminQuestionUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    question = service.update_public_question(db, question_id, data.model_dump())
    if not question or question.course_id != course_id:
        raise BusinessException(404, "公共题目不存在")
    return success(_format_question(question))


@router.delete("/{course_id}/questions/{question_id}", summary="删除公共课程题目", description="管理员：删除题目并同步删除教师副本")
def remove_public_question(
    course_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("admin")),
):
    question = service.update_public_question(db, question_id, {})
    if not question or question.course_id != course_id:
        raise BusinessException(404, "公共题目不存在")
    if not service.delete_public_question(db, question_id):
        raise BusinessException(404, "公共题目不存在")
    return success()
