"""故事线监督 Agent - 6 项固化维度刚性校验,不合格则强制打回。"""
from __future__ import annotations

from typing import Any, Dict, Union

from .base import BaseAgent, parse_json_safe
from ..core.prompts import (
    STORY_SUPERVISOR_SYSTEM,
    STORY_SUPERVISOR_USER_TEMPLATE,
)
from ..storage.persistence import SettingsArchive


class StorySupervisorAgent(BaseAgent):
    name = "story_supervisor"
    role = "故事线监督(刚性)"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, STORY_SUPERVISOR_SYSTEM)

    def run(
        self,
        settings: Union[SettingsArchive, str],
        fine_outline: str,
        text: str,
        prev_summary: str,
    ) -> Dict[str, Any]:
        """对章节正文做 6 维度刚性校验,返回结构化报告(包含 passed 字段)。"""
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        user_prompt = STORY_SUPERVISOR_USER_TEMPLATE.format(
            settings=settings_str,
            fine_outline=fine_outline or "(无)",
            prev_n=2,
            prev_summary=prev_summary or "(无)",
            text=text or "(空)",
        )
        raw = self._ask(user_prompt)
        report = parse_json_safe(raw)
        # 兜底字段
        report.setdefault("passed", False)
        report.setdefault("violations", [])
        report.setdefault("rewrite_instruction", "")
        if not isinstance(report.get("passed"), bool):
            report["passed"] = bool(report.get("passed"))
        if not isinstance(report.get("violations"), list):
            report["violations"] = []
        # 加一记原始文本便于审计
        report["raw"] = raw

        verdict = "通过 ✓" if report["passed"] else "不通过 ✗"
        self.logger.info(
            f"[{self.name}] 第 {fine_outline[:30]}… 校验 {verdict} "
            f"(违规点位 {len(report['violations'])})"
        )
        return report
