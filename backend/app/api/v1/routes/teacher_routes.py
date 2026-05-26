"""Teacher routes"""
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.security import require_role
from app.core.response import success
from app.core.exceptions import BusinessException
from app.schemas.common import AuthUser, ProjectReviewAction
from app.services.teacher_service import get_teacher_stats, list_students, list_all_projects
from app.services.project_service import approve_project, reject_project
from app.services.file_service import resolve_file_stream
from app.models.entities import User, Project

router = APIRouter(prefix="/teacher", tags=["teacher"])


def _format_project(db: Session, p):
    author = db.query(User).filter(User.id == p.author_id).first()
    images = [
        {"id": image.id, "image_url": image.image_url, "sort_order": image.sort_order, "file_id": image.file_id}
        for image in sorted(p.images, key=lambda item: (item.sort_order, item.id))
    ]
    if not images and p.image_url:
        images = [{"image_url": p.image_url, "sort_order": 0}]
    return {
        "id": p.id,
        "title": p.title,
        "author_id": p.author_id,
        "author_name": author.name if author else "",
        "major": p.major,
        "description": p.description,
        "tags": p.tags,
        "likes": p.likes,
        "featured": p.featured,
        "video_url": p.video_url,
        "report_url": p.report_url,
        "image_url": p.image_url,
        "images": images,
        "link_url": getattr(p, "link_url", ""),
        "status": p.status,
        "reject_reason": p.reject_reason,
        "date": p.date,
        "report_file_id": getattr(p, "report_file_id", None),
        "cover_file_id": getattr(p, "cover_file_id", None),
    }


@router.get("/stats", summary="工作台概览", description="教师端：返回总学生数、已发布章节数、待审核作品数、练习题量等教学数据")
def teacher_stats(db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    return success(get_teacher_stats(db))


@router.get("/students", summary="学生数据", description="教师端：返回所有学生的学号、姓名、专业、班级、学习进度和练习统计")
def get_students(
    class_id: int = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("teacher")),
):
    return success(list_students(db, class_id))


@router.get("/projects", summary="作品审核列表", description="教师端：按状态筛选所有学生作品，默认返回全部")
def get_all_projects(
    status: str = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("teacher")),
):
    projects = list_all_projects(db, status)
    return success([_format_project(db, p) for p in projects])


@router.post("/projects/{project_id}/approve", summary="通过作品审核", description="教师端：将指定作品设为审核通过")
def approve(project_id: int, db: Session = Depends(get_db), _: AuthUser = Depends(require_role("teacher"))):
    p = approve_project(db, project_id)
    if not p:
        raise BusinessException(404, "作品不存在")
    return success()


@router.post("/projects/{project_id}/reject", summary="驳回作品", description="教师端：驳回指定作品，需填写驳回原因")
def reject(
    project_id: int,
    data: ProjectReviewAction,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("teacher")),
):
    p = reject_project(db, project_id, data.reason or "")
    if not p:
        raise BusinessException(404, "作品不存在")
    return success()


def _sanitize_filename(name: str) -> str:
    """安全处理文件名，移除路径分隔符、控制字符等危险字符"""
    if not name:
        return "unnamed"
    # 移除路径分隔符、通配符和其他文件系统危险字符
    dangerous = r'\\/:*?"<>|'
    result = []
    for c in str(name):
        code = ord(c)
        # 过滤控制字符（<32，保留常用空白）和 DEL（127）
        if code < 32 or code == 127:
            continue
        if c in dangerous:
            continue
        result.append(c)
    safe = "".join(result).strip(". ")
    return safe if safe else "unnamed"


def _get_project_file_content(db: Session, p: Project) -> tuple[bytes | None, str | None]:
    """获取作品的报告文件内容和 ZIP 内文件名。

    优先通过 report_file_id（新方式）从存储适配器获取文件流；
    降级到 report_url（旧方式）从本地磁盘读取历史文件。

    返回 (content_bytes, inner_zip_name)，文件不存在时返回 (None, None)
    """
    author = db.query(User).filter(User.id == p.author_id).first()
    author_name = author.name if author else str(p.author_id)
    safe_title = _sanitize_filename(p.title)

    # 优先使用 report_file_id → 统一存储
    report_file_id = getattr(p, "report_file_id", None)
    if report_file_id:
        record, stream = resolve_file_stream(db, report_file_id)
        if record and stream:
            try:
                content = stream.read()
                ext = record.extension or Path(record.original_name).suffix or ".pdf"
                inner_name = f"{author_name}_{safe_title}{ext}"
                return content, inner_name
            finally:
                stream.close()

    # 降级到 report_url → 本地历史文件
    report_url = getattr(p, "report_url", "")
    if report_url:
        filename = Path(report_url).name
        if filename:
            upload_dir = Path(settings.local_upload_dir)
            file_path = upload_dir / filename
            if file_path.exists() and file_path.is_file():
                content = file_path.read_bytes()
                ext = file_path.suffix or ".pdf"
                inner_name = f"{author_name}_{safe_title}{ext}"
                return content, inner_name

    return None, None


@router.get("/projects/batch-download", summary="批量下载作品报告", description="教师端：打包下载所有已通过作品的 PDF 报告为 ZIP 文件")
def batch_download_projects(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_role("teacher")),
):
    # 查询已通过的作品（同时支持新 report_file_id 和旧 report_url）
    projects = (
        db.query(Project)
        .filter(Project.status == "approved")
        .filter(
            (Project.report_file_id.isnot(None)) |
            ((Project.report_url != "") & (Project.report_url.isnot(None)))
        )
        .all()
    )

    if not projects:
        raise BusinessException(404, "没有可下载的作品报告")

    # 使用临时文件作为 ZIP 缓冲区（避免全部文件读入内存）
    tmp_path: str | None = None
    file_added = False

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp_path = tmp.name
        tmp.close()  # 关闭文件句柄，保留磁盘文件

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in projects:
                content, inner_name = _get_project_file_content(db, p)
                if content is None:
                    continue
                zf.writestr(inner_name, content)
                file_added = True

        if not file_added:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise BusinessException(404, "没有可下载的作品报告文件")

        # 流式输出：从临时文件分块读取，避免内存中持有完整 ZIP
        # 使用 BackgroundTasks 在响应发送完成后清理临时文件
        file_path = tmp_path

        def _cleanup():
            try:
                os.unlink(file_path)
            except OSError:
                pass

        background_tasks.add_task(_cleanup)

        f = open(file_path, "rb")

        def _chunk_reader():
            try:
                while True:
                    chunk = f.read(64 * 1024)  # 64KB 块
                    if not chunk:
                        break
                    yield chunk
            finally:
                f.close()

        today = datetime.now().strftime("%Y%m%d")
        filename = f"project_reports_{today}.zip"

        return StreamingResponse(
            _chunk_reader(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise
