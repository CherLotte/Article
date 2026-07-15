"""多 Agent 自动小说创作流水线 - CLI 入口"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让 src/ 内的包可被 import
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.core.config import load_config
from src.core.llm import create_llm
from src.utils.logger import setup_logger
from src.pipeline.orchestrator import NovelPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多 Agent 自动小说创作流水线")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--mock", action="store_true",
                        help="使用本地模拟 LLM（无需 API Key）")
    parser.add_argument("--idea", help="覆盖配置文件中的创意种子")
    parser.add_argument("--chapters", type=int, help="目标章节数")
    parser.add_argument("--output", help="输出目录")
    parser.add_argument("--md", action="store_true", help="同时导出 Markdown")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    # 命令行参数覆盖配置
    if args.mock:
        cfg["llm"]["provider"] = "mock"
    if args.idea:
        cfg["novel"]["idea"] = args.idea
    if args.chapters:
        cfg["novel"]["target_chapters"] = args.chapters
    if args.output:
        cfg["project"]["output_dir"] = args.output

    logger = setup_logger(level=cfg["project"].get("log_level", "INFO"))
    logger.info("=" * 60)
    logger.info("多 Agent 自动小说创作流水线启动")
    logger.info(f"  作品 :《{cfg['novel'].get('title', '未命名')}》")
    logger.info(f"  体裁 :{cfg['novel'].get('genre', '-')}")
    logger.info(f"  章节 :{cfg['novel'].get('target_chapters', '-')}")
    logger.info(f"  LLM  :{cfg['llm'].get('provider')} ({cfg['llm'].get('model')})")
    logger.info("=" * 60)

    llm = create_llm(cfg["llm"])
    pipeline = NovelPipeline(config=cfg, llm=llm, logger=logger)

    try:
        novel = pipeline.run()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"流水线执行异常: {e}")
        sys.exit(1)

    # 持久化
    out_dir = Path(cfg["project"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{novel.title}.json"
    novel.save(json_path)
    logger.info(f"✓ 小说已保存至: {json_path}")

    if args.md:
        md_path = out_dir / f"{novel.title}.md"
        novel.save_markdown(md_path)
        logger.info(f"✓ Markdown 已导出: {md_path}")


if __name__ == "__main__":
    main()
