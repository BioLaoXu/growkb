# 吸收笔记：Biomni（斯坦福，Know-How 经验库 + 检索增强规划）

## 1. 提示词
- 核心系统提示内嵌 biomni/agent/a1.py（L1098-1143）：任务规划采用"勾选清单状态机"——`1. [ ] First step`→完成 `[✓]`，失败 `[✗] (failed because...)`，且"Always show the updated plan after each step"（L1102-1119）
- 行动协议：每轮必含 <execute> 或 <solution> 二选一，多语言代码用 #!R/#!BASH 前缀标记（L1124-1142）
- Know-How 注入提示（L1173-1186）："📚 KNOW-HOW DOCUMENTS (BEST PRACTICES & PROTOCOLS - ALREADY LOADED)"——全文预载而非按需检索；检索增强路径另见 retriever.py
- 防幻觉约束（L1152-1155）：生成实验协议时"ONLY include information found in these resources... Prioritize accuracy over completeness"
- Know-How 文档本身即"过程性提示词"：biomni/know_how/sgRNA_design_guide.md（L44）："You MUST complete BOTH Method 1 AND Method 2 before proceeding to Option 2"

## 2. 流程
- LangGraph 式状态机：state["next_step"] ∈ {generate, execute, end}，由解析结果驱动（a1.py L1438-1443），go()（L1759）主循环
- 重试：解析失败自动附加纠错消息（L1461-1468）；错误计数≥2 次终止对话（L1451-1460）；解析器对未闭合标签自动补全（L1415-1420），兼容 ``` 代码块回退（L1428-1433）

## 3. 工具
- 注册 schema 极简：必填 name/description/required_parameters（biomni/tool/tool_registry.py L32-34），校验失败抛错；支持 pickle 序列化（L79-89）；工具即 Python 函数按学科分 20+ 模块（genomics.py 110KB 等），docstring+签名即接口；另有 MCP 扩展（docs/mcp_integration.md）

## 4. 记忆
Know-How 经验库：biomni/know_how/loader.py。每篇 md schema：一级标题为 name；## Metadata 节解析 Short Description/Authors/Version/Last Updated/License/Commercial Use 六字段（loader.py L94-128）；## Overview 生成 description（截断 200 字符）；_strip_metadata 注入前剥离元数据（L165-224）
检索增强：biomni/model/retriever.py 的 prompt_based_retrieval（L14-132）——LLM 对 tools/data_lake/libraries/know_how 四类资源按索引挑选，指南要求"Be generous"、湿实验类必含分子生物学工具（L77-87）

## 5. 护栏
商业模式过滤非商用许可 Know-How（a1.py L876-896，读 commercial_use 元数据）；解析错误自纠错与熔断（L1445-1468）；协议生成反编造；Gradio 访问码（L2665）

## 6. 可移植清单
① Know-How 条目 schema（H1 标题 + ## Metadata 六字段 + ## Overview）→ MEMEX 记忆规范（loader.py L94-128）
② "清单式计划+每步回显更新"提示词 → 看板任务卡的 agent 提示模板（a1.py L1102-1119）
③ 全文预载 vs 索引式 LLM 检索的双模 Know-How 注入 → MEMEX + 收件箱检索策略（a1.py L1173/L1691，retriever.py）
④ 纠错重试≤2 次后熔断 → 脚本族状态机（a1.py L1451）
⑤ 极简工具注册三必填键 → 脚本族工具封装（tool_registry.py L32）

## 7. 知识库/技能清单
自带：Know-How 文档库（sgRNA_design_guide.md 14KB、single_cell_annotation.md 7KB）+ 配套数据资源 biomni/know_how/resource/（如 addgene_grna_sequences.csv）；data_lake 生物数据湖；protocols 库（biomni/tool/protocols.py，配 search_protocols/read_local_protocol 工具）。组织方式：md 文档平铺+内嵌元数据，无向量库、无外部依赖
