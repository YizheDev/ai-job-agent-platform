"""LangGraph 工作流编排（核心中枢）

完整流程: 简历解析 → JD匹配 → AI优化 → 人工确认 → 风控校验 → 自动化投递 → 结果记录
异常分支: 低匹配度拦截、风控触发、验证码、登录失效、页面改版
支持: 状态持久化、断点续投、人工介入
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.delivery_agent import delivery_node
from app.agents.exception_agent import handle_exception_node
from app.agents.jd_agent import jd_match_node
from app.agents.optimize_agent import optimize_resume_node
from app.agents.resume_agent import parse_resume_node
from app.agents.risk_agent import risk_check_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


# ================================================================
# 路由函数（控制流程走向）
# ================================================================

def _route_after_match(state: JobAgentState) -> str:
    """匹配结果路由: 高分→优化, 低分→记录, 异常→处理"""
    if state.get("error_code"):
        return "handle_exception"
    threshold = get_settings().MATCH_THRESHOLD
    score = state.get("match_score", 0)
    if score >= threshold:
        logger.info("匹配分数 %d >= 阈值 %d, 进入优化环节", score, threshold)
        return "optimize_resume"
    logger.info("匹配分数 %d < 阈值 %d, 终止投递流程", score, threshold)
    return "record_result"


def _route_after_risk(state: JobAgentState) -> str:
    """风控检查路由: 通过→投递, 拦截→记录, 异常→处理"""
    if state.get("error_code"):
        return "handle_exception"
    if state.get("risk_passed", False):
        return "delivery"
    logger.warning("风控拦截: %s", state.get("risk_message", ""))
    return "record_result"


def _route_after_delivery(state: JobAgentState) -> str:
    """投递结果路由: 成功→记录, 异常→处理"""
    if state.get("delivery_status") == "success":
        return "record_result"
    return "handle_exception"


def _route_after_exception(state: JobAgentState) -> str:
    """异常处理路由: 可重试→重新投递, 不可恢复→记录"""
    if state.get("retry", False):
        return "delivery"
    return "record_result"


# ================================================================
# 结果记录节点
# ================================================================

def record_result_node(state: JobAgentState) -> dict:
    """记录投递结果到数据库"""
    company = state.get("company", "未知公司")
    position = state.get("position", "未知岗位")
    position_url = state.get("position_url", "")
    match_score = state.get("match_score", 0)
    resume_id = state.get("resume_id")
    error_code = state.get("error_code", "")
    error_msg = state.get("error_msg", "")

    delivery_status = state.get("delivery_status", "failed")
    if not state.get("risk_passed") and not error_code:
        delivery_status = "cancelled"
    if state.get("match_score", 0) < get_settings().MATCH_THRESHOLD and not error_code:
        delivery_status = "cancelled"

    status_map = {"success": "success", "failed": "failed", "abort": "cancelled"}
    db_status = status_map.get(delivery_status, "error" if error_code else "cancelled")

    try:
        record_id = DeliveryRecordCRUD.create(
            company=company,
            position=position,
            position_url=position_url,
            resume_id=resume_id,
            match_score=match_score,
            status=db_status,
        )
        if error_code:
            DeliveryRecordCRUD.update_status(record_id, db_status, error_code, error_msg)
        logger.info("投递结果已记录: id=%d, company=%s, status=%s", record_id, company, db_status)
        return {"delivery_record_id": record_id, "delivery_status": db_status}
    except Exception as e:
        logger.error("记录投递结果失败: %s", e)
        return {"error_msg": f"记录失败: {e}"}


# ================================================================
# 构建工作流
# ================================================================

def build_workflow():
    """构建完整的 LangGraph 工作流图

    流程节点:
      parse_resume → match_jd → [路由] → optimize_resume → risk_check
      → [路由] → delivery → [路由] → record_result → END

    中断点:
      delivery 节点前暂停, 等待人工确认投递
    """
    graph = StateGraph(JobAgentState)

    # --- 添加节点 ---
    graph.add_node("parse_resume", parse_resume_node)
    graph.add_node("match_jd", jd_match_node)
    graph.add_node("optimize_resume", optimize_resume_node)
    graph.add_node("risk_check", risk_check_node)
    graph.add_node("delivery", delivery_node)
    graph.add_node("record_result", record_result_node)
    graph.add_node("handle_exception", handle_exception_node)

    # --- 设置入口 ---
    graph.set_entry_point("parse_resume")

    # --- 定义边 ---
    graph.add_edge("parse_resume", "match_jd")

    graph.add_conditional_edges("match_jd", _route_after_match, {
        "optimize_resume": "optimize_resume",
        "handle_exception": "handle_exception",
        "record_result": "record_result",
    })

    graph.add_edge("optimize_resume", "risk_check")

    graph.add_conditional_edges("risk_check", _route_after_risk, {
        "delivery": "delivery",
        "handle_exception": "handle_exception",
        "record_result": "record_result",
    })

    graph.add_conditional_edges("delivery", _route_after_delivery, {
        "record_result": "record_result",
        "handle_exception": "handle_exception",
    })

    graph.add_edge("record_result", END)

    graph.add_conditional_edges("handle_exception", _route_after_exception, {
        "delivery": "delivery",
        "record_result": "record_result",
    })

    # --- 编译（带检查点 + 投递前中断） ---
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["delivery"],
    )
    logger.info("LangGraph 工作流编译成功")
    return compiled


def get_workflow_graph_mermaid() -> str:
    """生成工作流 Mermaid 可视化代码"""
    return """graph TD
    A[parse_resume<br/>简历解析] --> B[match_jd<br/>JD匹配打分]
    B -->|分数>=阈值| C[optimize_resume<br/>AI简历优化]
    B -->|分数<阈值| G[record_result<br/>记录结果]
    B -->|异常| F[handle_exception<br/>异常处理]
    C --> D[risk_check<br/>风控校验]
    D -->|通过| E[delivery<br/>自动化投递]
    D -->|拦截| G
    D -->|异常| F
    E -->|成功| G
    E -->|异常| F
    F -->|重试| E
    F -->|终止| G
    G --> H((END))
"""


# 全局工作流单例
_workflow_instance = None


def get_workflow():
    """获取全局工作流实例（单例）"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = build_workflow()
    return _workflow_instance
