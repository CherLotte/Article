"""用户后台资料加载器 - 用户只需在 background/ 下放 5 份资料即可驱动流水线。

约定 background/ 文件夹下可出现下列文件(文件名支持中英文,扩展名 .json / .txt / .md):
  - worldview.{txt,json}        → 世界观设定
  - characters.{txt,json}       → 人物档案
  - framework.{txt,json}        → 全局总框架(主线剧情节点)
  - chapter_outline.{txt,json}  → 分卷分章大纲
  - style.{txt,json}            → 文风规范
  - taboos.{txt,json}           → 核心禁忌规则(可选)

解析策略:
  - 同一资料名 .json 优先于 .txt
  - .json 解析失败时自动回退按行解析
  - 找不到的文件不会抛异常,只记录到 bundle.missing,流水线按需回退给 LLM
  - .txt 按行解析;空行 / # 开头 / // 开头 视为注释
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# 文件名候选(支持中英文)
_FILE_ALIASES: Dict[str, List[str]] = {
    "worldview":       ["worldview", "世界观", "世界观设定", "world"],
    "characters":      ["characters", "人物档案", "角色", "人物"],
    "framework":       ["framework", "全局总框架", "总框架", "plot_framework", "main_plot"],
    "chapter_outline": ["chapter_outline", "分卷分章大纲", "分卷大纲", "章节大纲", "outline"],
    "style":           ["style", "文风规范", "文风", "style_guide"],
    "taboos":          ["taboos", "禁忌规则", "禁忌", "taboo_rules"],
}


@dataclass
class BackgroundBundle:
    """用户上传的背景资料包 - 由 load_background() 解析产物。"""
    source_dir: str = ""
    title: str = ""
    worldview: Any = None                              # dict or str
    characters: List[Dict[str, Any]] = field(default_factory=list)
    framework: List[str] = field(default_factory=list)
    chapter_outline: List[str] = field(default_factory=list)
    style: List[str] = field(default_factory=list)
    taboos: List[str] = field(default_factory=list)
    loaded_files: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)

    def is_complete(self, *, require_outline: bool = True) -> bool:
        ok = (
            self.worldview is not None
            and bool(self.characters)
            and bool(self.framework)
            and bool(self.style)
        )
        if require_outline:
            ok = ok and bool(self.chapter_outline)
        return ok

    def summary(self) -> str:
        return (
            f"背景已载入:{len(self.characters)} 位人物 / "
            f"{len(self.framework)} 个主线节点 / "
            f"{len(self.chapter_outline)} 卷大纲 / "
            f"{len(self.style)} 条文风"
            + (f" / {len(self.taboos)} 条禁忌" if self.taboos else "")
        )


# ============================================================ 内部解析器 ============================================================

def _find_file(folder: Path, aliases: List[str]) -> Optional[Path]:
    for name in aliases:
        for ext in (".json", ".txt", ".md"):
            p = folder / (name + ext)
            if p.exists() and p.is_file():
                return p
    return None


def _parse_worldview(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"raw": text}
        except json.JSONDecodeError:
            return {"raw": text}
    # text / md 模式打包到 raw 字段
    return {"raw": text}


def _parse_characters(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [_norm_char(c) for c in data]
            if isinstance(data, dict) and isinstance(data.get("characters"), list):
                return [_norm_char(c) for c in data["characters"]]
        except json.JSONDecodeError:
            pass

    # text 模式:每行一条
    # 支持格式:
    #   "name - identity - tag1,tag2,tag3"
    #   "name | identity | tag1,tag2"
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        parts = [p.strip(" ：:、") for p in s.replace("|", "-").split("-") if p.strip()]
        if len(parts) >= 2:
            entry: Dict[str, Any] = {"name": parts[0], "identity": parts[1]}
            if len(parts) >= 3:
                tags = [
                    t.strip()
                    for t in parts[2].replace("，", ",").split(",")
                    if t.strip()
                ]
                entry["personality_tags"] = tags
            out.append(_norm_char(entry))
        else:
            out.append({"name": s, "identity": "", "personality_tags": []})
    return out


def _norm_char(c: Dict[str, Any]) -> Dict[str, Any]:
    """把人物条目字段标准化,后续 Agent 查找时不踩坑。"""
    return {
        "name": str(c.get("name", "")).strip(),
        "identity": str(c.get("identity", "")).strip(),
        "personality_tags": list(c.get("personality_tags") or []),
        "core_drive": str(c.get("core_drive", "")).strip(),
        "relationships": dict(c.get("relationships") or {}),
    }


def _parse_textlist(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
            if isinstance(data, dict):
                for k in ("items", "lines", "values", "list", "nodes"):
                    if isinstance(data.get(k), list):
                        return [str(x).strip() for x in data[k] if str(x).strip()]
                if isinstance(data.get("text"), str):
                    return _split_lines(data["text"])
            return []
        except json.JSONDecodeError:
            pass

    return _split_lines(text)


def _split_lines(text: str) -> List[str]:
    items: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        # 去除数字前缀 "1. " "1、" 等
        if s and s[0].isdigit() and len(s) > 2 and s[1] in (".", "、", ")"):
            s = s[2:].strip()
        items.append(s)
    return items


# ============================================================ 公开 API ============================================================

def load_background(folder: str | Path) -> BackgroundBundle:
    """扫描 background 文件夹并解析为 BackgroundBundle。

    - 找不到的文件会进入 bundle.missing,不会抛异常
    - 调用方按需决定缺失项是补默认还是回退 LLM
    """
    folder = Path(folder)
    bundle = BackgroundBundle(source_dir=str(folder.resolve()))

    if not folder.exists() or not folder.is_dir():
        bundle.missing = list(_FILE_ALIASES.keys())
        return bundle

    parsers: Dict[str, Callable[[Path], Any]] = {
        "worldview": _parse_worldview,
        "characters": _parse_characters,
        "framework": _parse_textlist,
        "chapter_outline": _parse_textlist,
        "style": _parse_textlist,
        "taboos": _parse_textlist,
    }

    for section, parser in parsers.items():
        path = _find_file(folder, _FILE_ALIASES[section])
        if path is None:
            bundle.missing.append(section)
            continue
        try:
            value = parser(path)
            setattr(bundle, section, value)
            bundle.loaded_files[section] = path.name
        except Exception as exc:
            bundle.missing.append(f"{section}({path.name}: {exc})")

    # 优先用 worldview.json 里的 title
    if isinstance(bundle.worldview, dict):
        t = bundle.worldview.get("title") or bundle.worldview.get("name")
        if t:
            bundle.title = str(t)

    # 兜底标题:用首个人物归档
    if not bundle.title and bundle.characters:
        bundle.title = f"围绕「{bundle.characters[0]['name']}」的故事"

    return bundle
