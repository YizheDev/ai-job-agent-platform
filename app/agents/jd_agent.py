"""JD 解析与匹配智能体

职责: JD 文本结构化提取, 简历-JD 智能匹配打分, 差异项生成。
匹配权重: 关键词 60% + 工作年限 20% + 学历 20%
"""

from __future__ import annotations

import json
import re

from app.core.config import get_settings
from app.core.exceptions import JDMatchError
from app.core.logger import get_logger
from app.db.crud import JDMatchRecordCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)

_EDUCATION_RANK = {"大专": 1, "本科": 2, "学士": 2, "硕士": 3, "博士": 4, "其他": 0}


def _parse_jd_with_llm(jd_text: str) -> dict:
    """使用 LLM 提取 JD 结构化信息"""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return _parse_jd_basic(jd_text)

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0.1,
            max_tokens=1024,
        )
        prompt = (
            "请从以下岗位描述中提取结构化信息, 仅返回 JSON:\n"
            '{"position":"岗位名称","company":"公司名称",'
            '"required_skills":["技能1","技能2"],'
            '"experience_years":要求工作年限整数,'
            '"education":"学历要求(博士/硕士/本科/大专/不限)",'
            '"responsibilities":["职责1","职责2"],'
            '"keywords":["关键词1","关键词2"],'
            '"salary":"薪资范围"}\n\n'
            f"岗位描述:\n{jd_text[:3000]}"
        )
        response = llm.invoke(prompt)
        content = response.content.strip()
        if "```" in content:
            content = content.split("```json")[-1].split("```")[0].strip() if "```json" in content else content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM JD 解析失败, 降级为基础解析: %s", e)
        return _parse_jd_basic(jd_text)


def _parse_jd_basic(jd_text: str) -> dict:
    """基础 JD 结构提取"""
    struct: dict = {
        "position": "",
        "company": "",
        "required_skills": [],
        "experience_years": 0,
        "education": "不限",
        "responsibilities": [],
        "keywords": [],
        "salary": "",
    }

    edu_map = {"博士": "博士", "硕士": "硕士", "本科": "本科", "大专": "大专"}
    for kw, edu in edu_map.items():
        if kw in jd_text:
            struct["education"] = edu
            break

    years_match = re.search(r"(\d+)\s*[-~至到]\s*(\d+)\s*年", jd_text)
    if years_match:
        struct["experience_years"] = int(years_match.group(1))
    else:
        years_match2 = re.search(r"(\d+)\s*年以上", jd_text)
        if years_match2:
            struct["experience_years"] = int(years_match2.group(1))

    from app.agents.resume_agent import _COMMON_SKILLS

    text_upper = jd_text.upper()
    for skill in _COMMON_SKILLS:
        if skill.upper() in text_upper:
            struct["required_skills"].append(skill)
            struct["keywords"].append(skill)

    return struct


def _calc_keyword_score(resume_skills: list[str], jd_skills: list[str]) -> float:
    """关键词匹配得分 (0~100), 权重 60%"""
    if not jd_skills:
        return 100.0
    resume_upper = {s.upper() for s in resume_skills}
    jd_upper = {s.upper() for s in jd_skills}
    matched = resume_upper & jd_upper
    return (len(matched) / len(jd_upper)) * 100


def _calc_experience_score(resume_years: int, jd_years: int) -> float:
    """工作年限匹配得分 (0~100), 权重 20%"""
    if jd_years <= 0:
        return 100.0
    if resume_years >= jd_years:
        return 100.0
    if resume_years >= jd_years - 1:
        return 70.0
    if resume_years >= jd_years - 2:
        return 40.0
    return 10.0


def _calc_education_score(resume_edu: str, jd_edu: str) -> float:
    """学历匹配得分 (0~100), 权重 20%"""
    if jd_edu in ("不限", ""):
        return 100.0
    r_rank = _EDUCATION_RANK.get(resume_edu, 0)
    j_rank = _EDUCATION_RANK.get(jd_edu, 0)
    if r_rank >= j_rank:
        return 100.0
    if r_rank == j_rank - 1:
        return 60.0
    return 20.0


