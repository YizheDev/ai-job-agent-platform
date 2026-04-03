"""AI 简历优化智能体

职责: 基于 JD 要求优化简历, 植入关键词, 量化成果, 生成求职信。
依赖 LLM 大模型进行智能优化。
"""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


def _get_llm():
    """获取 LLM 实例"""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise LLMServiceError(details="未配置大模型 API 密钥, 请在系统设置中配置")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )


def _optimize_resume_with_llm(
    resume_text: str,
    jd_text: str,
    missing_items: list[str],
    weak_items: list[str],
) -> dict:
    """使用 LLM 优化简历

    Returns:
        {"optimized_resume": str, "suggestions": list[str]}
    """
    llm = _get_llm()

    missing_str = ", ".join(missing_items) if missing_items else "无"
    weak_str = ", ".join(weak_items) if weak_items else "无"

    prompt = f"""你是一名资深简历优化专家。请根据目标岗位的 JD 要求, 对以下简历进行针对性优化。

优化原则:
1. 在工作经历和项目经历中自然植入 JD 要求的关键技能词汇
2. 将模糊的工作成果量化 (添加具体数字、百分比、规模)
3. 突出与 JD 匹配的经验, 弱化不相关内容
4. 保持简历真实性, 不编造虚假经历
5. 语言精炼专业, 突出核心竞争力

JD 岗位描述:
{jd_text[:2000]}

缺失技能 (JD 要求但简历未提及): {missing_str}
薄弱项: {weak_str}

原始简历:
{resume_text[:3000]}

请返回 JSON 格式 (不要 markdown 代码块):
{{"optimized_resume": "完整的优化后简历文本", "suggestions": ["优化建议1: 说明 + 原因 + 示例", "优化建议2", "优化建议3"]}}"""

    response = llm.invoke(prompt)
    content = response.content.strip()
    if "```" in content:
        content = content.split("```json")[-1].split("```")[0].strip() if "```json" in content else content.split("```")[1].split("```")[0].strip()
    return json.loads(content)


def _generate_cover_letter_with_llm(
    resume_struct: dict, jd_struct: dict
) -> str:
    """使用 LLM 生成求职信 (100~150 字)"""
    llm = _get_llm()
    name = resume_struct.get("name", "求职者")
    position = jd_struct.get("position", "目标岗位")
    skills = ", ".join(resume_struct.get("skills", [])[:5])
    company = jd_struct.get("company", "贵公司")

    prompt = f"""请为以下求职者生成一封简短的求职信 (100~150字):
- 求职者: {name}
- 核心技能: {skills}
- 目标岗位: {company} {position}

要求:
1. 包含个人核心优势
2. 体现与岗位的匹配度
3. 表达求职意愿
4. 语言专业简练, 100~150字
5. 直接返回求职信文本, 不要其他内容"""

    response = llm.invoke(prompt)
    return response.content.strip()


def optimize_resume_node(state: JobAgentState) -> dict:
    """AI 简历优化节点（LangGraph 工作流节点函数）"""
    resume_text = state.get("resume_text", "")
    jd_text = state.get("jd_text", "")
    resume_struct = state.get("resume_struct", {})
    jd_struct = state.get("jd_struct", {})
    missing_items = state.get("missing_items", [])
    weak_items = state.get("weak_items", [])
    resume_id = state.get("resume_id")
    logger.info("===== AI 简历优化节点启动 =====")

    try:
        result = _optimize_resume_with_llm(resume_text, jd_text, missing_items, weak_items)
        optimized = result.get("optimized_resume", resume_text)
        suggestions = result.get("suggestions", [])

        cover_letter = ""
        try:
            cover_letter = _generate_cover_letter_with_llm(resume_struct, jd_struct)
            logger.info("求职信生成成功, 长度=%d", len(cover_letter))
        except Exception as e:
            logger.warning("求职信生成失败: %s", e)

        if resume_id:
            version_count = ResumeCRUD.count_versions(resume_id)
            if version_count < 10:
                position = jd_struct.get("position", "未知岗位")
                ResumeCRUD.create(
                    file_name=f"优化版-{position}",
                    file_path="",
                    file_type="docx",
                    struct_data=json.dumps({"optimized_text": optimized}, ensure_ascii=False),
                    is_original=False,
                    parent_id=resume_id,
                    version_label=f"针对 {position} 优化",
                )

        logger.info("简历优化成功: suggestions=%d, cover_letter=%d字",
                     len(suggestions), len(cover_letter))
        return {
            "optimized_resume": optimized,
            "optimize_suggestions": suggestions,
            "cover_letter": cover_letter,
            "error_code": "",
            "error_msg": "",
        }
    except LLMServiceError as e:
        logger.error("AI 优化失败: %s", e.message)
        return {
            "optimized_resume": resume_text,
            "optimize_suggestions": ["无法连接 AI 服务, 请检查 API 配置"],
            "error_code": "E008",
            "error_msg": e.message,
            "need_human_intervene": False,
        }
    except Exception as e:
        logger.error("简历优化异常: %s", e)
        return {
            "optimized_resume": resume_text,
            "optimize_suggestions": [f"优化过程异常: {e}"],
            "error_code": "E008",
            "error_msg": f"简历优化异常: {e}",
            "need_human_intervene": False,
        }
