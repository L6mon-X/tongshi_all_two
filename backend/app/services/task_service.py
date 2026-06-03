"""题目任务完成服务。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.entities import Announcement, AnnouncementClass, QuizAttempt, StudentClassEnrollment, TaskCompletion, User


def _student_can_access(db: Session, user_id: str, announcement_id: int) -> bool:
    class_ids = [
        row.class_id for row in db.query(StudentClassEnrollment.class_id)
        .filter(StudentClassEnrollment.user_id == user_id)
        .all()
    ]
    if not class_ids:
        return False
    return db.query(AnnouncementClass).filter(
        AnnouncementClass.announcement_id == announcement_id,
        AnnouncementClass.class_id.in_(class_ids),
    ).first() is not None


def mark_completed(db: Session, user_id: str, announcement_id: int):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann or not _student_can_access(db, user_id, announcement_id):
        return None
    # 截止时间校验：已过期的任务不允许标记完成
    if ann.end_time and datetime.now(timezone.utc) > ann.end_time:
        raise BusinessException(400, "该任务已截止，无法标记完成")
    existing = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user_id,
        TaskCompletion.announcement_id == announcement_id,
    ).first()
    if existing:
        return existing
    try:
        completion = TaskCompletion(user_id=user_id, announcement_id=announcement_id)
        db.add(completion)
        db.commit()
        db.refresh(completion)
        return completion
    except SQLAlchemyError:
        db.rollback()
        raise BusinessException(500, "标记完成失败")


def completion_report(db: Session, announcement_id: int, teacher_id: str):
    ann = db.query(Announcement).filter(
        Announcement.id == announcement_id,
        Announcement.teacher_id == teacher_id,
    ).first()
    if not ann:
        return None

    class_links = db.query(AnnouncementClass).filter(AnnouncementClass.announcement_id == announcement_id).all()
    class_ids = [link.class_id for link in class_links]
    students = (
        db.query(User, StudentClassEnrollment.class_id)
        .join(StudentClassEnrollment, StudentClassEnrollment.user_id == User.id)
        .filter(StudentClassEnrollment.class_id.in_(class_ids), User.role == "student")
        .all()
    )
    completed_ids = {
        row.user_id for row in db.query(TaskCompletion.user_id)
        .filter(TaskCompletion.announcement_id == announcement_id)
        .all()
    }

    class_name_by_id = {
        link.class_id: link.class_.name if link.class_ else ""
        for link in class_links
    }
    seen_student_ids: set[str] = set()
    completed_students = []
    incomplete_students = []
    per_class = []

    # 计算成绩：获取此任务的题目列表和每个学生的答题情况
    question_ids = ann.question_ids if isinstance(ann.question_ids, list) else []
    total_questions = len(question_ids)

    # 预计算每个学生在此任务中的成绩
    student_scores: dict[str, int] = {}
    if question_ids:
        # 获取所有学生在这些题目上的答题记录
        attempts = (
            db.query(QuizAttempt.user_id, QuizAttempt.question_id, QuizAttempt.is_correct)
            .filter(QuizAttempt.question_id.in_(question_ids))
            .all()
        )
        # 统计每个学生的正确题数
        score_counts: dict[str, int] = {}
        for user_id, question_id, is_correct in attempts:
            if is_correct:
                score_counts[user_id] = score_counts.get(user_id, 0) + 1
        # 计算百分比成绩
        for user_id, correct_count in score_counts.items():
            student_scores[user_id] = round(correct_count / total_questions * 100) if total_questions > 0 else 0

    for class_id in class_ids:
        class_students = [(student, cid) for student, cid in students if cid == class_id]
        class_completed = 0
        for student, _ in class_students:
            payload = {
                "id": student.id, 
                "name": student.name, 
                "major": student.major,
                "class_id": class_id, 
                "class_name": class_name_by_id.get(class_id, ""),
                "score": student_scores.get(student.id, 0),
                "total_questions": total_questions,
            }
            if student.id in completed_ids:
                class_completed += 1
                if student.id not in seen_student_ids:
                    completed_students.append(payload)
            elif student.id not in seen_student_ids:
                incomplete_students.append(payload)
            seen_student_ids.add(student.id)
        per_class.append({
            "class_id": class_id,
            "class_name": class_name_by_id.get(class_id, ""),
            "total": len(class_students),
            "completed": class_completed,
        })

    # 处理时区比较问题
    def _is_expired(end_time: datetime | None) -> bool:
        if not end_time:
            return False
        now = datetime.now(timezone.utc)
        if end_time.tzinfo is None:
            end_time_utc = end_time.replace(tzinfo=timezone.utc)
            return now > end_time_utc
        return now > end_time

    return {
        "announcement_id": ann.id,
        "announcement_title": ann.title,
        "course_id": ann.course_id,
        "class_names": [class_name_by_id.get(class_id, "") for class_id in class_ids],
        "total_students": len(seen_student_ids),
        "completed_students": completed_students,
        "completed_count": len(completed_students),
        "incomplete_students": incomplete_students,
        "per_class": per_class,
        "is_expired": _is_expired(ann.end_time),
        "deadline": _iso(ann.end_time),
        "created_at": _iso(ann.created_at),
        "total_questions": total_questions,
    }


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def task_overview(db: Session, teacher_id: str) -> dict:
    """教师所有任务的总览：总完成数、未完成数，以及每个任务的简要信息。"""
    anns = (
        db.query(Announcement)
        .filter(Announcement.teacher_id == teacher_id, Announcement.type == "quiz")
        .order_by(Announcement.created_at.desc())
        .all()
    )
    if not anns:
        return {"total_tasks": 0, "total_completed": 0, "total_incomplete": 0, "tasks": []}

    ann_ids = [ann.id for ann in anns]

    # 每个任务的班级信息
    class_links = db.query(AnnouncementClass).filter(AnnouncementClass.announcement_id.in_(ann_ids)).all()
    ann_class_ids: dict[int, list[int]] = {}
    class_id_set: set[int] = set()
    for link in class_links:
        ann_class_ids.setdefault(link.announcement_id, []).append(link.class_id)
        class_id_set.add(link.class_id)

    # 班级名称映射
    from app.models.entities import Class
    class_names_map = {c.id: c.name for c in db.query(Class).filter(Class.id.in_(class_id_set)).all()} if class_id_set else {}

    # 每个任务的已完成人数
    completion_counts = dict(
        db.query(TaskCompletion.announcement_id, func.count(TaskCompletion.user_id))
        .filter(TaskCompletion.announcement_id.in_(ann_ids))
        .group_by(TaskCompletion.announcement_id)
        .all()
    )

    # 每个任务关联的去重学生数（按任务+班级统计学生，再跨班级去重）
    if class_id_set:
        enrollments = (
            db.query(StudentClassEnrollment.user_id, StudentClassEnrollment.class_id)
            .filter(StudentClassEnrollment.class_id.in_(class_id_set))
            .all()
        )
    else:
        enrollments = []

    # 构建 class_id -> set of student_ids
    class_students: dict[int, set[str]] = {}
    for uid, cid in enrollments:
        class_students.setdefault(cid, set()).add(uid)

    total_completed = 0
    total_incomplete = 0
    tasks = []
    now = datetime.now(timezone.utc)

    def _is_expired(end_time: datetime | None) -> bool:
        if not end_time:
            return False
        # 处理时区比较问题
        if end_time.tzinfo is None:
            # end_time 无时区信息，转换为 UTC 时间比较
            end_time_utc = end_time.replace(tzinfo=timezone.utc)
            return now > end_time_utc
        return now > end_time

    for ann in anns:
        cids = ann_class_ids.get(ann.id, [])
        # 跨班级去重学生
        student_ids: set[str] = set()
        for cid in cids:
            student_ids.update(class_students.get(cid, set()))
        total = len(student_ids)
        completed = completion_counts.get(ann.id, 0)
        total_completed += completed
        total_incomplete += max(total - completed, 0)
        tasks.append({
            "id": ann.id,
            "title": ann.title,
            "class_names": [class_names_map.get(cid, "") for cid in cids],
            "total_students": total,
            "completed_count": completed,
            "is_expired": _is_expired(ann.end_time),
            "created_at": _iso(ann.created_at),
        })

    return {
        "total_tasks": len(anns),
        "total_completed": total_completed,
        "total_incomplete": total_incomplete,
        "tasks": tasks,
    }
