"""Class routes"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.response import success
from app.core.exceptions import BusinessException
from app.schemas.common import AuthUser, ClassCreate
from app.services.class_service import (
    list_classes, create_class, delete_class,
    list_class_students, enroll_student, remove_student,
    import_students_from_excel,
)

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("")
def get_classes(db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    return success(list_classes(db))


@router.post("")
def post_class(data: ClassCreate, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    cls = create_class(db, data.name, data.major)
    return success({"id": cls.id})


@router.delete("/{class_id}")
def remove_class(class_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    cls = delete_class(db, class_id)
    if not cls:
        raise BusinessException(404, "班级不存在")
    return success()


@router.get("/{class_id}/students")
def get_students(class_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    students = list_class_students(db, class_id)
    if students is None:
        raise BusinessException(404, "班级不存在")
    return success(students)


@router.post("/{class_id}/enroll")
def add_student(class_id: int, student_id: str, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    enrollment, status = enroll_student(db, class_id, student_id)
    if enrollment is None and status == "班级不存在":
        raise BusinessException(404, status)
    if enrollment is None and status == "学生不存在":
        raise BusinessException(404, status)
    return success({"status": status})


@router.delete("/{class_id}/enroll/{student_id}")
def remove_enrollment(class_id: int, student_id: str, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    enrollment = remove_student(db, class_id, student_id)
    if not enrollment:
        raise BusinessException(404, "选课关系不存在")
    return success()


@router.post("/import")
def import_class_students(file: UploadFile = File(...), db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    content = file.file.read()
    result = import_students_from_excel(db, content)
    return success(result)
