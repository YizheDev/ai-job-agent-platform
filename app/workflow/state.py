"""LangGraph 全局共享状态定义

严格遵循技术设计文档的 JobAgentState，所有智能体通过此状态共享数据。
使用 TypedDict(total=False) 使所有字段可选，支持节点增量更新。
"""

from __future__ import annotations

from typing import TypedDict


class JobAgentState(TypedDict, total=False):
    """全局共享状态（所有智能体读写）"""

    # === 用户标识 ===
    user_name: str

    # === 基础输入 ===
    resume_path: str
    jd_text: str
    position_url: str

    # === 人工确认 ===
    user_confirm: bool

    # === 简历解析数据 ===
    resume_text: str
    resume_struct: dict
    resume_id: int

    # === JD 解析数据 ===
    jd_struct: dict
    match_score: int
    match_feedback: list[str]
    match_items: list[str]
    missing_items: list[str]
    weak_items: list[str]

    # === 优化数据 ===
    optimized_resume: str
    optimize_suggestions: list[str]
    cover_letter: str

    # === 投递数据 ===
    company: str
    position: str
    delivery_status: str  # pending / success / failed / abort
    delivery_record_id: int

    # === 风控数据 ===
    risk_passed: bool
    risk_message: str

    # === 异常数据 ===
    error_code: str
    error_msg: str
    need_human_intervene: bool
    retry: bool
