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
```
