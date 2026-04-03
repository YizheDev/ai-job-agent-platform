"""文件工具类

简历文件操作, PDF 导出, Excel 数据导出, 文件大小格式化。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import DATA_DIR, RESUME_DIR
from app.core.exceptions import FileOperationError
from app.core.logger import get_logger

logger = get_logger(__name__)


def save_uploaded_file(src_path: str) -> str:
    """保存上传的简历文件到数据目录, 返回目标路径"""
    src = Path(src_path)
    if not src.exists():
        raise FileOperationError(details=f"源文件不存在: {src_path}")

    suffix = src.suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise FileOperationError(details=f"不支持的文件格式: {suffix}")

    size = src.stat().st_size
    if size > 10 * 1024 * 1024:
        raise FileOperationError(details="文件大小超过 10MB 限制")

    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESUME_DIR / src.name

    if dest.exists():
        stem = src.stem
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = RESUME_DIR / f"{stem}_{timestamp}{suffix}"

    shutil.copy2(str(src), str(dest))
    logger.info("文件已保存: %s (%.1f KB)", dest.name, size / 1024)
    return str(dest)


def export_resume_text(text: str, name: str = "简历") -> str:
    """导出简历文本为 TXT 文件"""
    export_dir = DATA_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{name}-{date_str}.txt"
    filepath = export_dir / filename
    filepath.write_text(text, encoding="utf-8")
    logger.info("简历导出成功: %s", filepath)
    return str(filepath)


def export_delivery_records_excel(records: list[dict]) -> str:
    """导出投递记录为 Excel 文件"""
    from openpyxl import Workbook

    export_dir = DATA_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = export_dir / f"投递记录-{date_str}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "投递记录"

    headers = ["序号", "公司", "岗位", "岗位链接", "匹配分数", "投递时间", "状态"]
    ws.append(headers)

    for i, record in enumerate(records, 1):
        ws.append([
            i,
            record.get("company", ""),
            record.get("position", ""),
            record.get("position_url", ""),
            record.get("match_score", 0),
            record.get("create_time", ""),
            record.get("status", ""),
        ])

    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col_idx)].width = 18

    wb.save(str(filepath))
    logger.info("投递记录导出成功: %s (%d条)", filepath, len(records))
    return str(filepath)


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def cleanup_exports(days: int = 30) -> int:
    """清理过期导出文件"""
    export_dir = DATA_DIR / "exports"
    if not export_dir.exists():
        return 0
    count = 0
    cutoff = datetime.now().timestamp() - days * 86400
    for f in export_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            count += 1
    if count:
        logger.info("清理过期导出文件: %d 个", count)
    return count
