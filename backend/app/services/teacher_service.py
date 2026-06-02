"""Teacher service"""
from sqlalchemy.orm import Session
from app.models.entities import (
    Announcement,
    AnnouncementClass,
    Class,
    Course,
    Project,
    QuizAttempt,
    StudentProgress,
    StudentClassEnrollment,
    TaskCompletion,
    User,
)


def _teacher_class_ids(db: Session, teacher_id: str) -> list[int]:
    return [
        row.id for row in db.query(Class.id)
        .join(Course, Course.id == Class.course_id)
        .filter(Course.created_by == teacher_id)
        .all()
    ]


def _teacher_student_ids(db: Session, teacher_id: str) -> list[str]:
    class_ids = _teacher_class_ids(db, teacher_id)
    if not class_ids:
        return []
    return [
        row.user_id for row in db.query(StudentClassEnrollment.user_id)
        .filter(StudentClassEnrollment.class_id.in_(class_ids))
        .distinct()
        .all()
    ]


def get_teacher_stats(db: Session, teacher_id: str):
    student_ids = _teacher_student_ids(db, teacher_id)
    total_students = len(student_ids)
    my_courses = db.query(Course).filter(Course.created_by == teacher_id).count()
    pending_reviews_query = db.query(Project).filter(Project.status == "pending")
    if student_ids:
        pending_reviews_query = pending_reviews_query.filter(Project.author_id.in_(student_ids))
    else:
        pending_reviews_query = pending_reviews_query.filter(False)
    pending_reviews = pending_reviews_query.count()
    weekly_exercises_query = db.query(QuizAttempt)
    if student_ids:
        weekly_exercises_query = weekly_exercises_query.filter(QuizAttempt.user_id.in_(student_ids))
    else:
        weekly_exercises_query = weekly_exercises_query.filter(False)
    weekly_exercises = weekly_exercises_query.count()  # simplified: total instead of weekly
    return {
        "total_students": total_students,
        "my_courses": my_courses,
        "pending_reviews": pending_reviews,
        "weekly_exercises": weekly_exercises,
    }


def list_students(db: Session, teacher_id: str, class_id: int = None, page: int = None, page_size: int = None, keyword: str = None):
    class_ids = _teacher_class_ids(db, teacher_id)
    if class_id:
        if class_id not in class_ids:
            return [], 0
        class_ids = [class_id]
    if not class_ids:
        return [], 0
    query = (
        db.query(User)
        .join(StudentClassEnrollment, StudentClassEnrollment.user_id == User.id)
        .filter(User.role == "student", StudentClassEnrollment.class_id.in_(class_ids))
        .distinct()
    )
    if keyword:
        query = query.filter(
            (User.id.like(f"%{keyword}%")) | (User.name.like(f"%{keyword}%"))
        )
    query = query.order_by(User.id)
    total = query.count()
    if page and page_size:
        students = query.offset((page - 1) * page_size).limit(page_size).all()
    else:
        students = query.all()

    student_ids = [s.id for s in students]
    student_class_ids: dict[str, set[int]] = {student_id: set() for student_id in student_ids}
    class_task_ids: dict[int, set[int]] = {}
    completed_task_ids: dict[str, set[int]] = {student_id: set() for student_id in student_ids}

    if student_ids:
        enrollment_rows = (
            db.query(StudentClassEnrollment.user_id, StudentClassEnrollment.class_id)
            .filter(
                StudentClassEnrollment.user_id.in_(student_ids),
                StudentClassEnrollment.class_id.in_(class_ids),
            )
            .all()
        )
        for user_id, owned_class_id in enrollment_rows:
            student_class_ids.setdefault(user_id, set()).add(owned_class_id)

        task_rows = (
            db.query(Announcement.id, AnnouncementClass.class_id)
            .join(AnnouncementClass, AnnouncementClass.announcement_id == Announcement.id)
            .filter(
                Announcement.teacher_id == teacher_id,
                Announcement.type == "quiz",
                AnnouncementClass.class_id.in_(class_ids),
            )
            .all()
        )
        all_task_ids: set[int] = set()
        for task_id, owned_class_id in task_rows:
            class_task_ids.setdefault(owned_class_id, set()).add(task_id)
            all_task_ids.add(task_id)

        if all_task_ids:
            completion_rows = (
                db.query(TaskCompletion.user_id, TaskCompletion.announcement_id)
                .filter(
                    TaskCompletion.user_id.in_(student_ids),
                    TaskCompletion.announcement_id.in_(all_task_ids),
                )
                .all()
            )
            for user_id, task_id in completion_rows:
                completed_task_ids.setdefault(user_id, set()).add(task_id)

    result = []
    for s in students:
        progresses = (
            db.query(StudentProgress)
            .join(Course, Course.id == StudentProgress.course_id)
            .filter(StudentProgress.user_id == s.id, Course.created_by == teacher_id)
            .all()
        )
        total_progress = sum(p.learn_progress for p in progresses)
        avg_progress = int(total_progress / len(progresses)) if progresses else 0

        total_done = sum(p.questions_done for p in progresses)
        total_accuracy = sum(p.accuracy for p in progresses)
        avg_accuracy = int(total_accuracy / len(progresses)) if progresses else 0

        enrollment_query = (
            db.query(StudentClassEnrollment, Class)
            .join(Class, Class.id == StudentClassEnrollment.class_id)
            .filter(StudentClassEnrollment.user_id == s.id, Class.id.in_(class_ids))
        )
        if class_id:
            enrollment_query = enrollment_query.filter(StudentClassEnrollment.class_id == class_id)
        enrollment = enrollment_query.order_by(StudentClassEnrollment.enrolled_at.desc()).first()
        class_id_value = enrollment[1].id if enrollment else None
        class_name = enrollment[1].name if enrollment else ""
        assigned_task_ids: set[int] = set()
        for owned_class_id in student_class_ids.get(s.id, set()):
            assigned_task_ids.update(class_task_ids.get(owned_class_id, set()))
        completed_count = len(assigned_task_ids & completed_task_ids.get(s.id, set()))
        total_task_count = len(assigned_task_ids)
        incomplete_count = max(total_task_count - completed_count, 0)
        task_completion_rate = int(round(completed_count / total_task_count * 100)) if total_task_count else 0

        result.append({
            "id": s.id,
            "name": s.name,
            "major": s.major or "",
            "class_id": class_id_value,
            "class_name": class_name,
            "progress": avg_progress,
            "exercises": total_done,
            "accuracy": avg_accuracy,
            "completed_tasks": completed_count,
            "incomplete_tasks": incomplete_count,
            "task_completion_rate": task_completion_rate,
        })
    return result, total


def list_all_projects(
    db: Session,
    status: str = None,
    page: int = None,
    page_size: int = None,
    teacher_id: str | None = None,
    keyword: str | None = None,
):
    query = db.query(Project)
    if teacher_id:
        student_ids = _teacher_student_ids(db, teacher_id)
        if student_ids:
            query = query.filter(Project.author_id.in_(student_ids))
        else:
            query = query.filter(False)
    if status:
        query = query.filter(Project.status == status)
    if keyword:
        query = query.filter(Project.title.like(f"%{keyword}%"))
    query = query.order_by(Project.date.desc())
    total = query.count()
    if page and page_size:
        projects = query.offset((page - 1) * page_size).limit(page_size).all()
    else:
        projects = query.all()
    return projects, total
