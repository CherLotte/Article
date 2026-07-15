"""跨 Agent 共享记忆 - 黑板式 KV + 章节状态机 + 全局只读设定档案。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class ChapterState:
    """单章运行状态机数据,记录每轮的创作/校验/迭代历史。"""

    def __init__(self) -> None:
        self.index: int = -1
        self.chapter_no: int = 0
        self.title: str = ""
        self.fine_outline: str = ""                # 单章细纲
        self.creativities: List[str] = []          # 每一轮的亮点方案
        self.drafts: List[str] = []                # 每一轮的生成稿
        self.rigid_reports: List[Dict[str, Any]] = []
        self.flex_reviews: List[Dict[str, Any]] = []
        self.best_score: float = -1.0
        self.best_draft: str = ""
        self.iter_count: int = 0
        self.state: str = "STATE_INIT"             # 见 STATE_* 常量
        self.final_text: str = ""                  # 终稿润色后的正文
        self.manual_review: bool = False           # 是否需要人工复核

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterState":
        s = cls()
        s.__dict__.update(data)
        return s


# 状态机常量(参考方案原文 5.4 节)
STATE_INIT          = "STATE_INIT"          # 初始化规则锁模
STATE_OUTLINE       = "STATE_OUTLINE"       # 总/细纲产出
STATE_CREATE        = "STATE_CREATE"        # 内容创意生成
STATE_RIGID_CHECK   = "STATE_RIGID_CHECK"   # 刚性合规校验
STATE_FLEX_CHECK    = "STATE_FLEX_CHECK"    # 柔性质量评审
STATE_ITERATE       = "STATE_ITERATE"       # 迭代优化中
STATE_FINISH        = "STATE_FINISH"        # 章节定稿完成
STATE_MANUAL_REVIEW = "STATE_MANUAL_REVIEW" # 迭代超限,人工复核


class SharedMemory:
    """轻量级"黑板":Agent 通过 set/get 存取共享上下文。"""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        # 只读基准:全局设定档案(JSON 字串)
        self._settings_archive: Optional[str] = None
        # 章节状态机
        self._chapter_states: Dict[int, ChapterState] = {}

    # ---------------------------- 基础 KV ----------------------------
    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    # ---------------------------- 全局只读设定 ----------------------------
    def save_settings(self, settings_json: str) -> None:
        """保存全局设定档案(JSON 字串),一经写入不予修改。"""
        if self._settings_archive is not None:
            return  # 锁定:不准覆写
        self._settings_archive = settings_json

    def get_settings(self) -> Optional[str]:
        return self._settings_archive

    # ---------------------------- 章节状态 ----------------------------
    def init_chapter_state(
        self,
        idx: int,
        chapter_no: int,
        title: str,
    ) -> ChapterState:
        s = ChapterState()
        s.index = idx
        s.chapter_no = chapter_no
        s.title = title
        s.state = STATE_INIT
        self._chapter_states[idx] = s
        return s

    def get_chapter_state(self, idx: int) -> Optional[ChapterState]:
        return self._chapter_states.get(idx)

    # ---------------------------- 兼容旧接口 ----------------------------
    def save_draft(self, idx: int, text: str) -> None:
        """兼容旧版接口,实际写入 ChapterState.drafts。"""
        s = self.get_chapter_state(idx)
        if s is not None:
            s.drafts.append(text)

    def get_draft(self, idx: int) -> Optional[str]:
        s = self.get_chapter_state(idx)
        return s.drafts[-1] if s and s.drafts else None

    def save_polished(self, idx: int, text: str) -> None:
        s = self.get_chapter_state(idx)
        if s is not None:
            s.final_text = text

    def get_polished(self, idx: int) -> Optional[str]:
        s = self.get_chapter_state(idx)
        return s.final_text if s else None

    def add_review(self, idx: int, review: Dict[str, Any]) -> None:
        # 默认加到柔性评审,具体由调用方控制
        s = self.get_chapter_state(idx)
        if s is not None:
            s.flex_reviews.append(review)

    def get_reviews(self, idx: int) -> List[Dict[str, Any]]:
        s = self.get_chapter_state(idx)
        return list(s.flex_reviews) if s else []

    # ---------------------------- 上下文生成 ----------------------------
    def previous_summary(self, n: int = 3) -> str:
        """拼接最近 n 章的终稿末尾承接摘要。"""
        if not self._chapter_states:
            return "(无,这是开篇第一卷)"
        chunks: List[str] = []
        indices = sorted(self._chapter_states.keys())
        last_n = indices[-n:] if n > 0 else []
        for i in last_n:
            s = self._chapter_states[i]
            if s.final_text:
                tail = s.final_text[-400:] if len(s.final_text) > 400 else s.final_text
                chunks.append(f"[第 {s.chapter_no} 卷 {s.title} 末尾] {tail}")
        return "\n\n".join(chunks) if chunks else "(无前文)"

    # ---------------------------- 序列化 ----------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "store": self._store,
            "settings_archive": self._settings_archive,
            "chapter_states": {
                k: v.to_dict() for k, v in self._chapter_states.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedMemory":
        mem = cls()
        mem._store = data.get("store", {})
        mem._settings_archive = data.get("settings_archive")
        states = data.get("chapter_states", {})
        for k, v in states.items():
            mem._chapter_states[int(k)] = ChapterState.from_dict(v)
        return mem
