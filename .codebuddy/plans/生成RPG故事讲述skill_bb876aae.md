---
name: 生成RPG故事讲述skill
overview: 在 agent/tools/story/skill.md 中创建一份中文化、两者兼顾的 skill：既是 CodeBuddy 标准 skill（YAML frontmatter + 指令正文），其正文也可直接作为 RPG agent 的讲故事提示词，覆盖故事叙述与怪物设计两大能力。
todos:
  - id: plan-skill-structure
    content: 参考 [skill:skill-creator] 规划 skill.md 结构、frontmatter 元数据与内容大纲
    status: completed
  - id: write-skill-content
    content: 撰写 skill.md 完整中文正文：故事叙述规范、怪物设计模板（属性对齐 param 体系）、JSON 输出格式
    status: completed
    dependencies:
      - plan-skill-structure
  - id: validate-skill
    content: 按 skill-creator 标准校验 skill.md（frontmatter 完整性、命令式风格、storys 目录引用）
    status: completed
    dependencies:
      - write-skill-content
---

## 产品概述
为 RPG agent 项目生成一个"讲 RPG 故事"的 skill 文件（`agent/tools/story/skill.md`）。该文件既符合标准 skill 文件格式（YAML 元数据 + 命令式指令正文），其正文也可直接作为 agent 的讲故事提示词注入 LLM 上下文使用。

## 核心功能
- **故事叙述**：定义世界观/场景构建、剧情推进、NPC 对话、氛围描写的叙述规范，让 agent 持续产出沉浸式冒险故事
- **怪物设计**：定义怪物设计规范（外观、技能、属性），属性命名与项目现有角色属性体系对齐，保证数据可被游戏系统复用
- **结构化输出**：怪物数据提供结构化模板（JSON），输出可解析、可复用
- **故事存档**：约定生成的故事保存至同级 `storys/` 目录，便于积累故事素材

## 技术方案

### 格式标准
采用 CodeBuddy 标准 skill 格式（参考 skill-creator 技能规范），目标文件为 `agent/tools/story/skill.md`（保持现有文件名）：
- YAML frontmatter：`name` + `description` 必填，description 使用第三人称说明触发时机（如"当需要生成 RPG 故事或设计怪物时使用"）
- 正文使用命令式/不定式（动词开头）撰写，避免第二人称
- 正文中文撰写，可直接作为 RPG agent 的讲故事提示词注入 LLM 上下文（与 `agent/memory/memory.py` 现有 DM 定位一致）

### 内容设计
1. **故事叙述规范**：世界观与场景构建、剧情推进节奏、NPC 对话与任务钩子、氛围与感官描写、玩家选择与分支
2. **怪物设计模板**：外观（appearance）、技能（skills）、属性（stats）；属性命名对齐项目 `agent/label/param.py` 体系——基础属性 attack/defense/speed/magic/health、能力属性 communicate/strength/intelligence/luck/dexterity、抗性 bleed/poison/disease/curse/fire/ice/light/dark
3. **结构化输出**：怪物设计提供 JSON 模板，保证输出可解析、可复用
4. **故事存档**：约定生成的故事保存至同级 `storys/` 目录

### 目录结构
```
agent/tools/story/
├── skill.md    # [NEW] RPG 故事叙述与怪物设计 skill（CodeBuddy 标准格式，正文可作 agent 提示词）
└── storys/     # 已有空目录，作为生成故事的存放位置（skill 正文中引用）
```

### 实施约束
- 仅写入 `agent/tools/story/skill.md` 一个文件，不改动任何 Python 代码与其他模块
- 不引入战斗规则等超范围内容，聚焦故事叙述与怪物设计

## Agent 扩展
### Skill
- **skill-creator**
  - 用途：作为创建 skill 的规范来源，指导 skill.md 的 YAML frontmatter 元数据（name/description）、命令式写作风格、资源目录组织方式
  - 预期产出：生成符合 CodeBuddy 标准的 skill.md，并通过 skill-creator 的校验标准（frontmatter 完整性、命名规范、结构要求）检查
