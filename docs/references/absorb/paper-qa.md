# 吸收笔记：PaperQA2（文献问答与引用校验，Future House）

## 1. 提示词（src/paperqa/prompts.py）
- **证据摘要 prompt**（summary_prompt）：对每段文献摘录——"Do not directly answer the question, instead summarize to give evidence to help answer the question. Stay detailed; report specific numbers, equations, or direct quotes (marked with quotation marks). Reply 'Not applicable' if the excerpt is irrelevant. At the end provide an integer score 1-10 indicating relevance. Do not explain your score."——**"先证据不先答案 + 相关性自评分"**
- **答案 prompt**（qa_prompt）："Write an answer based on the context... If the context provides insufficient information reply 'I cannot answer.' For each part of your answer, indicate which sources most support it via citation keys at the end of sentences... Only cite from the context above."
- **引用格式硬约束**（CITATION_KEY_CONSTRAINTS）：给出 Valid/Invalid citation examples 各 4-5 条（逗号分隔括号式合法；and/pqac-xxx 连接/作者年份式非法）——**用正反例清单约束引用格式**
- **迭代答案约束**（answer_iteration_prompt_template）："Create a new answer only using context keys and data from the included context. You can not use context keys from the prior answer which are not also included in the above context."——**迭代时强制剔除失效引用，防陈旧引用**
- CANNOT_ANSWER_PHRASE = "I cannot answer" 哨兵短语：1) 触发 complete 工具 has_successful_answer=False；2) 可用于单元测试

## 2. 流程（检索→证据→答案）
- agentic 层：agents/tools.py 中 NamedTool 类族——PaperSearch（文献搜索）、GatherEvidence（逐文献 gather_evidence 产生 Context+相关分）、GenerateAnswer；EnvironmentState 记录上下文/动作史，get_relevant_contexts(score_threshold) 按阈值筛证据
- 链路：search→gather（每篇文献独立 summary+打分）→answer（仅用通过阈值的 context keys）→重复迭代（answer_iteration 只用当前有效 context）
- 双层答案：证据摘要（不回答）与最终答案分离——答案只拼证据，杜绝幻觉直答

## 3. 工具
NamedTool 基类（agents/tools.py:95）便于查名；工具即类方法（paper_search/gather_evidence/generate_answer/complete_answer）；packages/ 四种 PDF 解析后端（docling/pymupdf/pypdf）可插拔

## 4. 记忆
- 文档索引：docs.py Doc 对象（dockey=md5sum、doi、citation）+ 向量索引（manifest 文件可复用）
- 无长期对话记忆；上下文=context keys 机制（CONTEXT_OUTER_PROMPT 列 Valid Keys）

## 5. 护栏
- 引用真实性：citation keys 只能来自上下文、格式正反例约束、CANNOT_ANSWER 哨兵（宁可不答不编造）
- extract_score（utils.py:134-140）：0-10 整数，0 为 N/A 哨兵——**0 分哨兵与提示词里的"Not applicable"呼应**
- 多模态富化 prompt（prompts.py:150-200）：图像/公式/表格描述带**失败模式清单**（logo/乱码/子图各自的正确处理方式）——把已知失败模式写进 prompt 是防幻觉的好范式
- 双解析器：llm_parse_json + strip_citations 容错

## 6. 可移植清单
1. "证据摘要与最终答案分离 + 1-10 相关性自评 + 0 分哨兵" → 方案有据的引用协议（报告结论每句挂证据键）
2. 引用格式正反例清单（Valid/Invalid examples）写进 prompt → 我们报告的参考文献格式约束
3. 迭代答案时强制剔除失效 context keys → 防陈旧引用（能力 2）
4. CANNOT_ANSWER 哨兵短语（宁可不答）+ 单元测试可用 → 受理/开工协议的"无法完成即申报"机制
5. 多模态描述 prompt 的失败模式清单写法 → 报告图表解读章节的提示词
6. 环境状态 get_relevant_contexts(score_threshold) → 看板证据分级展示

## 7. 知识库/技能清单
无内置领域知识库；索引与文档存储为本地 manifest+向量索引（可外接 DB/向量库缓存）；packages/ 四种 PDF 解析后端；docs/ 文档站（含 Customizing Prompts/Pre and Post Prompts 章节——提示词可配置是头等特性）
