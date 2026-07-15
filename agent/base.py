"""Agent 抽象基类 - 所有具体 Agent 继承它。"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..core.llm import LLMClient
from ..core.memory import SharedMemory


def parse_json_safe(text: str) -> Dict[str, Any]:
    """从 LLM 输出中容错提取首个 JSON 对象并解析为 dict。

    处理:首尾说明文字、Markdown 代码块、不闭合引号、空结果。
    解析失败时返回空 dict。
    """
    if not text:
        return {}
    s = text.strip()

    # 去除 ```json ... ``` 包裹
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if m:
        s = m.group(1)

    # 找首个 { 与最后一个 } 进行截取
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    candidate = s[start:end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # 尝试去除控制字符再试
        cleaned = re.sub(r"[\x00-\x1f]", " ", candidate)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


class BaseAgent:
    """Agent 基类:
    - 持有 llm、memory、logger、system_prompt
    - 提供 _ask() / _chat() 内部方法统一封装 LLM 调用
    - 子类必须实现 run() 来完成自己的子任务
    """

    name: str = "base"
    role: str = "通用角色"

    def __init__(
        self,
        llm: LLMClient,
        memory: SharedMemory,
        logger,
        system_prompt: str = "",
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.logger = logger
        self.system_prompt = system_prompt

    # ---------------- LLM 调用封装 ----------------
    def _ask(self, user_prompt: str, **kwargs) -> str:
        """单轮对话:自动附加本 Agent 的 system_prompt。"""
        messages = self._build_messages(user_prompt)
        return self.llm.chat(messages, **kwargs)

    def _chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """多轮对话:调用方完全掌控 messages。"""
        return self.llm.chat(messages, **kwargs)

    def _build_messages(self, user_prompt: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.append({"role": "user", "content": user_prompt})
        return msgs

    # ---------------- 子任务入口 ----------------
    def run(self, *args, **kwargs) -> Any:
        raise NotImplementedError("子类必须实现 run()")
