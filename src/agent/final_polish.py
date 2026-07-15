"""终稿润色 Agent - 根据评审建议统一文风,产出最终定稿。"""
from __future__ import annotations

from typing import List, Union

from .base import BaseAgent
from ..core.prompts import (
    FINAL_POLISH_SYSTEM,
    FINAL_POLISH_USER_TEMPLATE,
)
from ..storage.persistence import SettingsArchive


class FinalPolishAgent(BaseAgent):
    name = "final_polish"
    role = "终稿润色"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, FINAL_POLISH_SYSTEM)

    def run(
        self,
        text: str,
        style_constraints: Union[List[str], str],
        suggestions: Union[List[str], str] = "",
    ) -> str:
        """对章节正文做最终润色,返回终稿正文。

        style_constraints 既可接受 SettingsArchive.style_constraints 列表(本项目用法),
        也可接受任意字符串。
        """
        if isinstance(style_constraints, list):
            sc_text = "\n".join(f"- {s}" for s in style_constraints)
        else:
            sc_text = style_constraints or "(无)"
        if isinstance(suggestions, list):
            sg_text = "\n".join(f"- {s}" for s in suggestions)
        else:
            sg_text = suggestions or "(无)"

        user_prompt = FINAL_POLISH_USER_TEMPLATE.format(
            style_constraints=sc_text,
            text=text or "(空)",
            suggestions=sg_text,
        )
        polished = self._ask(user_prompt)
        self.logger.info(
            f"[{self.name}] ✓ 终稿润色完成 ({len(polished)} 字符)"
        )
        return polished
