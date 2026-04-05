"""DeepSeek API Key 校验工具

真实调用 DeepSeek 接口验证 API Key 合法性。
支持异常分类: 无效Key / 余额不足 / 网络异常 / 服务异常。
校验函数独立封装，可跨模块复用。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


@dataclass
class AuthResult:
    """API Key 校验结果"""

    success: bool
    message: str


def validate_deepseek_api_key(api_key: str) -> AuthResult:
    """校验 DeepSeek API Key 是否有效

    通过发起一次最小化 chat completion 请求验证 Key 合法性。
    捕获全部异常并返回用户友好的错误信息。

    Args:
        api_key: 待校验的 DeepSeek API Key

    Returns:
        AuthResult 包含校验结果 (success) 和提示信息 (message)
    """
    if not api_key or not api_key.strip():
        return AuthResult(success=False, message="请输入 API Key")

    api_key = api_key.strip()

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
            base_url=DEEPSEEK_BASE_URL,
            timeout=15.0,
        )

        client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )

        logger.info("DeepSeek API Key 校验通过")
        return AuthResult(success=True, message="校验通过")

    except AuthenticationError:
        logger.warning("DeepSeek API Key 认证失败")
        return AuthResult(
            success=False, message="API Key 无效或无权限，请检查后重新输入"
        )

    except RateLimitError as e:
        msg = str(e).lower()
        if "insufficient" in msg or "balance" in msg or "quota" in msg:
            logger.warning("DeepSeek 账户余额不足")
            return AuthResult(
                success=False, message="API Key 余额不足，请充值后重试"
            )
        logger.warning("DeepSeek 请求频率超限: %s", e)
        return AuthResult(success=False, message="请求过于频繁，请稍后重试")

    except APIConnectionError:
        logger.error("DeepSeek API 连接失败")
        return AuthResult(
            success=False, message="无法连接 DeepSeek 服务，请检查网络连接"
        )

    except APIStatusError as e:
        logger.error("DeepSeek API 服务异常: status=%s", e.status_code)
        return AuthResult(
            success=False,
            message=f"API 服务异常 (HTTP {e.status_code})，请稍后重试",
        )

    except Exception as e:
        logger.error("DeepSeek API Key 校验未知异常: %s", e)
        return AuthResult(success=False, message=f"校验异常: {e}")
