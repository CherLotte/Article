"""大纲拆解 Agent - 同时承担【总纲】与【单章细纲】两项产出。"""
from __future__ import annotations

from typing import List, Union

from .base import BaseAgent
from ..core.prompts import (
    OUTLINE_DECOMPOSER_SYSTEM_CHAPTER,
    OUTLINE_DECOMPOSER_SYSTEM_TOTAL,
    OUTLINE_DECOMPOSER_USER_CHAPTER,
    OUTLINE_DECOMPOSER_USER_TOTAL,
)
from ..storage.persistence import SettingsArchive


class OutlineDecomposerAgent(BaseAgent):
    name = "outline_decomposer"
    role = "大纲拆解工程师"

    def __init__(self, llm, memory, logger):
        # 注意:总纲与细纲使用不同的系统提示词,系统模板不可在 __init__ 固定。
        super().__init__(llm, memory, logger, system_prompt="")

    # ------------------------- 总纲 -------------------------
    def run_total(self, settings: Union[SettingsArchive, str], style: str, n: int) -> List[str]:
        """生成多卷本的总章节目录,返回每行一条。"""
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        user_prompt = OUTLINE_DECOMPOSER_USER_TOTAL.format(
            settings=settings_str, style=style or "(无)", n=n,
        )
        text = self._chat([
            {"role": "system", "content": OUTLINE_DECOMPOSER_SYSTEM_TOTAL},
            {"role": "user", "content": user_prompt},
        ])
        outline = [line.strip() for line in text.splitlines() if line.strip()]
        self.memory.set("total_outline", outline)
        self.logger.info(f"[{self.name}] ✓ 全局大纲生成 {len(outline)} 条")
        return outline

    # ------------------------- 单章细纲 -------------------------
    def run_chapter(
        self,
        settings: Union[SettingsArchive, str],
        chapter_no: int,
        total_outline_line: str,
        prev_summary: str,
        words: int,
    ) -> str:
        """拆解出某一卷的「单章可执行细纲」文字。"""
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        sys_prompt = OUTLINE_DECOMPOSER_SYSTEM_CHAPTER.format(chapter_no=chapter_no)
        user_prompt = OUTLINE_DECOMPOSER_USER_CHAPTER.format(
            settings=settings_str,
            total_outline_line=total_outline_line,
            chapter_no=chapter_no,
            prev_n=2,
            prev_summary=prev_summary or "(无,这是首章)",
            words=words,
        )
        text = self._chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ])
        self.logger.info(f"[{self.name}] ✓ 第 {chapter_no} 卷细纲已生成 ({len(text)} 字符)")
        return text

    # ---------- 保持与基类协议兼容(只走总纲分支) ----------
    def run(self, settings, style, n, **kwargs):
        return self.run_total(settings, style, n)
