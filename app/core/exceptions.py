"""统一自定义异常类

严格遵循技术设计文档的异常码定义（E001~E011）。
所有异常继承 JobAgentException 基类，携带异常码、消息、详情。
"""

from __future__ import annotations


class JobAgentException(Exception):
    """智能管家全局基础异常"""

    def __init__(self, code: str, message: str, details: str = ""):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{code}] {message}")


class ResumeParseError(JobAgentException):
    """E001 - 简历解析失败"""

    def __init__(self, message: str = "简历解析失败，请检查文件格式或重新上传", details: str = ""):
        super().__init__("E001", message, details)


class JDMatchError(JobAgentException):
    """E002 - JD匹配失败"""

    def __init__(self, message: str = "JD匹配失败，请检查JD文本或重新上传简历", details: str = ""):
        super().__init__("E002", message, details)


class CaptchaError(JobAgentException):
    """E003 - 验证码触发"""

    def __init__(self, message: str = "检测到验证码，投递已暂停", details: str = ""):
        super().__init__("E003", message, details)


class LoginExpiredError(JobAgentException):
    """E004 - 登录失效"""

    def __init__(self, message: str = "登录已失效，请重新扫码登录", details: str = ""):
        super().__init__("E004", message, details)


class PageChangedError(JobAgentException):
    """E005 - 页面元素失效（平台改版）"""

    def __init__(self, message: str = "页面结构已变更，请使用手动投递", details: str = ""):
        super().__init__("E005", message, details)


class RiskControlError(JobAgentException):
    """E006 - 风控触发"""

    def __init__(self, message: str = "检测到平台风控，当日投递已暂停", details: str = ""):
        super().__init__("E006", message, details)


class DeliveryTimeoutError(JobAgentException):
    """E007 - 投递超时"""

    def __init__(self, message: str = "投递操作超时，请检查网络或重试", details: str = ""):
        super().__init__("E007", message, details)


class LLMServiceError(JobAgentException):
    """E008 - 大模型服务异常"""

    def __init__(self, message: str = "AI服务调用失败，请检查API配置", details: str = ""):
        super().__init__("E008", message, details)


class DatabaseError(JobAgentException):
    """E009 - 数据库操作异常"""

    def __init__(self, message: str = "数据库操作失败", details: str = ""):
        super().__init__("E009", message, details)


class EncryptionError(JobAgentException):
    """E010 - 加密/解密异常"""

    def __init__(self, message: str = "数据加密/解密失败", details: str = ""):
        super().__init__("E010", message, details)


class FileOperationError(JobAgentException):
    """E011 - 文件操作异常"""

    def __init__(self, message: str = "文件操作失败", details: str = ""):
        super().__init__("E011", message, details)
