"""剧情评审 Agent - 对通过刚性校验的章节做柔性 0-10 分量化评分。"""
from __future__ import annotations

from typing import Any, Dict, Union

from .base import BaseAgent, parse_json_safe
from ..core.prompts import (
    PLOT_REVIEWER_SYSTEM,
    PLOT_REVIEWER_USER_TEMPLATE,
)
from ..storage.persistence import SettingsArchive


class PlotReviewerAgent(BaseAgent):
    name = "plot_reviewer"
    role = "剧情评审(柔性)"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, PLOT_REVIEWER_SYSTEM)

    def run(
        self,
        settings: Union[SettingsArchive, str],
        fine_outline: str,
        text: str,
        prev_summary: str,
    ) -> Dict[str, Any]:
        """对章节正文做柔性 5 维度评分,返回结构化结果(含 passed_branch 字段)。

        评分分支: >=8 直接定稿; 6-7.9 局部优化; <6 重建创意+正文。
        """
        settings_str = settings.to_json() if isinstance(settings, SettingsArchive) else (settings or "{}")
        user_prompt = PLOT_REVIEWER_USER_TEMPLATE.format(
            settings=settings_str,
            fine_outline=fine_outline or "(无)",
            prev_n=2,
            prev_summary=prev_summary or "(无)",
            text=text or "(空)",
        )
        raw = self._ask(user_prompt)
        review = parse_json_safe(raw)
        review.setdefault("score", 0)
        review.setdefault("breakdown", {})
        review.setdefault("strengths", "")
        review.setdefault("weaknesses", "")
        review.setdefault("next_iteration_suggestions", [])

        try:
            score = float(review.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0

        # 分支判定
        if score >= 8.0:
            branch = "FINALIZE"
        elif score >= 6.0:
            branch = "LOCAL_OPTIMIZE"
        else:
            branch = "REGENERATE"

        review["raw"] = raw
        review["score"] = score
        review["branch"] = branch

        self.logger.info(
            f"[{self.name}] 评分 {score:.1f} → 分支 {branch}"
        )
        return review
