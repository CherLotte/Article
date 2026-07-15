"""配置加载模块 - YAML 配置 + 默认值补齐 + 环境变量加载"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """读取 YAML 配置,缺失字段以默认值补齐。"""
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件 {path} 不存在")

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # ---- 默认值兜底 ----
    cfg.setdefault("project", {})
    cfg["project"].setdefault("name", "novel-pipeline")
    cfg["project"].setdefault("output_dir", "./data")
    cfg["project"].setdefault("log_level", "INFO")

    cfg.setdefault("llm", {})
    cfg["llm"].setdefault("provider", "mock")
    cfg["llm"].setdefault("model", "gpt-4o-mini")
    cfg["llm"].setdefault("temperature", 0.8)
    cfg["llm"].setdefault("max_tokens", 2048)
    cfg["llm"].setdefault("timeout", 60)

    cfg.setdefault("novel", {})
    cfg["novel"].setdefault("title", "未命名小说")
    cfg["novel"].setdefault("target_chapters", 5)
    cfg["novel"].setdefault("words_per_chapter", 1500)
    cfg["novel"].setdefault("style", "叙述流畅,人物丰满")

    cfg.setdefault("pipeline", {})

    # 把 .env 中的环境变量注入到 llm 配置子项,供 create_llm 读取
    cfg["llm"].setdefault("_env", load_env())

    return cfg


def load_env() -> Dict[str, Any]:
    """从 .env 加载环境变量(可选依赖 python-dotenv)。"""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except ImportError:
        pass

    return {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }
