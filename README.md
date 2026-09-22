# RPG Agent
RPG Agent 是一个基于大语言模型（LLM）的智能角色扮演代理框架。它赋予 NPC 长期记忆、自主决策和动态对话能力，使其能够在开放世界或剧本杀场景中，像真实玩家一样思考、行动与交互。
## 核心特性（未完成）
- 认知架构：基于 ReAct / Plan-and-Solve 范式，支持“观察-思考-行动”闭环。
- 长期记忆：集成向量数据库（如 ChromaDB/Milvus），支持基于语义的历史回忆与关键事件提取。
- 动态人设：支持 System Prompt 动态注入，NPC 性格、语气、目标随剧情阶段自动演变。
- 工具调用：原生支持 Function Calling，可查询游戏数据库、触发战斗、交易物品或改变世界状态。
- 多模态扩展：预留 TTS/STT 及立绘切换接口，支持语音交互与表情差分。

## 代码架构
[用户/游戏引擎] 
```      ️ 
[RPG Agent Core] 
   ├──  LLM Brain (Qwen/GPT-4/Claude)
   ├──  Memory Module (Short-term + Long-term)
   ├── ️ Action Planner (Tool Execution)
   └──  Persona Manager (State & Emotion)
      ️ 
[Game World / Database]
   ├──  task Module
   ├──  inventory Module 
   ├── ️ fight Module
   └──  base Module （important）
```

## 补充情况
### Agent
- LLM Brain已经接入
- Memory 完成世界观生成、剧情编排、怪物设计（后续会更改）
- skill 未接入框架
- 人物剧情线未设计

### Game
- task 生成已完成
- 背包系统 框架搭建完成
- 战斗系统 采用agent生成战斗逻辑（对话操控）
- 基本模块已完成

## 任务清单

> 最后更新：2026-09-22。优先级 P0 = 阻塞跑通，P1 = 打通主流程，P2 = 体验增强。

### P0 先把项目跑起来

- [ ] **修复断掉的 import**：`agent/fight/enemy.py:8`、`agent/fight/battle.py:16`、`agent/web/gamedata.py:5` 仍在引用已删除的 `agent.player.equipment` / `agent.player.player`，实际路径是 `agent/inventory/equip.py` 与 `agent/players/player.py`。当前 `import agent.fight` 直接 `ModuleNotFoundError`。
- [ ] **修复 `agent/memory/world.py` 语法错误**：文件第 3 行 `world_promote = ` 后面没有值，任何解析到它的工具都会报错。补齐世界观 prompt，或先删空占位。
- [ ] **重建 `Player` 类**：`agent/players/player.py` 目前只有一行 `from agent.label.chara import Chara`，战斗、背包、任务三个模块都在等它。至少提供 `RES_NAMES`、`compute_stats()`、装备槽读写。
- [ ] **落实 `agent/inventory/equip.py`**：`Item` / `Bag` / `Equipment` 三个类全是 `pass`，需要与已删除的 `agent/fight/equip.py` 对齐，定义 `EquipmentSlot`、`Rarity`。
- [ ] **恢复 `agent/fight/base.py` 被注释的 `RES_NAMES` import**（第 11-14 行），否则 `BattleUnit` 属性计算抛 `NameError`。
- [ ] **补齐依赖清单**：新增 `requirements.txt`（openai、fastapi、uvicorn、sqlalchemy、aiosqlite、pydantic、email-validator、passlib、python-dotenv、pyyaml 等），并提供 `.env.example`。
- [ ] **补上 `agent/__init__.py`**：现在依赖 PE P420 命名空间包运行，Windows 下容易踩坑。
- [ ] **让 `RPG.py` 有内容**：顶层入口目前是 0 字节空文件，需要一个能真正启动的最小 demo（或 CLI 入口 `python -m agent`）。
- [ ] **修好根目录 `test.py`**：第 1 行 `from agent.label.param import Ability`，但 `param.py` 中没有 `Ability`，直接跑必 `ImportError`。

### P1 打通"玩家—战斗—任务"主链路

