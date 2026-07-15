"""数据持久化 - Novel / SettingsArchive / Chapter 数据类 + JSON 与 Markdown 导出。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SettingsArchive:
    """全局只读设定档案 - 由 GlobalSettingsAgent 一次写入,全程锁模。

    字段直接对应 prompts.GLOBAL_SETTINGS_SYSTEM 中的 JSON Schema。
    """
    title: str = ""
    genre: str = ""
    worldview: Dict[str, Any] = field(default_factory=dict)
    characters: List[Dict[str, Any]] = field(default_factory=list)
    main_plot_nodes: List[str] = field(default_factory=list)
    taboo_rules: List[str] = field(default_factory=list)
    style_constraints: List[str] = field(default_factory=list)
    timeline_anchor: Dict[str, Any] = field(default_factory=dict)

    # ---------- JSON 序列化 ----------
    @classmethod
    def from_json(cls, raw: str) -> "SettingsArchive":
        """从 LLM 输出(或 mock 输出)的 JSON 字串安全解析。"""
        # 容错提取首个 {...} 块
        s = raw.strip()
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return cls()
        try:
            data = json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            return cls()
        return cls(
            title=str(data.get("title", "")),
            genre=str(data.get("genre", "")),
            worldview=data.get("worldview") or {},
            characters=list(data.get("characters") or []),
            main_plot_nodes=list(data.get("main_plot_nodes") or []),
            taboo_rules=list(data.get("taboo_rules") or []),
            style_constraints=list(data.get("style_constraints") or []),
            timeline_anchor=data.get("timeline_anchor") or {},
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


@dataclass
class Chapter:
    """单章结果 - 含所有迭代轮次与终稿。"""
    index: int
    chapter_no: int
    title: str
    total_outline_line: str = ""
    fine_outline: str = ""
    iterations: int = 0
    state: str = "STATE_INIT"
    manual_review: bool = False
    best_score: float = -1.0

    # 每轮的产物
    drafts: List[str] = field(default_factory=list)
    polished: List[str] = field(default_factory=list)         # 与 drafts 同步,每轮一次终稿润色
    rigid_reports: List[Dict[str, Any]] = field(default_factory=list)
    flex_reviews: List[Dict[str, Any]] = field(default_factory=list)
    final_text: str = ""

    @property
    def passed(self) -> bool:
        return self.state == "STATE_FINISH" and bool(self.final_text)


@dataclass
class Novel:
    """完整小说产物。"""
    title: str
    subtitle: str = ""
    settings: Optional[SettingsArchive] = None

    # 总章节目录
    total_outline: List[str] = field(default_factory=list)

    # 章节列表(按章序号)
    chapters: List[Chapter] = field(default_factory=list)

    # ---------- JSON 持久化 ----------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "title": self.title,
            "subtitle": self.subtitle,
            "settings": asdict(self.settings) if self.settings else None,
            "total_outline": self.total_outline,
            "chapters": [asdict(c) for c in self.chapters],
        }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "Novel":
        data = json.loads(path.read_text(encoding="utf-8"))
        settings_data = data.pop("settings", None)
        settings = SettingsArchive(**settings_data) if settings_data else None
        chapters_data = data.pop("chapters", [])
        novel = cls(**data, settings=settings)
        novel.chapters = [Chapter(**c) for c in chapters_data]
        return novel

    # ---------- Markdown 导出 ----------
    def to_markdown(self) -> str:
        parts: List[str] = [f"# {self.title}"]
        if self.subtitle:
            parts.append(f"## {self.subtitle}")
        parts.append("")

        if self.settings:
            parts.append("## 全局设定档案")
            parts.append(self.settings.to_json())
            parts.append("")

        if self.total_outline:
            parts.append("## 全文大纲")
            for i, line in enumerate(self.total_outline, 1):
                parts.append(f"{i}. {line}")
            parts.append("")

        for ch in self.chapters:
            parts.append(f"## {ch.title}")
            if ch.manual_review:
                parts.append("> ⚠ 本章因 3 次迭代未达标已标记**待人工复核**")
            content = ch.final_text or (ch.polished[-1] if ch.polished else "")
            parts.append(content)
            parts.append("")

        return "\n".join(parts)

    def save_markdown(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
