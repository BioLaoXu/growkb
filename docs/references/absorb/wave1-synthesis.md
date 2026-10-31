# Wave 1 吸收综合快报（8 源精读完成，2026-10-31）

> 明细见同目录 8 份笔记。以下为跨源高频模式（按可落地优先级），正式综合报告待 Wave 2/3 完成后合并。

## 跨源共性发现（≥3 个源独立验证的模式，可信度高）

1. **技能=文档+脚本，渐进披露**（OmicsClaw+OpenHands+scientific-agent-skills）：
   系统提示只放一行描述路由，正文按需加载；SKILL.md 描述写"load/skip 双半"
2. **输出契约显式化**（CellAgent+MetaGPT+BixBench）：
   prompt 内写死输出格式（JSON schema 或固定段落标题）+ 解析容错 + 重试修复
3. **事件化留痕**（OpenHands+MetaGPT+OmicsClaw）：
   动作/观察成对同构记录，失败可重放；消息按产生动作类型建索引
4. **评分三梯度**（BixBench+GenoTEX+CellAgent）：
   精确匹配→部分匹配→LLM verifier；"跑失败=0 分"计入总分
5. **记忆=结构化条目+读取不续命**（mem0+OmicsClaw）：
   条目含 created/updated/expiration/hits；去重双层（精确哈希+语义）；冲突编辑不追加
6. **防谎报完成**（OmicsClaw+GenoTEX）：单次只许完成一项；失败记 0 分；agent 输出格式与专家格式同构

## 对六大能力的直接映射（改进提案预告）

- 能力 1 方案科学性 ← OmicsClaw SKILL.md 格式 + GenoTEX 专家格式同构（W1 可落地）
- 能力 2 结果可靠性 ← BixBench 胶囊消毒+三层判分+replica 投票（W1 可落地）
- 能力 3 规范化管理 ← OpenHands 事件契约 + TaskTracker（W1 可落地）
- 能力 4 记忆 RSI ← mem0 条目 schema+四操作规则+score_details（MEMEX 定稿直接引用）
- 能力 5 长任务规划 ← MetaGPT cause_by 订阅 + BioMaster（W2 补充）
- 能力 6 Harness 工具层 ← BioMCP 目录表+中间件管道+SectionSource 溯源（W1 可落地）

## Wave 2/3 需补充的问题

- OpenHands 新版 Agent 循环在 software-agent-sdk 仓（本次只读了前端契约）——W2 可补克隆
- GenoAgent 五角色完整 prompt 未开源——以 GenoTEX 论文附录为准，W3 读论文补
- MobaXterm 场景下 mem0 的 MCP 形态未展开——与 ws_* MCP 化同批评估
