"""版本号与 User-Agent 解析。

User-Agent 统一格式为 ``talon-sandbox-python/<version>``，平台后端据此把
createSandbox 请求的来源归类为 ``sdk-python``。版本号从包元数据动态获取，
发版时自动更新，避免硬编码漂移。
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

# 分发包名（见 pyproject.toml [project].name）
_DIST_NAME = "talon-sandbox"


def get_version() -> str:
    """获取已安装分发包的版本号。

    优先读取包元数据（importlib.metadata），这样发版即自动更新；
    源码树未安装时回退到 ``__version__`` 常量，最差兜底为 ``0.0.0``。
    """
    try:
        return _dist_version(_DIST_NAME)
    except PackageNotFoundError:
        # 未作为分发包安装（例如直接从源码树运行）时回退到模块常量
        try:
            from . import __version__  # 延迟导入避免循环

            return __version__
        except Exception:
            return "0.0.0"


def get_user_agent() -> str:
    """规范 User-Agent：``talon-sandbox-python/<version>``。"""
    return f"talon-sandbox-python/{get_version()}"
