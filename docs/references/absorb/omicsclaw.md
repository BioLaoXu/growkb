# 吸收笔记：OmicsClaw（清华 AI4Life，OpenClaw 底座多组学 Agent）

## 1. 提示词
- 运行时契约即系统提示：`OMICSCLAW.md` 为顶层，含 Identity/Operating Rules/技能路由表。规则直白可执行："Do non-trivial analysis in a module"、"Preserve numbers, p-values, paths, and errors. Never silently alter or fabricate scientific output"、"Report a tool error once with its likely cause. Do not loop failures"（OMICSCLAW.md:14-17）
- 渐进式披露：系统提示只放每技能一行 `- name: description`（88 个约 8k tokens），正文留磁盘按需加载（OMICSCLAW.md:175-184）
- SKILL.md 路由描述"load/skip 双半"：description 必须同时说何时加载、何时跳过并指名替代技能（templates/skill/SKILL.md:24-27）；frontmatter 只认 name/description/trigger/tags 四键（AGENTS.md:248-257）
- 正文固定章节：When to use / Use from a step / API（从 _api.py 生成）/ Methods and parameters / Gotchas（每条锚定 `<script>.py:LINE`）/ Inputs and outputs / CLI / Dependencies（AGENTS.md:388-407）

## 2. 流程
- plan_write 状态机：pending→in_progress→completed/cancelled（planning/plan.py:29-59）；提示词约束"3–7 pending items, exactly one in_progress"（OMICSCLAW.md:22-24）
- 防谎报完成：rules.py 两条规则——拒绝复活 cancelled 项；MAX_DIRECT_COMPLETIONS=1，"Finishing one thing per turn is what doing the work looks like; finishing nine is what describing the work looks like"（rules.py:27-42），拒绝以 ToolArgumentError 回给模型自愈
- 模块/步骤模型：analysis/<NN_slug>/ 编号 step 文件按序执行，末尾必有 <k>_validate.py 断言（列存在/表非空/数字在范围/图表存在，OMICSCLAW.md:89）；step 以 read_input/write_output 记录 IO，输出改名不覆盖输入
- 人工介入点：模块完成→accept（用户显式接受才冻结）；改动已接受模块需先告知再 revise（保留 baseline）；歧义时给 2-6 个选项并等待

## 3. 工具
- 内置 read_file/write_file/edit_file/bash/web_* + 88 技能 + use_skill/load_skill/run_cli/install_skill_deps/plan_write/memory_search/memory_write/task(子代理)/MCP
- 技能脚本统一 --input/--output/--demo；带 ## API 走 load_skill，否则 CLI 走 run_cli；技能与框架只通过文件相遇、互不 import（AGENTS.md:229-237）
- 分域依赖降级：skills/_sdk/deps.py 的 DEPENDENCIES 注册表（PyPI 名→module/kind/install/conda 备选）；use_skill 默认 probe 探测，install 需人工批准建 overlay venv（--system-site-packages，只装缺的、pinned、失败回滚），基环境永不动（AGENTS.md:292-304）

## 4. 记忆（重点）
- 存储：单 SQLite <workspace>/.omicsclaw/memory.db，会话与长期同库（entry/memory.py:71-72）
- 条目：MemoryEntry{id,title,content,category(knowledge/preference/task/skill),importance 0-10,ttl_days,tags,use_count,last_used_at}（memory/longterm.py:44-68）
- 检索：FTS5 全文搜索，"Ranking, not filtering, is what puts the best match on top"（store.py:46-66）；命中写回 use_count/last_used_at；结果上限 4096 字节、截断置 content_truncated 标记
- 去重/TTL：内容规范化（小写+折叠空白）SHA-256 指纹，重复合并取高重要度；TTL 从 updated_at 起算，"Reading one does not [refresh]: reaching for a memory is no evidence that it is still true"（longterm.py:75-89）
- 更新：压缩前 extractor 先读将摘要消息抽取"会话结束后仍为真"的偏好/事实/决定/流程（失败全吸收，"Losing a memory is a smaller problem than losing the turn"）；写后重渲染 MEMORY.md précis（≤30 条/5KB，原子替换 0600），下一轮注入系统提示末尾

## 5. 护栏
- 权限门：规则+模式+28 个危险命令模式（5 个数据外传：scp/rsync/ssh/curl 上传），require_approval fail-closed；批准卡显示工具/风险/原因、凭证打码
- 本地优先/网络护栏：scheme 白名单、拒 userinfo、DNS 对 14 段 CIDR 逐地址判定、每跳重检；工作区路径 containment
- 沙箱：docker 挂载 omicsclaw/、skills/ 只读，.env 盖 /dev/null
- 远程鉴权：非 loopback 绑定且 token 为空则拒绝启动；IM 渠道 owner allowlist；MCP 每次调用需批准

## 6. 可移植清单
1. 计划防谎报规则（单次只完成 1 项、禁复活 cancelled）→ Agent 常驻规则 + 状态机校验 Hook
2. 记忆指纹+TTL+读取不续命 → .kb 条目格式升级（MEMEX）
3. 压缩前抽取器 + 闭包式 précis（≤30 条/5KB 注入提示词末尾）→ 记忆库
4. 技能描述 load/skip 双半 + 渐进披露 → .kb 方案库 SKILL.md 格式
5. overlay 分域依赖安装（人工批准隔离 venv）→ 技能文档/Hook
6. 危险操作外传模式 + fail-closed 批准卡 → Hook/看板
