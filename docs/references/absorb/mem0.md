# 吸收笔记：mem0（Agent 记忆层，MEMEX 直接参考）

## 1. 提示词：提取与更新决策（重点）
本仓库版本为"V3 加性管线"：提取阶段只做 ADD（不再让 LLM 做 UPDATE/DELETE），旧版四操作决策 prompt 保留作对照。

- 提取 prompt（mem0/configs/prompts.py:468 ADDITIVE_EXTRACTION_PROMPT）核心规则：
  - 角色："You are a Memory Extractor — a precise, evidence-bound processor... Your sole operation is ADD"；从 user 和 assistant 双侧提取
  - 去重指令："Existing Memories... Use these ONLY for deduplication and linking"；语义等价且无新信息则跳过；但"实体相同≠事实重复"——"User has a dog named Max" 与 "went camping with Max" 必须分开存并用 linked_memory_ids 关联
  - 时间锚定："Observation Date is your ONLY temporal anchor"——"went to Paris last week" 必须落成 "the week of May 15, 2023"
  - 质量标准："Contextually Rich, Not Atomic"（变更类记忆必须记录转变前后："switched from almond milk to oat milk... after developing an almond sensitivity"）；"When in doubt, extract"（宁多勿漏，去重交下游）
- 更新决策 prompt（ADD/UPDATE/DELETE/NONE 判定，:176 DEFAULT_UPDATE_MEMORY_PROMPT）：
  - UPDATE："same information → keep the fact which has the most information"（信息不同则 UPDATE 且保持同一 ID）
  - DELETE："information that contradicts the information present in the memory"
  - NONE：事实已存在；ADD：全新信息才生成新 ID
  - user/agent 两侧专用提取 prompt（:63/:124），关键护栏："YOU WILL BE PENALIZED IF YOU INCLUDE INFORMATION FROM ASSISTANT OR SYSTEM MESSAGES"（角色泄漏惩罚）

## 2. 流程链路与检索评分
add→extract→store（memory/main.py:760 add → :881 _add_to_vector_store）七阶段批处理：
1. Phase0 上下文：取本 session 最近 10 条消息
2. Phase1 用新消息 embedding 搜 top10 已有记忆，**UUID→整数映射防 LLM 幻觉 ID**（:936）
3. Phase2 单次 LLM 调用提取
4. Phase3 批量 embed
5. Phase5 **MD5 hash 去重**（跨库+批内双 set，:1022）
6. Phase6 批量写入向量库+历史
7. Phase7 实体抽取与链接（实体相似度 ≥0.95 视为同实体，合并 linked_memory_ids）

检索评分融合（main.py:1642 + utils/scoring.py:60 score_and_rank）：
- 三信号加性融合：combined = (semantic + bm25 + entity_boost) / max_possible，max_possible 随信号激活自适应（1.0/1.5/2.0/2.5）
- BM25 经 sigmoid 归一化到 [0,1]，参数按查询词数自适应（≤3 词: midpoint=5.0, steep=0.7；scoring.py:16-40）
- entity_boost = 实体相似度 × 0.5 × 链接数衰减 1/(1+0.001·(n-1)²)（popular 实体降权，main.py:1816）
- threshold 只门控 semantic 分，BM25/entity 无法救回弱语义候选（scoring.py:74）；explain=True 返回 score_details 逐信号分解——**MEMEX "hits 统计"可直接借鉴的可解释字段**

## 3. 工具：存储抽象
- 向量库 base.py:4：insert/search/delete/update/get/list/reset + 可选 keyword_search（BM25，不支持返回 None 降级）+ search_batch；**所有实现必须返回"越大越相似"的 [0,1] 分数**（cosine 转 1-d，L2 转 1/(1+d)）
- 历史库 memory/storage.py:11 SQLiteManager：history 表 memory_id/old_memory/new_memory/event/created_at/is_deleted/actor_id/role，自动迁移旧 schema
- 实体库 main.py:559：惰性初始化、复用向量库配置仅换 collection 名
- LLM/Embedding：LlmFactory/VectorStoreFactory 工厂创建

## 4. 记忆：数据结构、scope、去重与 TTL
- MemoryItem（configs/base.py:16）：id/memory/hash/metadata/score/created_at/updated_at（pydantic）；payload 侧含 data/hash/text_lemmatized（为 BM25 预计算）/created_at/updated_at/attributed_to/expiration_date
- scope：user_id/agent_id/run_id 至少其一（main.py:391 强校验）；**身份键从自由 metadata 中剥离**，防调用方把记忆写进未授权 scope（:360 issue #6655）；search 拒绝顶层 user_id 参数、强制走 filters=
- 去重：MD5(text) 精确去重 + 提取 prompt 语义去重双层
- TTL：expiration_date（YYYY-MM-DD），_payload_is_expired（main.py:442）在 search/get_all 时惰性过滤，show_expired=True 可见——**不物理删除，读取时隐藏**

## 5. 护栏：边界与回退
- LLM 提取失败改为抛 LLMError 而非静默返回空——否则调用方无法区分"模型 429/超时"与"确实没有新事实"（main.py:965-971）
- 批量 insert 失败→逐条重试，仍失败的跳过；persisted_records 只含确认落库的记录——"a record the store rejected must never be reported back as a successful ADD"（:1052）；全失败抛 VectorStoreError
- 历史/实体链接失败仅 warning 降级不阻塞；embed_batch 失败逐条回退，向量数不齐 padding/truncate 保实体链接（:1133）
- JSON 解析两级回退（extract_json 兜底 code block 残留）；rerank 失败回退原始结果（:1518）

## 6. 可移植清单（→ MEMEX 规范 / .kb 条目格式）
1. 条目 schema：{id, text, hash, created_at, updated_at, expiration_date, attributed_to, linked_ids[]}，对应 MemoryItem+payload；hits 统计可类比 linked_memory_ids 计数衰减做 popular 降权
2. 提取策略：LLM 只做"加法提取"（sole operation ADD），变更/失效交独立决策层（四操作规则）；MEMEX 的"触发条件/依据"对应 linked_memory_ids + evidence-bound 角色
3. 变更记忆写法：强制记录"转变前后"（switched from X to Y after Z），MEMEX 内容字段应写明替换关系而非只写新状态
4. 去重双层：MD5 精确（便宜先做）+ 检索已有记忆进 prompt 做语义去重 + "实体相同≠重复"规则写进提取 prompt
5. TTL 惰性过期：expiration_date 存 payload、读取时过滤不物理删，配 show_expired 逃生口——适配 .kb 经验失效机制
6. 检索评分：semantic+BM25(sigmoid)+实体 boost 加性融合、threshold 只门控语义分、score_details 可解释字段——MEMEX 检索的 hits 统计记录 score_details 结构
