"""LLM API Key 校验工具

真实调用 LLM 接口验证 API Key 合法性。
支持异常分类: 无效Key / 余额不足 / 网络异常 / 服务异常。
校验函数独立封装，可跨模块复用。
使用 Settings 中配置的 LLM_BASE_URL / LLM_MODEL 进行校验。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


@dataclass
class AuthResult:
    """API Key 校验结果"""

    success: bool
    message: str


def validate_api_key(
    api_key: str,
    base_url: str = "",
    model: str = "",
) -> AuthResult:
    """校验 LLM API Key 是否有效

    通过发起一次最小化 chat completion 请求验证 Key 合法性。
    base_url / model 为空时使用 Settings 中的配置，再无则使用默认值。

    Args:
        api_key: 待校验的 API Key
        base_url: LLM API base URL (可选)
        model: LLM 模型名称 (可选)

    Returns:
        AuthResult 包含校验结果 (success) 和提示信息 (message)
    """
    if not api_key or not api_key.strip():
        return AuthResult(success=False, message="请输入 API Key")

    api_key = api_key.strip()

    if not base_url or not model:
        from app.core.config import get_settings
        settings = get_settings()
        base_url = base_url or settings.LLM_BASE_URL or DEFAULT_BASE_URL
        model = model or settings.LLM_MODEL or DEFAULT_MODEL

    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            OpenAI,
            RateLimitError,
        )

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=15.0,
        )

        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )

        logger.info("API Key 校验通过 (base_url=%s, model=%s)", base_url, model)
        return AuthResult(success=True, message="校验通过")

    except AuthenticationError:
        logger.warning("API Key 认证失败")
        return AuthResult(
            success=False, message="API Key 无效或无权限，请检查后重新输入"
        )

    except RateLimitError as e:
        msg = str(e).lower()
        if "insufficient" in msg or "balance" in msg or "quota" in msg:
            logger.warning("账户余额不足")
            return AuthResult(
                success=False, message="API Key 余额不足，请充值后重试"
            )
        logger.warning("请求频率超限: %s", e)
        return AuthResult(success=False, message="请求过于频繁，请稍后重试")

    except APIConnectionError:
        logger.error("LLM API 连接失败 (base_url=%s)", base_url)
        return AuthResult(
            success=False, message="无法连接 LLM 服务，请检查网络连接"
        )

    except APIStatusError as e:
        logger.error("LLM API 服务异常: status=%s", e.status_code)
        return AuthResult(
            success=False,
            message=f"API 服务异常 (HTTP {e.status_code})，请稍后重试",
        )

    except Exception as e:
        logger.error("API Key 校验未知异常: %s", e)
        return AuthResult(success=False, message=f"校验异常: {e}")


# 向后兼容别名
validate_deepseek_api_key = validate_api_key
