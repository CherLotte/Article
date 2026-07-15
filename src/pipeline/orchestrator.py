"""流水线编排器 - 三层博弈对抗 + 状态机 + 3 轮迭代上限。

完整流程(严格对应方案原文 5.2 节六大阶段):
    [一] INIT    GlobalSettingsAgent.run()                   一次性
    [一] OUTLINE OutlineDecomposerAgent.run_total()          一次性
    每章循环:
        [一] OUTLINE OutlineDecomposerAgent.run_chapter()
        [二] CREATE  PlotCreativityAgent.run() + NovelGeneratorAgent.run()
        [三] RIGID   StorySupervisorAgent.run()
            ├─ 不合格 → iteration+=1,继续本轮循环(携带重写指令)
            └─ 合格   → 进入 FLEX
        [四] FLEX    PlotReviewerAgent.run()
            ├─ ≥8   → FINALIZE
            ├─ 6-8  → LOCAL_OPTIMIZE(iter+=1,带建议下一轮)
            └─ <6   → REGENERATE(iter+=1)
        [五] ITERATE LIMIT check  (max=3)
            ├─ 超限 → STATE_MANUAL_REVIEW,保留最优版本
            └─ 未超限 → 继续
    [六] FINISH  FinalPolishAgent → 写入 Chapter.final_text
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core.llm import LLMClient
from ..core.memory import (
    STATE_CREATE,
    STATE_FINISH,
    STATE_INIT,
    STATE_ITERATE,
    STATE_MANUAL_REVIEW,
    STATE_OUTLINE,
    STATE_RIGID_CHECK,
    STATE_FLEX_CHECK,
    SharedMemory,
)
from ..agents.global_settings import GlobalSettingsAgent
from ..agents.outline_decomposer import OutlineDecomposerAgent
from ..agents.plot_creativity import PlotCreativityAgent
from ..agents.novel_generator import NovelGeneratorAgent
from ..agents.story_supervisor import StorySupervisorAgent
from ..agents.plot_reviewer import PlotReviewerAgent
from ..agents.final_polish import FinalPolishAgent
from ..storage.background_loader import (
    BackgroundBundle,
    load_background,
)
from ..storage.persistence import Chapter, Novel, SettingsArchive


class NovelPipeline:
    """多 Agent 流水线协调器(三层博弈对抗)。"""

    # 评分分档阈值(可由 config 覆盖)
    SCORE_FINALIZE = 8.0
    SCORE_LOCAL = 6.0

    def __init__(
        self,
        config: Dict[str, Any],
        llm: LLMClient,
        logger,
    ) -> None:
        self.config = config
        self.llm = llm
        self.logger = logger
        self.memory = SharedMemory()

        pipe_cfg = config.get("pipeline", {})
        self.max_iterations = int(
            pipe_cfg.get("max_iterations_per_chapter", 3)
        )
        self.words_per_chapter = int(
            config.get("novel", {}).get("words_per_chapter", 1500)
        )
        self.use_background = bool(
            pipe_cfg.get("use_background", True)
        )
        self.background_dir = pipe_cfg.get("background_dir", "./background")

        # ---- 实例化 7 个 Agent(均基于 BaseAgent) ----
        self.global_settings = GlobalSettingsAgent(
            self.llm, self.memory, self.logger
        )
        self.outline_decomposer = OutlineDecomposerAgent(
            self.llm, self.memory, self.logger
        )
        self.plot_creativity = PlotCreativityAgent(
            self.llm, self.memory, self.logger
        )
        self.novel_generator = NovelGeneratorAgent(
            self.llm, self.memory, self.logger
        )
        self.story_supervisor = StorySupervisorAgent(
            self.llm, self.memory, self.logger
        )
        self.plot_reviewer = PlotReviewerAgent(
            self.llm, self.memory, self.logger
        )
        self.final_polish = FinalPolishAgent(
            self.llm, self.memory, self.logger
        )

    # ========================== 顶层流程 ==========================
    def run(self) -> Novel:
        novel_cfg = self.config["novel"]

        # ---------- 阶段零:尝试从 background/ 加载用户资料 ----------
        bundle: BackgroundBundle = BackgroundBundle()
        if self.use_background:
            bundle = load_background(self.background_dir)
            has_any_background = (
                bundle.worldview is not None
                or bool(bundle.characters)
                or bool(bundle.framework)
                or bool(bundle.style)
            )
            if has_any_background:
                self.logger.info("─" * 60)
                self.logger.info(
                    f"[阶段零 BACKGROUND] 已从 background/ 读取用户资料"
                    f"({len(bundle.loaded_files)}/{6})"
                )
                if bundle.missing:
                    self.logger.warning(
                        f"  · 缺失项,流水线将用 LLM 兜底补齐: "
                        + ", ".join(bundle.missing)
                    )

        # ---------- 阶段一:初始化规则锁模(一次性) ----------
        self.logger.info("─" * 60)
        if bundle.is_complete(require_outline=False):
            self.logger.info(
                "[阶段一 INIT] user-supplied · 用 BackgroundBundle 直接锁定基准(免 LLM)"
            )
            settings = self.global_settings.run_from_bundle(bundle)
        else:
            self.logger.info(
                "[阶段一 INIT] GlobalSettingsAgent · LLM 自动生成设定档案"
            )
            settings = self.global_settings.run(
                genre=novel_cfg.get("genre", ""),
                idea=novel_cfg.get("idea", ""),
                style=novel_cfg.get("style", ""),
            )

        # 优先用 background 提供的标题;否则用 novel.title
        title = settings.title or novel_cfg.get("title", "未命名小说")
        self.memory.set("title", title)

        # ---------- 阶段一 OUTLINE:总章节目录(一次性) ----------
        self.logger.info("─" * 60)
        if bundle.chapter_outline:
            total_outline = list(bundle.chapter_outline)
            self.memory.set("total_outline", total_outline)
            self.logger.info(
                f"[阶段一 OUTLINE] 从 background 直接读入分卷大纲 "
                f"({len(total_outline)} 条,跳过 LLM 总纲生成)"
            )
        else:
            self.logger.info(
                "[阶段一 OUTLINE] OutlineDecomposerAgent · LLM 生成总纲"
            )
            total_outline = self.outline_decomposer.run_total(
                settings=settings,
                style=novel_cfg.get("style", ""),
                n=int(novel_cfg.get("target_chapters", 5)),
            )

        # ---------- 阶段二~六:逐章博弈对抗 ----------
        self.logger.info("─" * 60)
        self.logger.info(
            f"[阶段二~六] 章节循环(共 {len(total_outline)} 章,"
            f"单章最大迭代 {self.max_iterations} 次)"
        )
        chapters: List[Chapter] = []
        for idx, outline_line in enumerate(total_outline):
            chapter = self._produce_chapter(
                idx=idx,
                settings=settings,
                total_outline_line=outline_line,
            )
            chapters.append(chapter)
            self.logger.info("─" * 60)

        # ---------- 装配 Novel ----------
        return Novel(
            title=title,
            subtitle=novel_cfg.get("subtitle", ""),
            settings=settings,
            total_outline=total_outline,
            chapters=chapters,
        )

    # ========================== 单章博弈流程 ==========================
    def _produce_chapter(
        self,
        idx: int,
        settings: SettingsArchive,
        total_outline_line: str,
    ) -> Chapter:
        chapter_no = idx + 1
        chapter_title = self._extract_title(total_outline_line)

        self.logger.info(
            f"▶ 第 {chapter_no} 卷 [{chapter_title}] 开始"
        )

        # 初始化章节状态机
        state = self.memory.init_chapter_state(
            idx=idx,
            chapter_no=chapter_no,
            title=chapter_title,
        )

        # ---- 单章细纲(一次产出) ----
        fine_outline = self.outline_decomposer.run_chapter(
            settings=settings,
            chapter_no=chapter_no,
            total_outline_line=total_outline_line,
            prev_summary=self.memory.previous_summary(2),
            words=self.words_per_chapter,
        )
        state.fine_outline = fine_outline
        state.state = STATE_OUTLINE

        # 章节结果对象(供边迭代边填充)
        ch = Chapter(
            index=idx,
            chapter_no=chapter_no,
            title=chapter_title,
            total_outline_line=total_outline_line,
            fine_outline=fine_outline,
        )

        # ---- 状态机主循环 ----
        iter_count = 0
        last_review_suggestions = ""
        best_score = -1.0
        best_draft = ""
        last_draft = ""

        while iter_count < self.max_iterations:
            iter_count += 1
            ch.iterations = iter_count
            state.iter_count = iter_count
            state.state = STATE_CREATE
            self.logger.info(
                f"   ┣━ [iter {iter_count}/{self.max_iterations}] STATE_CREATE"
            )

            # ---- STATE_CREATE ----
            creativity = self.plot_creativity.run(
                settings=settings,
                fine_outline=fine_outline,
                prev_summary=self.memory.previous_summary(2),
                prev_review=last_review_suggestions,
            )
            state.creativities.append(creativity)

            draft = self.novel_generator.run(
                settings=settings,
                chapter_no=chapter_no,
                chapter_title=chapter_title,
                fine_outline=fine_outline,
                creativity=creativity,
                prev_summary=self.memory.previous_summary(2),
                prev_review=last_review_suggestions,
                words=self.words_per_chapter,
            )
            last_draft = draft
            state.drafts.append(draft)
            ch.drafts.append(draft)

            # ---- STATE_RIGID_CHECK ----
            state.state = STATE_RIGID_CHECK
            rigid = self.story_supervisor.run(
                settings=settings,
                fine_outline=fine_outline,
                text=draft,
                prev_summary=self.memory.previous_summary(2),
            )
            state.rigid_reports.append(rigid)
            ch.rigid_reports.append(rigid)

            if not rigid.get("passed"):
                self.logger.warning(
                    f"   ┣━ ✗ 刚性不通过 iter+1 → 携带指令重写"
                )
                # 把 supervisor 反馈塞进下一轮的 prev_review,引导生成
                last_review_suggestions = (
                    "[刚性打回]"
                    + (rigid.get("rewrite_instruction") or "")
                    + "\n"
                    + self._format_violations(rigid.get("violations"))
                )
                continue

            # ---- STATE_FLEX_CHECK ----
            state.state = STATE_FLEX_CHECK
            flex = self.plot_reviewer.run(
                settings=settings,
                fine_outline=fine_outline,
                text=draft,
                prev_summary=self.memory.previous_summary(2),
            )
            state.flex_reviews.append(flex)
            ch.flex_reviews.append(flex)

            score = float(flex.get("score", 0))
            branch = flex.get("branch", "REGENERATE")
            if score > best_score:
                best_score = score
                best_draft = draft
                state.best_score = best_score
                state.best_draft = best_draft

            # ----- 评分分档判定 -----
            if branch == "FINALIZE":  # ≥8
                self.logger.info(
                    f"   ┣━ ✓ 评分 {score:.1f} ≥ 8 → FINALIZE"
                )
                state.state = STATE_FINISH
                break

            if branch == "LOCAL_OPTIMIZE":  # 6-8
                self.logger.info(
                    f"   ┣━ ↻ 评分 {score:.1f} ∈ [6,8) → LOCAL_OPTIMIZE iter+1"
                )
                state.state = STATE_ITERATE
                last_review_suggestions = self._format_suggestions(flex)
                continue

            # <6 → REGENERATE
            self.logger.info(
                f"   ┣━ ↻ 评分 {score:.1f} < 6 → REGENERATE iter+1"
            )
            state.state = STATE_ITERATE
            last_review_suggestions = self._format_suggestions(flex)
            continue

        # ---- 阶段六:终稿润色 & 存档 ----
        # 取评分最高的版本作为最终 draft;若未达 8 分,标记待人工复核
        final_source = best_draft or last_draft
        ch.best_score = best_score if best_score > 0 else 0.0
        ch.manual_review = (
            state.state != STATE_FINISH
        )

        # 取最后一轮的柔性建议或刚性指令一并喂给润色
        if state.flex_reviews:
            last_suggestions = self._format_suggestions(
                state.flex_reviews[-1]
            )
        else:
            last_suggestions = "(无)"

        polished = self.final_polish.run(
            text=final_source,
            style_constraints=(
                settings.style_constraints if settings else []
            ),
            suggestions=last_suggestions,
        )
        ch.polished.append(polished)
        ch.final_text = polished
        state.final_text = polished

        # 写入 memory(为下一章做承接)
        self.memory.save_polished(idx, polished)

        if ch.manual_review:
            ch.state = STATE_MANUAL_REVIEW
            state.state = STATE_MANUAL_REVIEW
            self.logger.warning(
                f"   ┗━ ⚠ 已达 {self.max_iterations} 次迭代上限,"
                f"标记待人工复核 (最佳评分 {ch.best_score:.1f})"
            )
        else:
            ch.state = STATE_FINISH
            state.state = STATE_FINISH
            self.logger.info(
                f"   ┗━ 🎯 第 {chapter_no} 卷定稿"
                f"(迭代 {iter_count} 次 / 评分 {ch.best_score:.1f})"
            )

        return ch

    # ========================== 工具方法 ==========================
    @staticmethod
    def _extract_title(outline_line: str) -> str:
        if "】" in outline_line:
            head = outline_line.split("】", 1)[0]
            return head.lstrip("【").strip()
        return outline_line.strip()[:32]

    @staticmethod
    def _format_violations(violations: Any) -> str:
        if not isinstance(violations, list) or not violations:
            return ""
        chunks = []
        for v in violations:
            if isinstance(v, dict):
                chunks.append(
                    f"维度:{v.get('dimension','')} 证据:{v.get('evidence','')} "
                    f"问题:{v.get('issue','')} 重写:{v.get('rewrite_hint','')}"
                )
            else:
                chunks.append(str(v))
        return "\n- ".join(chunks)

    @staticmethod
    def _format_suggestions(review: Dict[str, Any]) -> str:
        sug = review.get("next_iteration_suggestions") or []
        if not isinstance(sug, list):
            sug = [str(sug)]
        if not sug:
            # 退而求其次用 weaknesses
            weak = review.get("weaknesses") or ""
            return f"请基于以下不足改进: {weak}" if weak else "(无)"
        return "[柔性评审建议]\n- " + "\n- ".join(str(s) for s in sug)
