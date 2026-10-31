# 吸收笔记：BioMCP（生医 MCP server：统一命令语法，Rust 单二进制）

> 实际形态：Cargo 工作区 + rmcp SDK，CLI（clap）与 MCP server（stdio/HTTP）共用同一套 entities/sources 核心逻辑。核心在 src/{cli,mcp,entities,sources,cache,render,error}。

## 1. 提示词（工具描述写法）
- 工具描述集中在静态目录表 src/mcp/catalog.rs:12-48，catalog::apply()（L50-71）统一注入路由，assert_eq!(actual.len(), TOOLS.len(), "MCP router and catalog differ") 强制"路由实现"与"给 Agent 的文案"一一对应
- 写法要点：**动词 + 有界输入 + 明确禁止项**：
  - "Run one read-only BioMCP command. Prefer typed tools. Use `biomcp list <entity>` for discovery or `biomcp skill list` for workflows. Set `json` for structured output. Binary downloads and mutations are rejected."
  - "Get one biomedical record with typed inputs. Binary assets are CLI-only."
- server 级 system prompt 在 catalog.rs:93-102 instructions()：先列 7 个只读工具，指示"优先有界 typed 工具，raw biomcp 兜底"
- 参数约束直接写进 schema（src/mcp/shell.rs:56-108）：schemars(length(min=1,max=50))、deny_unknown_fields、range(min=1,max=100)

## 2. 流程：请求→适配器→外部 API→响应
- 三层：entities/*（业务编排）→ sources/*（适配器）→ HTTP。适配器先产**纯 RequestPlan**（无网络、可单测），再交 request_from_plan() 注入 live client（sources/mod.rs:735-740）
- 样例链路（ClinicalTrials，sources/clinicaltrials.rs:16-115）：CtGovSearchParams → detail_plan() → studies/{id} → send() 里 apply_cache_mode + send_with_source_context(SourceContext::retry(CLINICAL_TRIALS)) + read_limited_source_body（8MB 上限，mod.rs:525）
- 错误/重试（mod.rs:1215,1299）：RetryTransientMiddleware + ExponentialBackoff（3 次），共享 client 管道 = URL策略→限速→重试→HTTP缓存；错误封装 BioMcpError（error.rs:348 起），带结构化 SourceContext（L237-249：RetryRemoteSource/ReviewSourceConfiguration/NarrowRequest）+ 人类可读恢复指令，public_projection() 做脱敏（测试断言 sentinel 不泄漏，error.rs:1245-1251）；ORCID 另有应用层 Retry-After 循环（orcid.rs:237-253）

## 3. 工具：CLI/MCP 共享与 70 源组织
- CLI 路由枚举 src/cli/commands.rs:10-258（只定义参数）；MCP server src/mcp/shell.rs:1320+ 的 typed 工具 handler 直接调 entities 层——**CLI 与 MCP 都汇入 entities 层**，渲染层 CLI 用 markdown（render/human.rs）、MCP 用 JSON（render/json.rs）
- 适配器组织：src/sources/ 一源一文件（~100 个）；发现靠 SourceProvider 枚举 + source_state_registry.rs 的 SOURCE_STATE_ROWS 静态注册表，健康检查 biomcp health 按表探活
- mcp/tools 仅 7 个工具，靠 raw biomcp 命令透传长尾

## 4. 记忆：缓存与限流
- HTTP 缓存：http_cache_reqwest 磁盘缓存（cacache），BIOMCP_CACHE_MODE/--no-cache 全进程单一读取点 current_cache_mode()（mod.rs:615-621）；**认证请求强制 NoStore**（resolve_cache_mode，mod.rs:628）
- cache/manager.rs+limits.rs 管配额：blob 引用计数、over_max_size/below_min_disk_free 双阈值驱逐（limits.rs:76-103）
- 限流：sources/rate_limit.rs:14-18 RateLimitPolicy{key, prefix, min_interval} 按源 min-interval 节流中间件；批量文章调用全局 deadline+Semaphore(10)（mod.rs:22-55）

## 5. 护栏
- Key 管理：只从环境变量读（ncbi_api_key/s2_api_key mod.rs:721-733；ONCOKB_TOKEN 有 token 才启用该源 cli/list/helpers.rs:5-7）；含 key 的请求走 apply_cache_mode_with_auth 禁缓存（pubmed.rs:210-214）；错误信息校验"1-4096 visible ASCII bytes"（error.rs:612）
- 输入校验：schema 级 + 业务级（is_valid_gene_symbol mod.rs:714-719；PMID 纯数字检查 pubmed.rs:190）
- 来源可信：render/provenance.rs:22-52 每个结果 section 附 SectionSource{label, outcome, sources[]} 溯源标注；URL 白名单 + 拒绝非受信主机且不重试（mod.rs:1153-1156）

## 6. 可移植清单（→ 脚本族 MCP 化 / 看板 API）
1. 工具目录表 + assert 对齐：把管理脚本族"建任务/检索/体检/回执"各写一条 description（动词+边界+禁止项）收进静态表，启动时校验与路由一致
2. Plan 纯函数 seam：适配器先产无 IO 的 RequestPlan 再注入 client → 看板 API 查询先构 plan 便于单测
3. 共享中间件管道：URL 策略→限速→指数退避(3)+Retry-After→磁盘缓存→body 上限 → 脚本族 HTTP 层统一封装一处
4. 带 SourceContext 的错误投影：错误附来源+三类恢复动作文案+脱敏 → MCP 返回给 Agent 的错误直接可行动
5. SectionSource 溯源：每个返回 section 标注数据源与状态（ok/degraded/unavailable）→ 体检/回执输出标"数据来自哪个源、是否降级"
6. 认证请求禁缓存 + env-only key → 带 token 的看板/平台 API 响应一律 NoStore
