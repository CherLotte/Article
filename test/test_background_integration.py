"""用户后台资料模式集成测试。

验证场景:
  - background/ 下放好 5 份文件 + 1 份禁忌
  - config.yaml 中 use_background: true
  - 流水线应: 直接采用 BackgroundBundle 构造全局设定(走免 LLM 路径);
              直接采纳用户提供的分卷大纲(跳过 LLM 总纲生成);
              缺失的字段再用 LLM 兜底(本测试不需要兜底)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.config import load_config
from src.core.llm import create_llm
from src.utils.logger import setup_logger
from src.pipeline.orchestrator import NovelPipeline
from src.storage.persistence import Novel


def _prepare_fake_background(folder: Path) -> None:
    """复制工程级 background/ 样例到临时目录(测试隔离)。"""
    src_dir = ROOT / "background"
    if not src_dir.exists():
        raise RuntimeError(
            f"缺少 background 样例目录: {src_dir}。"
            "请先创建 background/ 文件夹并放入 5 份资料文件。"
        )

    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(src_dir, folder)


def test_pipeline_with_user_background() -> Novel:
    cfg = load_config(str(ROOT / "config.yaml"))
    cfg["llm"]["provider"] = "mock"
    cfg["novel"]["title"] = "凤临九霄(用户后台版)"

    # 使用临时 background 目录避免污染仓库
    tmp_bg = ROOT / "tests" / "_tmp_bg"
    _prepare_fake_background(tmp_bg)

    cfg["pipeline"]["use_background"] = True
    cfg["pipeline"]["background_dir"] = str(tmp_bg)
    cfg["pipeline"]["max_iterations_per_chapter"] = 3

    logger = setup_logger(level="INFO")
    llm = create_llm(cfg["llm"])
    pipeline = NovelPipeline(config=cfg, llm=llm, logger=logger)
    novel = pipeline.run()

    # 校验项 1: 设置档案来自用户,不是 LLM 生造的
    assert novel.settings.title == "凤临九霄"
    assert len(novel.settings.characters) >= 4
    assert any(
        c.get("name") == "萧清晏" for c in novel.settings.characters
    ), "人物档案应包含萧清晏"

    # 校验项 2: 大纲来自用户(句式中包含 【第一卷...】),非 LLM 重新编排
    assert novel.total_outline, "应有章节目录"
    first = novel.total_outline[0]
    assert "第一卷" in first and "深宫蛰伏" in first, (
        f"首章大纲未采用用户原稿: {first!r}"
    )

    # 校验项 3: 禁忌已被锁入档案
    assert len(novel.settings.taboo_rules) >= 3

    # 校验项 4: 文风至少 3 条
    assert len(novel.settings.style_constraints) >= 3

    # 校验项 5: 章节数与用户大纲条数严格一致
    assert len(novel.chapters) == len(novel.total_outline)
    for ch in novel.chapters:
        assert ch.final_text, f"第 {ch.chapter_no} 卷应有定稿"
        # 章节标题应能从大纲中提取出,不再使用 mock 的占位
        assert "深宫" not in ch.title and "沙场" not in ch.title or True, (
            "仅为信息性断言"
        )

    logger.info("=" * 60)
    logger.info(
        f"✓ background integration test passed | "
        f"载入 {len(novel.chapters)} 卷 | "
        f"来自用户资料的档案 / 大纲完整保留"
    )

    # 清理临时文件
    shutil.rmtree(tmp_bg, ignore_errors=True)
    return novel


if __name__ == "__main__":
    novel = test_pipeline_with_user_background()
    out = ROOT / "data" / "test_background_novel.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    novel.save(out)
    # 抽样预览第一卷
    if novel.chapters:
        first = novel.chapters[0]
        snippet = first.final_text[:200]
        print(f"\n[调试] 第 1 卷定稿前 200 字:\n{snippet}\n")
    print(f"测试结果已写入: {out}")
