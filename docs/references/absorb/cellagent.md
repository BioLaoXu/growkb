# 吸收笔记：CellAgent（scRNA-seq 三角色闭环）

## 1. 提示词（三角色原文 + 设计手法）
- Planner（src/planner.py:14-40）："你是一名专门从事生物信息学的规划助手。请根据以下信息，为用户的 scRNA-seq 数据分析任务生成详细的任务规划。输出格式为 JSON……"（含数据描述槽位）
- ToolSelector（src/tool_selector.py:16-38）："你是一名专业的生物信息学工具选择专家……可用工具列表：{available_tools}……1、输出的 JSON 格式必须正确 2、选择的工具必须在可用工具列表中 3、selected_tools 是一个列表"
- CodeProgrammer 生成（src/code_programmer.py:13-43）："你是一名专业的生物信息学代码编写专家……历史代码：{historical_code}……人类专家经验：- 预处理中通常需去除低质量细胞和基因并识别高变基因 - 批次效应校正可用 Harmony/Scanorama/scVI 选最佳 - 细胞类型注释用多方法综合评估……输出格式为代码块 ```python 包裹"
- CodeProgrammer 优化（:68-78）："……根据以下信息优化之前编写的代码：评估反馈：{evaluation_feedback}，之前的尝试：{previous_attempts}"
- Evaluator（src/evaluator.py:12-36）："你是一名经验丰富的生物信息学专家。请评估代码执行结果的正确性和合理性并给出改进建议……输出：评估结果：[…] 改进建议：[…] 请勿包含其他内容"

手法总结：① 角色设定+结构化变量槽；② 输出契约显式写在 prompt（JSON schema 或固定段落标题）+ json_utils 首尾花括号切片容错解析；③ CodeProgrammer 内嵌"人类专家经验"条目——领域先验硬编码进 prompt；④ 明确"只给代码不要解释"

## 2. 流程（main.py:68-149）
串行两段式：Planner 一次性产出 steps → 逐步骤循环，无人工介入。每步闭环：ToolSelector 选工具 → CodeProgrammer 生成 → CodeSandbox 执行 → Evaluator 评估 → 不满意 optimize_code 带反馈重写。重试默认 max_attempts=2，步骤含"批次效应校正"提升为 3（难任务加预算）；超次跳过不阻塞。每步重置 local_memory，全局 memory 只留成功代码

## 3. 工具
执行环境=Jupyter Notebook（nbformat+ExecutePreprocessor timeout=600 回写输出，异常转文本）。工具不是函数调用而是"文档注入"：tool_registry 注册 9 个工具名称+一句话描述，选中后把文档文本注入 CodeProgrammer prompt——"代码即工具调用"

## 4. 记忆
双层（src/memory.py 仅 14 行）：GlobalMemory 只存每步最终代码，get_all_code 拼接注入后续步骤（AnnData 靠 Notebook 同 kernel 变量延续）；local_memory 存步骤内 {attempt, code, analysis} 全部尝试。无跨会话持久化

## 5. 护栏
Evaluator 五要素输入（需求/数据/步骤/执行结果），固定段落输出。质量判定极简：is_result_satisfactory 仅文本匹配 "'改进建议' in evaluation and ('无' in evaluation or '暂无' in evaluation)"——对措辞脆弱且同 LLM 自评。执行异常被 CodeSandbox 捕获转文本送评，间接"报错即不通过"

## 6. 可移植清单
1. 三角色 prompt 模板（角色+变量槽+输出契约）→ 开工/收尾会话提示词骨架
2. "人类专家经验"硬编码段 → 开工会话提示词（NGS 黄金实践写为条目）
3. Evaluator 固定段落 + 建议升级为结构化 pass/fail 字段+阈值（替代文本匹配）→ 评分基准
4. 按步骤难度分级重试预算（2→3 次，超限跳过不阻塞）→ 看板"步骤难度/重试列"
5. 双层记忆（全局成功代码+步内尝试历史）→ 收尾会话提示词
6. Notebook 即产物（代码+输出+图回写）→ 产物页天然可审计
