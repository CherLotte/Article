"""端到端冒烟测试 - 用 MockLLM 验证三层博弈对抗流水线可完整跑通。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.config import load_config
from src.core.llm import create_llm
from src.core.memory import (
    STATE_FINISH,
    STATE_MANUAL_REVIEW,
)
from src.utils.logger import setup_logger
from src.pipeline.orchestrator import NovelPipeline
from src.storage.persistence import Novel


def test_pipeline_runs_end_to_end() -> Novel:
    cfg = load_config(str(ROOT / "config.yaml"))
    cfg["llm"]["provider"] = "mock"
    cfg["novel"]["title"] = "测试小说-凤临九霄"
    cfg["pipeline"]["max_iterations_per_chapter"] = 3

    logger = setup_logger(level="INFO")
    llm = create_llm(cfg["llm"])
    pipeline = NovelPipeline(config=cfg, llm=llm, logger=logger)
    novel = pipeline.run()

    # ---- 基本断言 ----
    assert isinstance(novel, Novel), "Novel 应为 Novel 类型"
    assert novel.settings is not None, "应产出全局设定档案"
    assert novel.settings.title, "设定档案 title 不应为空"
    assert len(novel.settings.characters) >= 1, "至少应有 1 位主人物"
    assert novel.total_outline, "应产出总章节目录"
    assert len(novel.chapters) == len(novel.total_outline), \
        "章节数应等于总纲条目数"

    for ch in novel.chapters:
        assert ch.fine_outline, f"第 {ch.chapter_no} 卷应有细纲"
        assert ch.drafts, f"第 {ch.chapter_no} 卷应有初稿"
        assert ch.rigid_reports, f"第 {ch.chapter_no} 卷应有刚性校验报告"
        assert ch.flex_reviews, (
            f"第 {ch.chapter_no} 卷应有柔性评审记录"
        )
        assert ch.final_text, f"第 {ch.chapter_no} 卷应有定稿正文"
        # Mock 默认全通过:应该是 STATE_FINISH
        if not ch.manual_review:
            assert ch.state == STATE_FINISH, \
                f"未标记人工复核时,状态应为 STATE_FINISH, 得到 {ch.state}"

    # 统计
    passed_count = sum(1 for c in novel.chapters if c.state == STATE_FINISH)
    manual_review = sum(1 for c in novel.chapters if c.manual_review)
    logger.info("=" * 60)
    logger.info(
        f"✓ end-to-end test passed | "
        f"通过 {passed_count}/{len(novel.chapters)} | "
        f"人工复核 {manual_review}"
    )
    return novel


if __name__ == "__main__":
    novel = test_pipeline_runs_end_to_end()
    out = ROOT / "data" / "test_novel.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    novel.save(out)
    print(f"\n测试结果已写入: {out}")
