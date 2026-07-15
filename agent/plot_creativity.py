"""剧情创意 Agent - 在不破坏设定的前提下为本章注入亮点(博弈增益方)。"""
from __future__ import annotations

from typing import Union

from .base import BaseAgent
from ..core.prompts import (
    PLOT_CREATIVITY_SYSTEM,
    PLOT_CREATIVITY_USER_TEMPLATE,
)
from ..storage.persistence import SettingsArchive


class PlotCreativityAgent(BaseAgent):
    name = "plot_creativity"
    role = "剧情创意工程师"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, PLOT_CREATIVITY_SYSTEM)

    def run(
        self,
        settings: Union[SettingsArchive, str],
        fine_outline: str,
        prev_summary: str,
        prev_review: str = "",
    ) -> str:
        """产出 2 处亮点 + 合规性说明,返回纯文本。"""
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        user_prompt = PLOT_CREATIVITY_USER_TEMPLATE.format(
            settings=settings_str,
            fine_outline=fine_outline or "(无)",
            prev_n=2,
            prev_summary=prev_summary or "(无,这是首章)",
            prev_review=prev_review or "(无)",
        )
        text = self._ask(user_prompt)
        self.logger.info(
            f"[{self.name}] ✓ 创意亮点方案({len(text)} 字符)"
        )
        return text
