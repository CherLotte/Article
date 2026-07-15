"""LLM 抽象层
- 通过 Protocol 定义统一的 LLMClient 接口
- 提供 MockLLM(离线、零依赖)与 OpenAILLM(兼容 OpenAI 协议)两种实现
- 通过工厂方法 create_llm(config) 选择实际实现
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class LLMClient(Protocol):
    """所有 LLM 实现都必须满足此接口。"""

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """对话式调用:传入消息列表,返回模型回复文本。"""
        ...


# ----------------------------------------------------------------- Mock 实现


class MockLLM:
    """本地模拟 LLM,无需任何第三方依赖。

    根据 system prompt 中的"角色标识"分发不同模板响应,便于离线
    调试流水线结构与单元测试。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self.call_count = 0

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        self.call_count += 1
        system = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )

        # 通过 system prompt 的角色关键词做轻量分发
        if "全局设定工程师" in system:
            return self._mock_global_settings()
        if "产出多卷本长篇的总章节目录" in system:
            return self._mock_total_outline()
        if "把总大纲中的某一卷拆解" in system:
            return self._mock_chapter_outline(user)
        if "剧情创意工程师" in system:
            return self._mock_creativity(user)
        if "小说生成 Agent" in system and "融合" in system:
            return self._mock_writer(user)
        if "故事线监督 Agent" in system:
            return self._mock_story_supervisor()
        if "剧情评审 Agent" in system:
            return self._mock_plot_reviewer()
        if "终稿润色 Agent" in system:
            return self._mock_polish(user)

        # 兼容旧关键字
        if "总策划" in system or "产出可执行的章节大纲" in system:
            return self._mock_total_outline()
        if "世界观架构师" in system or "时代背景" in system:
            return self._mock_world()
        if "人物设定师" in system or "主要角色" in system:
            return self._mock_character()
        if "章节撰写 Agent" in system or "扩写出符合风格的章节正文" in system:
            return self._mock_writer(user)
        if "文笔编辑" in system or "润色" in system:
            return self._mock_polish(user)
        if "审稿 Agent" in system or "总评分" in system:
            return self._mock_plot_reviewer()

        return f"[mock #{self.call_count}] " + (user[:80] if user else "")

    # ---- 各角色模板化响应(贴合本项目示例《凤临九霄》) ----
    @staticmethod
    def _mock_global_settings() -> str:
        return (
            "{\n"
            '  "title": "凤临九霄",\n'
            '  "genre": "古风权谋",\n'
            '  "worldview": {\n'
            '    "era": "架空古风,延续百年的大曜王朝,景和年间",\n'
            '    "geography": "中原王朝以京城与北境、西南为关键地缘",\n'
            '    "factions": ["皇室宗亲", "谢氏等百年世族", "北境蛮族", "寒门新贵"],\n'
            '    "lore": "积弊深重的末世王朝,皇权、世家、寒门三方角力"\n'
            '  },\n'
            '  "characters": [\n'
            '    {"name": "萧清晏", "identity": "大曜七公主,后为永安女帝", "personality_tags": ["沉稳", "藏锋守拙", "兼具杀伐与悲悯"], "core_drive": "重塑山河、终结乱局", "relationships": {"谢临渊": "君臣制衡的知己", "先帝": "被猜忌的父皇"}},\n'
            '    {"name": "谢临渊", "identity": "太傅嫡子,翰林院掌院,谢氏暗谍之主", "personality_tags": ["谋深似海", "慧眼识君", "甘为盛世铺路"], "core_drive": "得遇明君、安天下", "relationships": {"萧清晏": "异时空对手与君臣", "萧清晏(后期)": "同心共治"}},\n'
            '    {"name": "二皇子", "identity": "皇室夺嫡势力之一", "personality_tags": ["野心", "结党营私"], "core_drive": "夺嫡", "relationships": {"萧清晏": "构陷主谋"}},\n'
            '    {"name": "三皇子", "identity": "京畿兵权在握的夺嫡势力", "personality_tags": ["跋扈", "刚愎"], "core_drive": "夺嫡", "relationships": {"萧清晏": "视为威胁"}}\n'
            '  ],\n'
            '  "main_plot_nodes": [\n'
            '    "萧清晏蛰伏深宫密折揭弊",\n'
            '    "挂帅北征大破蛮族",\n'
            '    "功高震主流放西南",\n'
            '    "西南蛰伏起兵北上",\n'
            '    "京华定鼎登基永安"\n'
            '  ],\n'
            '  "taboo_rules": [\n'
            '    "严禁出现明确的色情、暴力血腥或政治敏感描写",\n'
            '    "严禁让萧清晏失却藏锋本性、突然成无脑言情女主",\n'
            '    "严禁让任何主线人物做出与其人设标签相悖的言行",\n'
            '    "严禁时间线出现无法解释的跳跃或倒退",\n'
            '    "严禁破坏已确立的世界观与阵营关系"\n'
            '  ],\n'
            '  "style_constraints": [\n'
            '    "沉稳大气、权谋与热血交织",\n'
            '    "对话精炼,多用短句",\n'
            '    "画面感强,场景描写克制而有张力",\n'
            '    "人物弧线丰满,情感克制不滥情"\n'
            '  ],\n'
            '  "timeline_anchor": {"起点": "景和三年暮春", "跨度": "约 5 年至景和八年秋"}\n'
            "}"
        )

    @staticmethod
    def _mock_total_outline() -> str:
        return (
            "【第一卷 深宫蛰伏】亡国公主萧清晏以一纸密折揭发皇子贪腐,与谋臣谢临渊隔空对弈,初露锋芒。\n"
            "【第二卷 沙场喋血】蛮族南侵,萧清晏挂帅北征,以少胜多,一战封神,声震朝野。\n"
            "【第三卷 一朝倾覆】功高震主,遭构陷流放西南,九死一生,与谢临渊达成暗中相护的默契。\n"
            "【第四卷 潜龙在渊】于瘴地开荒屯田、收拢流民,一年后挥师北上,清君侧、平内乱。\n"
            "【第五卷 京华定鼎】兵临京城,登基称帝,改元永安,与谢临渊开启千古君臣制衡。"
        )

    @staticmethod
    def _mock_chapter_outline(user: str) -> str:
        # 提取本章卷名
        first_line = next((ln.strip() for ln in user.splitlines() if ln.strip()), "")
        title = "本卷"
        if "】" in first_line:
            title = first_line.split("】")[0].lstrip("【").strip()
        return (
            f"【{title}】\n"
            f"- 核心剧情: 推进 {title} 的主线,延续前章悬念、揭开本章冲突\n"
            f"- 必须推进的主线进度: 对应全局主线节点之一\n"
            f"- 必含冲突点(1-2 处): 权谋对弈与内心抉择\n"
            f"- 伏笔预留位置: 末尾埋下与下一章呼应的钩子\n"
            f"- 场景氛围: 沉稳克制、画面感强\n"
            f"- 对话风格: 精炼文言、潜台词\n"
            f"- 节奏: 开端冲突 -> 推进 -> 悬念"
        )

    @staticmethod
    def _mock_world() -> str:
        return (
            "大曜王朝:延续百年的古风王朝,景和年间皇室积弊,皇子争储、世家盘踞、边患频仍。\n"
            "朝堂格局:三皇子夺嫡,文官集团中衰,寒门贤才被压制,太傅谢氏掌暗谍而中立。\n"
            "北境:蛮族铁骑虎视眈眈,军备废弛,关中赤野千里。\n"
            "西南:瘴疠之地,流民汇聚,反而成为萧清晏日后起兵的根据地。"
        )

    @staticmethod
    def _mock_character() -> str:
        return (
            "萧清晏:大曜七公主,后为永安女帝。性沉稳,藏锋守拙,兼具帝王杀伐与悲悯之心。\n"
            "谢临渊:太傅嫡子,执掌谢氏百年暗谍。谋深似海,慧眼识君,甘为盛世铺路。\n"
            "二皇子:野心滔天,结党营私,构陷忠良,终被清算。\n"
            "三皇子:手握京畿兵权,跋扈嚣张,兵败自刎。"
        )

    @staticmethod
    def _mock_creativity(user: str) -> str:
        return (
            "亮点 1: 本章中段设置一处权谋反转——某人看似倒戈实为假降,扭转场上力量对比。\n"
            "亮点 2: 主角与谢临渊的隔空对话通过一幅画、一行批注完成,克制而充满张力。\n"
            "合规性说明: 反转人物已在大纲中预埋,新画作与批注属于人物关系互动,不新增主线、不修改人设、不破坏时间线。"
        )

    @staticmethod
    def _mock_writer(user: str) -> str:
        # 截取大纲行作为章首
        first_line = next(
            (ln.strip() for ln in user.splitlines() if ln.strip()), ""
        )
        return (
            f"【{first_line[:60]}】\n\n"
            "暮春三月,紫禁城海棠盛放,落英铺满青砖御道。"
            "萧清晏跪坐窗下,指尖轻抚一卷兵书,眸色静如止水。"
            "她是大曜最不起眼的七公主,生母早逝,偏殿无人问津。\n\n"
            "五年蛰伏,她昼读经史、夜研兵策,将朝堂百官派系、山川地理尽数刻入心底。"
            "今夜,她将借着入宫问安的契机,呈上一纸密折,揭开这场千年棋局的大幕。"
            "而千里之外的翰林院,谢临渊亦无声落子,将她视作乱世布局中唯一的未知。\n\n"
            "烛火摇曳间,一只信鸽掠过夜空,把这一切写进了永安元年之前最长的一段底色。"
        )

    @staticmethod
    def _mock_polish(user: str) -> str:
        body = user.replace("原文:", "").strip() if user.startswith("原文:") else user
        return "[已润色]\n" + body

    @staticmethod
    def _mock_story_supervisor() -> str:
        # 假装本卷通过 6 项刚性校验(mock 默认一切合规)
        return (
            "{\n"
            '  "passed": true,\n'
            '  "violations": [],\n'
            '  "rewrite_instruction": ""\n'
            "}"
        )

    @staticmethod
    def _mock_plot_reviewer() -> str:
        # 假装柔性评审高分(mock 默认 ≥ 8,触发直接定稿分支)
        return (
            "{\n"
            '  "score": 9,\n'
            '  "breakdown": {\n'
            '    "剧情冲突度": 9,\n'
            '    "节奏流畅度": 9,\n'
            '    "细节丰富度": 9,\n'
            '    "情绪表现力": 9,\n'
            '    "剧情吸引力": 9\n'
            '  },\n'
            '  "strengths": "情节推进紧凑,人物刻画细腻,与大纲高度契合。",\n'
            '  "weaknesses": "可加强首段冲突的明示,以更快切入主题。",\n'
            '  "next_iteration_suggestions": ["首段前置一句萧清晏与谋臣隔空对弈的画面"]\n'
            "}"
        )


# ------------------------------------------------------------- OpenAI 实现


class OpenAILLM:
    """OpenAI 兼容 LLM 客户端。"""

    def __init__(self, config: Dict[str, Any]):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "使用 OpenAI provider 需要 openai SDK,请运行 "
                "`pip install openai` 或在 requirements.txt 中启用。"
            ) from e

        env = config.get("_env", {}) or {}
        api_key = env.get("api_key") or config.get("api_key")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY 未设置,请在 .env 中配置或通过环境变量传入。"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=env.get("base_url") or config.get("base_url"),
        )
        self.model = config.get("model") or env.get("model", "gpt-4o-mini")
        self.default_temperature = float(config.get("temperature", 0.8))
        self.default_max_tokens = int(config.get("max_tokens", 2048))

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=(
                temperature if temperature is not None else self.default_temperature
            ),
            max_tokens=max_tokens or self.default_max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


# ----------------------------------------------------------------- 工厂方法


def create_llm(config: Dict[str, Any]) -> LLMClient:
    """根据 config['provider'] 字段返回对应 LLM 实例。"""
    provider = (config.get("provider") or "mock").lower()
    if provider == "openai":
        return OpenAILLM(config)
    return MockLLM(config)