def _generate_match_details(
    resume_struct: dict, jd_struct: dict
) -> tuple[list[str], list[str], list[str]]:
    """生成匹配项、缺失项、薄弱项"""
    resume_skills = {s.upper() for s in resume_struct.get("skills", [])}
    jd_skills = {s.upper() for s in jd_struct.get("required_skills", [])}

    match_items = [s for s in jd_struct.get("required_skills", []) if s.upper() in resume_skills]
    missing_items = [s for s in jd_struct.get("required_skills", []) if s.upper() not in resume_skills]

    weak_items = []
    resume_years = resume_struct.get("experience_years", 0)
    jd_years = jd_struct.get("experience_years", 0)
    if 0 < resume_years < jd_years:
        weak_items.append(f"工作年限不足 (简历 {resume_years} 年, JD 要求 {jd_years} 年)")

    r_edu_rank = _EDUCATION_RANK.get(resume_struct.get("education", ""), 0)
    j_edu_rank = _EDUCATION_RANK.get(jd_struct.get("education", ""), 0)
    if 0 < r_edu_rank < j_edu_rank:
        weak_items.append(f"学历偏低 (简历 {resume_struct.get('education')}, JD 要求 {jd_struct.get('education')})")

    return match_items, missing_items, weak_items


def jd_match_node(state: JobAgentState) -> dict:
    """JD 解析与匹配节点（LangGraph 工作流节点函数）"""
    jd_text = state.get("jd_text", "")
    resume_struct = state.get("resume_struct", {})
    resume_id = state.get("resume_id")
    logger.info("===== JD 匹配节点启动 =====")

    try:
        if not jd_text or len(jd_text.strip()) < 50:
            raise JDMatchError(details="JD 文本过短, 请输入至少 50 字的岗位描述")

        jd_struct = _parse_jd_with_llm(jd_text)
        logger.info("JD 解析完成: position=%s, skills=%s",
                     jd_struct.get("position"), jd_struct.get("required_skills"))

        resume_skills = resume_struct.get("skills", [])
        jd_skills = jd_struct.get("required_skills", [])
        resume_years = resume_struct.get("experience_years", 0)
        jd_years = jd_struct.get("experience_years", 0)
        resume_edu = resume_struct.get("education", "")
        jd_edu = jd_struct.get("education", "不限")

        kw_score = _calc_keyword_score(resume_skills, jd_skills)
        exp_score = _calc_experience_score(resume_years, jd_years)
        edu_score = _calc_education_score(resume_edu, jd_edu)

        total_score = int(kw_score * 0.6 + exp_score * 0.2 + edu_score * 0.2)
        total_score = max(0, min(100, total_score))

        match_items, missing_items, weak_items = _generate_match_details(resume_struct, jd_struct)

        feedback = []
        if total_score >= 85:
            feedback.append("高匹配: 简历与 JD 高度匹配, 建议直接投递")
        elif total_score >= 60:
            feedback.append("一般匹配: 简历与 JD 部分匹配, 建议优化后投递")
        else:
            feedback.append("低匹配: 简历与 JD 匹配度较低, 建议仔细评估")
        if missing_items:
            feedback.append(f"缺失技能: {', '.join(missing_items[:5])}")
        if weak_items:
            feedback.extend(weak_items)

        company = jd_struct.get("company", "未知公司")
        position = jd_struct.get("position", "未知岗位")

        if resume_id:
            JDMatchRecordCRUD.create(
                resume_id=resume_id,
                jd_text=jd_text[:2000],
                jd_struct=json.dumps(jd_struct, ensure_ascii=False),
                match_score=total_score,
                match_items=json.dumps(match_items, ensure_ascii=False),
                missing_items=json.dumps(missing_items, ensure_ascii=False),
                weak_items=json.dumps(weak_items, ensure_ascii=False),
                user_name=state.get("user_name", ""),
            )

        logger.info("匹配完成: score=%d, matched=%d, missing=%d, weak=%d",
                     total_score, len(match_items), len(missing_items), len(weak_items))
        return {
            "jd_struct": jd_struct,
            "match_score": total_score,
            "match_feedback": feedback,
            "match_items": match_items,
            "missing_items": missing_items,
            "weak_items": weak_items,
            "company": company,
            "position": position,
            "error_code": "",
            "error_msg": "",
        }
    except JDMatchError as e:
        logger.error("JD 匹配失败: %s", e.message)
        return {"error_code": "E002", "error_msg": e.message, "need_human_intervene": False}
    except Exception as e:
        logger.error("JD 匹配异常: %s", e)
        return {"error_code": "E002", "error_msg": f"JD 匹配异常: {e}", "need_human_intervene": False}
