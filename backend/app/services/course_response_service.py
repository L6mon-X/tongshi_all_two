"""课程接口响应组装。"""
from __future__ import annotations

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


def build_course_list(db: Session, current_user: AuthUser):
    if current_user.role == "teacher":
        courses = list_courses(db, current_user.id)
        return [_format_course(db, course, current_user) for course in courses]

    if current_user.role == "student":
        enrollments = (
            db.query(StudentClassEnrollment)
            .filter(StudentClassEnrollment.user_id == current_user.id)
            .all()
        )
        if not enrollments:
            return {"courses": [], "hint": "你尚未加入任何班级，请联系老师"}

        class_ids = [item.class_id for item in enrollments]
        classes_with_course = (
            db.query(Class)
            .filter(Class.id.in_(class_ids), Class.course_id.isnot(None))
            .all()
        )
        if not classes_with_course:
            return {"courses": [], "hint": "你的班级尚未分配课程，请联系老师"}

        course_ids = list({item.course_id for item in classes_with_course})
        courses = db.query(Course).filter(Course.id.in_(course_ids)).order_by(Course.id.desc()).all()
        return {
            "courses": [_format_course(db, course, current_user) for course in courses],
            "hint": None,
        }

    courses = list_courses(db)
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