- [ ] **修复 `agent/fight/base.py` 状态机制**：`add_status()`（190-205 行）与 `tick_status()`（207-221 行）函数体被整段注释，`return None` / 空 logs，导致中毒、流血、灼烧等持续伤害完全不生效。
- [ ] **补全 `can_act()` 判定**：目前只处理 FREEZE / STUN，漏了 WEAKEN / FRAGILE（见 `base.py:177` 的 `#! need repair` 标记）。
- [ ] **串起战斗与玩家数据**：`Battle.from_player()`、`settle()` 的经验/金币/掉落结算依赖 `Player`，需要联调 `auto_fight()` 跑一次完整回合。
- [ ] **实现 `TaskManager`**：`Task` 单类已可用（`accept` / `complete` / `fail` / `to_dict` / `from_dict`），但缺少任务池、发布/查询/到期检测的容器层；且现有设计只支持 4 人队，多人需重构。
- [ ] **接入游戏时钟**：`agent/memory/timer.py` 已写好 `EventTrigger` / `Event`，接到 `Task` 的 `due_date` 上，让任务真的会过期。
- [ ] **实现背包与仓库**：`web/main.py` 已有 `ItemMove` 接口（backpack / warehouse），但 `agent/inventory/items.py` 还没有对应的容量、堆叠、排序逻辑。
- [ ] **校验天赋系统**：`agent/label/talent.py` 与 `test/test_talent_levelup.py`、`test/test_ability.py` 已存在，跑一遍测试，确认升级与天赋点发放符合预期。

### P2 LLM / Agent 能力

- [ ] **统一 LLM 调用层**：`agent/http/api.py` 中 `API.stream` 声明为 `async def`，`OpenaiApi.stream` 却写成了同步方法；`stream()` 内用 `stream["id"]` 下标访问流式对象；`Responses.content` 取的是 `message.text`（实际是 `.content`）。三处都要修。
- [ ] **补 `Responses` 的流式场景**：`choices` 为 chunk 时结构与 chat.completion 不同，需要区分处理。
- [ ] **把 Skill 系统接进框架**：`agent/memory/skill.py` 的 `SkillsManager` 会去找 `SKILL.md`（大写），而 `agent/tools/` 下的实际文件名是 `skill.md`（小写）；且它需要 YAML Frontmatter 元数据。`skillLoader.read()` 仍是空 `pass`。统一命名与加载时机（懒加载进 System Prompt）。
- [ ] **实现 Function Calling**：目前只有定义好的 LLM 接口，没有 tool registry，也没有把 LLM 输出的工具调用分派到 task / inventory / fight 模块上的执行器。
- [ ] **实现 ReAct 认知循环**：README 宣传的"观察-思考-行动"闭环还没代码，需要一个 Agent 主循环把 Memory + Planner + Tool 串起来。
- [ ] **长期记忆**：`Memory` 现在只是一个 messages 列表 + 写死的 System Prompt。需要切片摘要、关键事件提取、以及向量库（ChromaDB / Milvus）检索接入。
- [ ] **动态人设**：基于剧情阶段自动改写 System Prompt / 语气 / 目标的 `PersonaManager` 尚未开始。

### P3 前端与外围

- [ ] **对齐 Web 前后端**：`agent/web/static/js/app.js` 调用了 12 个 `/api/*` 和 `/ws`，而 `agent/web/main.py` 只有 `/game`、`/auth/register`、`/items/{id}/move`、`/ui/settings` 四个路由，且 `index.html` 没有引用 `app.js`。
- [ ] **修复模板路径**：`Jinja2Templates(directory="templates")` 但传的是 `"agent\web\static\index.html"`，Windows 反斜杠 + 目录不匹配。
- [ ] **补登录/鉴权**：有注册和密码哈希，但没有登录、会话、Token，`/ui/settings` 里还是"取第一条用户"的占位实现。
- [ ] **`agent/web/gamedata.py` 联调**：依赖上述 P0 修复后才能导入，需要定义它对外暴露的世界数据接口。
- [ ] **多模态预留**：TTS / STT、立绘切换、表情差分，目前完全空白，先出接口定义即可。

### 说明
- `agent/config/setting.py:22` 的路径写成 `r".agent/config/labels.json"`（少了斜杠），实际文件在 `agent/config/labels.json`；`SKILLS` 用的是相对路径 `./agent/tools`，依赖 CWD，建议改成基于文件位置的绝对路径。- [ ] 
