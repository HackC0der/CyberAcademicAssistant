"""
智能体自动发现与注册
扫描当前目录下所有 .py 文件，返回 BaseAgent 子类列表
"""

import importlib
import inspect
from pathlib import Path

from .base import BaseAgent


def discover_agents() -> list:
    """发现当前目录下所有 BaseAgent 子类"""
    agents = []
    current_dir = Path(__file__).parent

    for py_file in current_dir.glob("*.py"):
        if py_file.name.startswith("_") or py_file.name == "base.py":
            continue

        module_name = f"agents.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseAgent) and obj is not BaseAgent:
                    agents.append(obj)
        except Exception as e:
            print(f"  [警告] 加载智能体模块 {module_name} 失败: {e}")

    return agents
