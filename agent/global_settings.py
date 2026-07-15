"""全局设定 Agent - 一次性产出《小说全局设定档案》JSON,随后锁模只读。

两条路径:
  - run():        用 LLM 产生设定档案(没有 background 资料时)
  - run_from_bundle(): 直接以 BackgroundBundle 构造(用户上传了 background 时)
"""
from __future__ import annotations

from typing import Any, Dict

from .base import BaseAgent
from ..core.prompts import (
    GLOBAL_SETTINGS_SYSTEM,
    GLOBAL_SETTINGS_USER_TEMPLATE,
)
from ..storage.background_loader import BackgroundBundle
from ..storage.persistence import SettingsArchive


class GlobalSettingsAgent(BaseAgent):
    name = "global_settings"
    role = "全局设定工程师"

    def __init__(self, llm, memory, logger):
        super().__init__(llm, memory, logger, GLOBAL_SETTINGS_SYSTEM)

    # ------------------------------------ 路径 1: LLM 自动生成 ------------------------------------
    def run(
        self,
        genre: str,
        idea: str,
        style: str,
        characters_hint: str = "",
    ) -> SettingsArchive:
        user_prompt = GLOBAL_SETTINGS_USER_TEMPLATE.format(
            genre=genre or "(未指定)",
            characters_hint=characters_hint or "(无)",
            idea=idea or "(无)",
            style=style or "(无)",
        )
        raw = self._ask(user_prompt)
        archive = SettingsArchive.from_json(raw)
        if not archive.title:
            archive.title = "未命名小说"

        self.memory.save_settings(archive.to_json())
        self.memory.set("title", archive.title)
        self.logger.info(
            f"[{self.name}] ✓ 全局设定档案生成并已锁模 "
            f"(主人物 {len(archive.characters)} 位,禁忌 {len(archive.taboo_rules)} 条)"
        )
        return archive

    # ------------------------------------ 路径 2: 从 BackgroundBundle 加载 ------------------------------------
    def run_from_bundle(self, bundle: BackgroundBundle) -> SettingsArchive:
        """不调 LLM,直接将 BackgroundBundle 转为 SettingsArchive 并锁模。"""
        # worldview: 用户可能在 .json 中给出结构化字段,也可能只给一段 raw 文本
        wv = bundle.worldview
        worldview_dict: Dict[str, Any] = {}
        if isinstance(wv, dict):
            worldview_dict = {
                "era": str(wv.get("era", "")),
                "geography": str(wv.get("geography", "")),
                "factions": list(wv.get("factions") or []),
                "lore": str(wv.get("lore", "") or wv.get("raw", "")),
                "raw": str(wv.get("raw", "")),
            }
        else:
            worldview_dict = {
                "era": "", "geography": "", "factions": [], "lore": str(wv or ""),
                "raw": str(wv or ""),
            }

        archive = SettingsArchive(
            title=bundle.title or "未命名小说",
            genre="",
            worldview=worldview_dict,
            characters=list(bundle.characters),
            main_plot_nodes=list(bundle.framework),
            taboo_rules=list(bundle.taboos),
            style_constraints=list(bundle.style),
            timeline_anchor={},
        )

        # 写入 memory(锁模)
        self.memory.save_settings(archive.to_json())
        self.memory.set("title", archive.title)
        self.logger.info(
            f"[{self.name}] ✓ 用户后台资料已锁模 "
            f"({len(archive.characters)} 位 / {len(archive.main_plot_nodes)} 节点 / "
            f"{len(archive.taboo_rules)} 禁忌 / {len(archive.style_constraints)} 文风)"
        )
        return archive
