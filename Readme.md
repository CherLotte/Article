# 多 Agent 自动小说创作流水线

> **三层博弈对抗架构** —— 一个解耦合、可扩展的多 Agent 协作框架,用于自动生成多卷本精品小说。  
> 参考「方案三：多Agent博弈对抗方案」(刚性约束 + 柔性提质 + 创意亮点)。

## 特性

- 🎯 **三层博弈对抗**：
  - **第一层 静态规则锁**：GlobalSettingsAgent、OutlineDecomposerAgent — 只读基准
  - **第二层 动态创作**：PlotCreativityAgent、NovelGeneratorAgent — 进攻方
  - **第三层 双层校验**：StorySupervisorAgent(刚性风控 6 项)、PlotReviewerAgent(柔性提质 5 项)
  - **收尾**：FinalPolishAgent
- 🧩 **状态机驱动**：每章依次经过 `STATE_CREATE → STATE_RIGID_CHECK → STATE_FLEX_CHECK → STATE_ITERATE → STATE_FINISH` 等状态
- 🔁 **3 轮迭代上限**：刚 / 柔任一不通过均触发迭代,3 次未达标自动进入 `STATE_MANUAL_REVIEW`
- 🔌 **LLM 可插拔**：内置 `MockLLM`(离线) 与 `OpenAILLM`(兼容 OpenAI / DeepSeek / 智谱 / 通义 / Ollama 等)
- 💾 **JSON + Markdown 双格式**：全局设定档案、章节每次迭代的初稿/评审报告全部持久化
- ⌨️ **CLI 友好**：`--mock`、`--idea`、`--chapters`、`--md`

## 目录结构

```
.
├── main.py                        # CLI 入口
├── config.yaml                    # 配置
├── requirements.txt
├── .env.example
├── README.md
├── background/                    # 用户上传资料目录(使用前请放入 5 份文件)
│   ├── worldview.{json,txt}
│   ├── characters.{json,txt}
│   ├── framework.{json,txt}
│   ├── chapter_outline.{json,txt}
│   ├── style.{json,txt}
│   └── taboos.{json,txt}    # 可选
├── data/                          # 输出
├── src/
│   ├── core/
│   │   ├── config.py              # YAML / .env 配置加载
│   │   ├── llm.py                 # LLM 抽象 + Mock + OpenAI
│   │   ├── memory.py              # 黑板 + 状态机 + 章节状态
│   │   └── prompts.py             # 7 个 Agent 提示词集中管理
│   ├── agents/
│   │   ├── base.py                # BaseAgent + parse_json_safe 工具
│   │   ├── global_settings.py     # 全局设定档案(锁模)
│   │   ├── outline_decomposer.py  # 总纲 / 单章细纲
│   │   ├── plot_creativity.py     # 亮点注入(博弈进攻)
│   │   ├── novel_generator.py     # 章节正文生成
│   │   ├── story_supervisor.py    # 6 项刚性风控
│   │   ├── plot_reviewer.py       # 5 项柔性评分
│   │   └── final_polish.py        # 终稿润色
│   ├── pipeline/
│   │   └── orchestrator.py        # 三层博弈 + 状态机 + 3 轮迭代上限
│   ├── storage/
│   │   ├── persistence.py         # SettingsArchive / Chapter / Novel
│   │   └── background_loader.py   # 读取 background/ 目录
│   └── utils/logger.py
└── tests/
    ├── test_pipeline.py                  # 端到端(LLM 模式)
    └── test_background_integration.py    # 端到端(用户资料模式)
```

## 完整工作流

```
┌── 初始化(只执行 1 次)─────────────────────┐
│  GlobalSettingsAgent.run()  → 锁模设定档案 │
│  OutlineDecomposerAgent.run_total()       │
└────────────────────────────────────────────┘
                    │
                    ▼
┌── 每章循环(最多 3 次迭代)──────────────────┐
│  OutlineDecomposerAgent.run_chapter()     │  STATE_OUTLINE
│             ↓                             │
│  PlotCreativityAgent.run()                │  STATE_CREATE
│  NovelGeneratorAgent.run()                │
│             ↓                             │
│  StorySupervisorAgent.run()  6 项二元判定  │  STATE_RIGID_CHECK
│    ├─ ✗ 不合格 → 携带 rewrite_instruction │
│    │           → iter+1 回 STATE_CREATE  │
│    └─ ✓ 合格 → 进入下一步                 │
│             ↓                             │
│  PlotReviewerAgent.run()  5 项 0-10 分    │  STATE_FLEX_CHECK
│    ├─ ≥8 → FINALIZE                       │
│    ├─ 6-8 → LOCAL_OPTIMIZE(iter+1)        │  STATE_ITERATE
│    └─ <6 → REGENERATE    (iter+1)         │
│             ↓  [退出条件: 3 次迭代上限]   │
│  FinalPolishAgent.run()                   │  STATE_FINISH / STATE_MANUAL_REVIEW
│  - 取最高分版本作为最终稿                  │
│  - 若 STATE_FINISH → 入库                 │
│  - 否则标记 ⚠ 待人工复核                  │
└────────────────────────────────────────────┘
```

## 快速开始

### 0. 安装依赖

```bash
pip install -r requirements.txt
```

> `openai` SDK 仅在你需要真实 LLM 时才用,纯 mock 测试不必安装。

### 1. 无 API Key 试跑

