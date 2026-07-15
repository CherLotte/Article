"""小说生成 Agent - 融合「细纲 + 创意亮点 + 前文承接」产出章节正文。"""
from __future__ import annotations

from typing import Union

from .base import BaseAgent
from ..core.prompts import (
    NOVEL_GENERATOR_SYSTEM,
    NOVEL_GENERATOR_USER_TEMPLATE,
)
from ..storage.persistence import SettingsArchive


class NovelGeneratorAgent(BaseAgent):
    name = "novel_generator"
    role = "小说生成 Agent"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, system_prompt="")  # 运行时注入

    def run(
        self,
        settings: Union[SettingsArchive, str],
        chapter_no: int,
        chapter_title: str,
        fine_outline: str,
        creativity: str,
        prev_summary: str,
        prev_review: str = "",
        words: int = 1500,
    ) -> str:
        """生成单章正文,返回字符串。"""
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        sys_prompt = NOVEL_GENERATOR_SYSTEM.format(
            chapter_no=chapter_no,
            chapter_title=chapter_title,
            words=words,
        )
        user_prompt = NOVEL_GENERATOR_USER_TEMPLATE.format(
            settings=settings_str,
            fine_outline=fine_outline or "(无)",
            creativity=creativity or "(无)",
            prev_n=2,
            prev_summary=prev_summary or "(无,这是首章)",
            prev_review=prev_review or "(无)",
        )
        text = self._chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ])
        self.logger.info(
            f"[{self.name}] ✓ 第 {chapter_no} 卷正文初稿生成({len(text)} 字符)"
        )
        return text
