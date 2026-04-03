"""简历解析智能体

职责: PDF/DOCX 简历上传、解析、结构化提取、版本管理。
使用 python-docx 解析 DOCX, PyPDF2 解析 PDF, LLM 提取结构化信息。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from app.core.config import RESUME_DIR, get_settings
from app.core.exceptions import ResumeParseError
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)

# 常见技术技能关键词（降级解析用）
_COMMON_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Git", "CI/CD", "Jenkins", "GitHub Actions",
    "机器学习", "深度学习", "NLP", "计算机视觉", "PyTorch", "TensorFlow",
    "数据分析", "数据挖掘", "Spark", "Hadoop", "Flink",
    "微服务", "分布式", "高并发", "消息队列", "Kafka", "RabbitMQ",
    "产品经理", "项目管理", "Scrum", "敏捷开发",
    "HTML", "CSS", "Sass", "Webpack", "Vite",
]


def _parse_pdf(file_path: str) -> str:
    """解析 PDF 文件提取文本"""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    pages_text = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            pages_text.append(extracted)
    text = "\n".join(pages_text).strip()
    if not text:
        raise ResumeParseError(details="PDF 文件内容为空或无法提取文本")
    return text


def _parse_docx(file_path: str) -> str:
    """解析 DOCX 文件提取文本"""
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise ResumeParseError(details="DOCX 文件内容为空")
    return text


def _extract_structure_with_llm(text: str) -> dict:
    """使用 LLM 提取简历结构化信息"""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        logger.info("未配置 LLM API, 使用基础解析")
        return _extract_structure_basic(text)

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0.1,
            max_tokens=2048,
        )
        prompt = (
            "请从以下简历文本中提取结构化信息, 仅返回 JSON (不要 markdown 代码块):\n"
            '{"name":"姓名","phone":"手机号","email":"邮箱",'
            '"education":"最高学历(博士/硕士/本科/大专/其他)",'
            '"experience_years":工作年限整数,'
            '"skills":["技能1","技能2"],'
            '"work_experience":[{"company":"公司","position":"职位","duration":"时间段","description":"描述"}],'
            '"project_experience":[{"name":"项目名","role":"角色","description":"描述"}],'
            '"education_background":[{"school":"学校","major":"专业","degree":"学历","duration":"时间段"}],'
            '"summary":"个人简介"}\n\n'
            f"简历文本:\n{text[:4000]}"
        )
        response = llm.invoke(prompt)
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1] if content.startswith("```") else content.split("```json")[-1].split("```")[0]
            content = content.strip()
            if content.startswith("json"):
                content = content[4:].strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM 简历解析失败, 降级为基础解析: %s", e)
        return _extract_structure_basic(text)


def _extract_structure_basic(text: str) -> dict:
    """基础简历结构提取（无 LLM 时的降级方案）"""
    struct: dict = {
        "name": "",
        "phone": "",
        "email": "",
        "education": "其他",
        "experience_years": 0,
        "skills": [],
        "work_experience": [],
        "project_experience": [],
        "education_background": [],
        "summary": "",
    }

    phone_match = re.search(r"1[3-9]\d{9}", text)
    if phone_match:
        struct["phone"] = phone_match.group()

    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        struct["email"] = email_match.group()

    edu_map = {"博士": "博士", "硕士": "硕士", "本科": "本科", "学士": "本科", "大专": "大专"}
    for keyword, level in edu_map.items():
        if keyword in text:
            struct["education"] = level
            break

    years_match = re.search(r"(\d+)\s*[年年].*(?:工作|经验|从业)", text)
    if years_match:
        struct["experience_years"] = int(years_match.group(1))

    found_skills = []
    text_upper = text.upper()
    for skill in _COMMON_SKILLS:
        if skill.upper() in text_upper:
            found_skills.append(skill)
    struct["skills"] = found_skills

    lines = text.split("\n")
    if lines:
        first = lines[0].strip()
        if 1 < len(first) <= 6 and not re.search(r"[a-zA-Z@.]", first):
            struct["name"] = first

    return struct


def save_resume_file(file_path: str) -> str:
    """将上传的简历复制到数据目录, 返回目标路径"""
    src = Path(file_path)
    if not src.exists():
        raise ResumeParseError(details=f"文件不存在: {file_path}")

    suffix = src.suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise ResumeParseError(details=f"不支持的文件格式: {suffix}, 仅支持 PDF/DOCX")

    file_size = src.stat().st_size
    if file_size > 10 * 1024 * 1024:
        raise ResumeParseError(details="文件大小超过 10MB 限制")

    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESUME_DIR / src.name
    shutil.copy2(str(src), str(dest))
    logger.info("简历文件已保存: %s -> %s", src.name, dest)
    return str(dest)


def parse_resume_node(state: JobAgentState) -> dict:
    """简历解析节点（LangGraph 工作流节点函数）"""
    resume_path = state.get("resume_path", "")
    logger.info("===== 简历解析节点启动: %s =====", resume_path)

    try:
        path = Path(resume_path)
        if not path.exists():
            raise ResumeParseError(details=f"文件不存在: {resume_path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = _parse_pdf(resume_path)
        elif suffix == ".docx":
            text = _parse_docx(resume_path)
        else:
            raise ResumeParseError(details=f"不支持的格式: {suffix}")

        struct = _extract_structure_with_llm(text)

        resume_id = ResumeCRUD.create(
            file_name=path.name,
            file_path=str(path),
            file_type=suffix.lstrip("."),
            file_size=path.stat().st_size,
            struct_data=json.dumps(struct, ensure_ascii=False),
        )

        logger.info("简历解析成功: name=%s, skills=%s", struct.get("name", ""), struct.get("skills", []))
        return {
            "resume_text": text,
            "resume_struct": struct,
            "resume_id": resume_id,
            "error_code": "",
            "error_msg": "",
        }
    except ResumeParseError as e:
        logger.error("简历解析失败: %s", e.message)
        return {"error_code": "E001", "error_msg": e.message, "need_human_intervene": False}
    except Exception as e:
        logger.error("简历解析异常: %s", e)
        return {"error_code": "E001", "error_msg": f"简历解析异常: {e}", "need_human_intervene": False}
