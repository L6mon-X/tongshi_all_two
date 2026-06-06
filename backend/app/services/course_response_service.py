"""课程接口响应组装。"""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.timezone_utils import to_beijing_iso
from app.models.entities import Class, Course, StudentClassEnrollment
from app.schemas.common import AuthUser
from app.services.question_service import list_courses


def _format_course(db: Session, course: Course, current_user: AuthUser, class_count: int | None = None) -> dict:
    if class_count is None:
        class_count = (
            db.query(Class).filter(Class.course_id == course.id, Class.created_by == current_user.id).count()
            if current_user.role == "teacher"
            else len(course.classes)
        )
    return {
        "id": course.id,
        "name": course.name,
        "created_at": to_beijing_iso(course.created_at),
        "created_by": course.created_by,
        "is_public": bool(course.is_public),
        "is_owner": course.created_by == current_user.id,
        "material_count": len(course.materials),
        "question_count": len(course.questions),
        "class_count": class_count,
    }


def build_course_list(db: Session, current_user: AuthUser, keyword: str | None = None):
    if current_user.role == "teacher":
        courses = list_courses(db, current_user.id, keyword)
        return [_format_course(db, course, current_user) for course in courses]

    if current_user.role == "student":
        enrollments = (
            db.query(StudentClassEnrollment)
            .filter(StudentClassEnrollment.user_id == current_user.id)
            .all()
        )
        class_ids = [item.class_id for item in enrollments]
        if class_ids:
            classes_with_course = (
                db.query(Class)
                .filter(Class.id.in_(class_ids), Class.course_id.isnot(None))
                .all()
            )
            enrolled_course_ids = list({item.course_id for item in classes_with_course})
        else:
            enrolled_course_ids = []

        # 学生可见：已加入班级的课程 + 所有公共课程
        query = db.query(Course).filter(
            or_(Course.id.in_(enrolled_course_ids), Course.is_public == True)
        )
        if keyword:
            query = query.filter(Course.name.contains(keyword))
        courses = query.order_by(Course.id.desc()).all()
        return {
            "courses": [_format_course(db, course, current_user) for course in courses],
            "hint": None,
        }

    courses = list_courses(db, keyword=keyword)
    return [_format_course(db, course, current_user) for course in courses]


def build_course_detail(db: Session, detail: tuple[Course, int, int, int], current_user: AuthUser) -> dict:
    course, material_count, question_count, class_count = detail
    visible_class_count = (
        db.query(Class).filter(Class.course_id == course.id, Class.created_by == current_user.id).count()
        if current_user.role == "teacher"
        else class_count
    )
    data = _format_course(db, course, current_user, visible_class_count)
    data["material_count"] = material_count
    data["question_count"] = question_count
    return data