```bash
python main.py --mock --md
```

输出落 `data/<书名>.json` + `.md`。

### 2. 使用真实 LLM

```bash
cp .env.example .env
# 编辑 .env: OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
python main.py --md
```

支持任何 OpenAI 兼容服务：**DeepSeek、智谱、通义、火山、Ollama** 等。

### 3. 用户后台资料驱动模式（推荐用法）⭐

> 用户只需在 `background/` 文件夹下放 5–6 份资料，流水线会优先采用；缺失字段再回退给 LLM 兜底。

5 份必需 + 1 份可选，文件名支持中英文 (如 `世界观.txt` = `worldview.txt`)，扩展名 `.txt` / `.json` 均可：

| 文件名（任一别名） | 内容 | 进入 | 喂给哪个 Agent |
|---|---|---|---|
| `worldview.json/.txt` | 世界观设定（朝代、地缘、阵营、底层规则） | `SettingsArchive.worldview` | `GlobalSettingsAgent` |
| `characters.json/.txt` | 人物档案（姓名/身份/标签/驱动/关系） | `SettingsArchive.characters` | `GlobalSettingsAgent` |
| `framework.json/.txt` | 全局总框架（主线节点列表） | `SettingsArchive.main_plot_nodes` | `GlobalSettingsAgent` |
| `chapter_outline.json/.txt` | 分卷分章大纲（卷名 + 概述） | 直接作为全局大纲 | `OutlineDecomposerAgent` 跳过 LLM 总纲 |
| `style.json/.txt` | 文风规范条目（每行一条） | `SettingsArchive.style_constraints` | `GlobalSettingsAgent` + `FinalPolishAgent` |
| `taboos.json/.txt`（可选） | 禁忌规则 | `SettingsArchive.taboo_rules` | `StorySupervisorAgent` 刚性校验 |

#### 文本格式示例

`characters.txt` 支持 `name | identity | personality_tags` 一行一角色：

```text
萧清晏 | 大曜七公主 | 沉稳,藏锋守拙
谢临渊 | 太傅嫡子,翰林院掌院 | 谋深似海,慧眼识君
```

`chapter_outline.txt` 每行一条：

```text
【第一卷 深宫蛰伏】萧清晏密折揭弊、初露锋芒...
【第二卷 沙场喋血】蛮族南侵,挂帅北征...
```

`framework.txt` / `style.txt` / `taboos.txt` 一样每行一条。

#### JSON 格式示例

```json
// worldview.json
{ "era": "架空古风·景和年间", "geography": "...", "factions": [...], "lore": "..." }
```

```json
// characters.json
[
  {"name": "萧清晏", "identity": "七公主", "personality_tags": ["沉稳"],
   "core_drive": "重塑山河", "relationships": {"谢临渊": "君臣知己"}}
]
```

#### 启用与关闭

```yaml
# config.yaml
pipeline:
  use_background: true      # 默认开启
  background_dir: ./background
```

缺失字段会回退给 LLM：例如只放 4 份资料，仍然能跑，缺的 1 份由 GlobalSettingsAgent 走 LLM 补齐，再与用户资料合并锁模。

### 4. 命令行常用参数

```bash
python main.py \
  --idea "亡国公主与权臣在王朝末世的对弈与共生" \
  --chapters 5 \
  --output ./data \
  --md
```

### 4. 端到端冒烟测试

```bash
python tests/test_pipeline.py
```

## 模块边界与依赖方向

| 层        | 模块                | 职责                          | 依赖                   |
| --------- | ------------------- | ----------------------------- | ---------------------- |
| `core`    | `LLMClient` 协议     | 屏蔽 LLM provider 差异        | 第三方 SDK             |
| `core`    | `SharedMemory`      | 黑板 + 状态机 + 章节状态     | 无                     |
| `core`    | `SettingsArchive`   | 全局只读基准(JSON)           | dataclass             |
| `core`    | `prompts.py`        | 7 个 Agent 提示词             | 无                     |
| `agents`  | `BaseAgent`         | Agent 抽象                    | core                  |
| `agents`  | 7 个具体 Agent       | 完成具体子任务                | BaseAgent              |
| `pipeline`| `NovelPipeline`     | 状态机 + 迭代上限调度          | agents / memory        |
| `storage` | `Novel` / `Chapter` | 结果持久化                    | dataclass              |
| `utils`   | `logger`            | 统一日志                      | 无                     |

依赖方向:**`pipeline → agents → core`**、**`storage → dataclasses`**。

## 扩展指引

- **加新 Agent**：`src/agents/` 新建文件,继承 `BaseAgent`,实现 `run()`;在 `orchestrator.py` 中实例化并调度
- **换 LLM**：实现满足 `LLMClient` 协议的新类,在 `llm.py` 工厂加入分支
- **改提示词**：只动 `src/core/prompts.py`,业务代码零改动
- **换调度策略**：重写 `NovelPipeline._produce_chapter`,例如改成并发调度多个章节
- **接入持久化(数据库)**：把 `Novel.save()` 替换为数据库写入即可

## 异常降级


- **超时 / 调用失败**：自动重试 2 次,失败则保留当前进度 + 异常日志
- **3 次迭代未达标**：标记 `STATE_MANUAL_REVIEW` 并保留最优版本,不阻塞流水线
- **章节缺失亮点**：本框架默认由 LLM 自行生成;若改用 mock,可注入备用创意模板
