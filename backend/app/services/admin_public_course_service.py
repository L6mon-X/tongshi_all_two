"""管理员公共课程服务。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.entities import Course, Material, Question
from app.services.public_course_sync_service import (
    delete_synced_materials,
    delete_synced_questions,
    sync_course_name_to_copies,
    sync_material_to_course_copies,
    sync_question_to_course_copies,
)


def _get_public_course(db: Session, course_id: int) -> Course | None:
    return db.query(Course).filter(Course.id == course_id, Course.is_public.is_(True)).first()


def list_public_courses(db: Session) -> list[Course]:
    return db.query(Course).filter(Course.is_public.is_(True)).order_by(Course.id.desc()).all()


def create_public_course(db: Session, name: str, admin_id: str) -> Course:
    if db.query(Course).filter(Course.name == name, Course.created_by == admin_id).first():
        raise BusinessException(400, "公共课程已存在")
    course = Course(name=name, created_by=admin_id, is_public=True)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def update_public_course(db: Session, course_id: int, name: str) -> Course | None:
    course = _get_public_course(db, course_id)
    if not course:
        return None
    course.name = name
    sync_course_name_to_copies(db, course)
    db.commit()
    db.refresh(course)
    return course


def delete_public_course(db: Session, course_id: int) -> bool:
    course = _get_public_course(db, course_id)
    if not course:
        return False
    copies = db.query(Course).filter(Course.source_course_id == course.id).all()
    source_material_ids = [material.id for material in course.materials]
    source_question_ids = [question.id for question in course.questions]
    for copy in copies:
        copy.source_course_id = None
    if source_material_ids:
        db.query(Material).filter(
            Material.source_material_id.in_(source_material_ids),
        ).update({Material.source_material_id: None}, synchronize_session=False)
    if source_question_ids:
        db.query(Question).filter(
            Question.source_question_id.in_(source_question_ids),
        ).update({Question.source_question_id: None}, synchronize_session=False)
    db.delete(course)
    db.commit()
    return True


def list_public_materials(db: Session, course_id: int) -> list[Material]:
    course = _get_public_course(db, course_id)
    if not course:
        raise BusinessException(404, "公共课程不存在")
    return db.query(Material).filter(Material.course_id == course_id).order_by(Material.id).all()


def create_public_material(db: Session, course_id: int, data: dict) -> Material:
    course = _get_public_course(db, course_id)
    if not course:
        raise BusinessException(404, "公共课程不存在")
    material = Material(
        course_id=course.id,
        date=datetime.now().strftime("%Y-%m-%d"),
        **data,
    )
    db.add(material)
    db.flush()
    sync_material_to_course_copies(db, material)
    db.commit()
    db.refresh(material)
    return material


def update_public_material(db: Session, material_id: int, data: dict) -> Material | None:
    material = db.query(Material).join(Course).filter(
        Material.id == material_id,
        Course.is_public.is_(True),
    ).first()
    if not material:
        return None
    for key, value in data.items():
        if value is not None and hasattr(material, key):
            setattr(material, key, value)
    sync_material_to_course_copies(db, material)
    db.commit()
    db.refresh(material)
    return material


def delete_public_material(db: Session, material_id: int) -> bool:
    material = db.query(Material).join(Course).filter(
        Material.id == material_id,
        Course.is_public.is_(True),
    ).first()
    if not material:
        return False
    delete_synced_materials(db, material.id)
    db.delete(material)
    db.commit()
    return True


def list_public_questions(db: Session, course_id: int) -> list[Question]:
    course = _get_public_course(db, course_id)
    if not course:
        raise BusinessException(404, "公共课程不存在")
    return db.query(Question).filter(Question.course_id == course_id).order_by(Question.id).all()


def create_public_question(db: Session, course_id: int, data: dict) -> Question:
    course = _get_public_course(db, course_id)
    if not course:
        raise BusinessException(404, "公共课程不存在")
    question = Question(course_id=course.id, **data)
    db.add(question)
    db.flush()
    sync_question_to_course_copies(db, question)
    db.commit()
    db.refresh(question)
    return question


def update_public_question(db: Session, question_id: int, data: dict) -> Question | None:
    question = db.query(Question).join(Course).filter(
        Question.id == question_id,
        Course.is_public.is_(True),
    ).first()
    if not question:
        return None
    for key, value in data.items():
        if value is not None and hasattr(question, key):
            setattr(question, key, value)
    sync_question_to_course_copies(db, question)
    db.commit()
    db.refresh(question)
    return question


def delete_public_question(db: Session, question_id: int) -> bool:
    question = db.query(Question).join(Course).filter(
        Question.id == question_id,
        Course.is_public.is_(True),
    ).first()
    if not question:
        return False
    delete_synced_questions(db, question.id)
    db.delete(question)
    db.commit()
    return True
