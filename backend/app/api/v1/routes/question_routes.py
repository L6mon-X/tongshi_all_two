"""Question routes"""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, UploadFile, File
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.core.response import success
from app.core.exceptions import BusinessException
from app.schemas.common import AuthUser, QuestionCreate, QuestionUpdate
from app.services.question_service import (
    list_questions, create_question, update_question, delete_question,
    get_chapter_questions, list_courses, create_course, update_course, delete_course,
    import_questions_from_excel,
)

router = APIRouter(prefix="/questions", tags=["questions"])


def _format_question(q):
    return {
        "id": q.id, "type": q.type, "chapter_id": q.chapter_id,
        "stem": q.stem, "options": q.options,
        "answer": q.answer, "explanation": q.explanation,
    }


@router.get("")
def get_questions(chapter_id: int = None, type: str = None, db: Session = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    questions = list_questions(db, chapter_id, type)
    return success([_format_question(q) for q in questions])


@router.get("/chapter/{chapter_id}")
def get_chapter_questions_for_quiz(chapter_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    questions = get_chapter_questions(db, chapter_id)
    return success([_format_question(q) for q in questions])


@router.post("")
def add_question(data: QuestionCreate, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    q = create_question(db, data.model_dump())
    return success({"id": q.id})


@router.put("/{question_id}")
def edit_question(question_id: int, data: QuestionUpdate, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    q = update_question(db, question_id, data.model_dump(exclude_unset=True))
    if not q:
        raise BusinessException(404, "题目不存在")
    return success()


@router.delete("/{question_id}")
def remove_question(question_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    if not delete_question(db, question_id):
        raise BusinessException(404, "题目不存在")
    return success()


@router.get("/courses")
def get_courses(db: Session = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    return success([{ "id": c.id, "name": c.name, "created_at": c.created_at.isoformat() if c.created_at else "" } for c in list_courses(db)])


@router.post("/courses")
def add_course(payload: dict, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    course = create_course(db, payload.get("name", "").strip())
    return success({"id": course.id})


@router.put("/courses/{course_id}")
def edit_course(course_id: int, payload: dict, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    course = update_course(db, course_id, payload.get("name", "").strip())
    if not course:
        raise BusinessException(404, "课程不存在")
    return success()


@router.delete("/courses/{course_id}")
def remove_course(course_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    if not delete_course(db, course_id):
        raise BusinessException(404, "课程不存在")
    return success()


@router.post("/import")
def import_questions(file: UploadFile = File(...), db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    wb = load_workbook(filename=BytesIO(file.file.read()), data_only=True)
    ws = wb.active
    headers = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        item = {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
        rows.append(item)
    return success(import_questions_from_excel(db, rows))
