# BOARD-PLAN —— 「ControlTower 塔台」看板：评估与详细规划

> 立项：2026-10-29 · 状态：**评估完成，待用户确认启动**
> 痛点：「打开 CodeBuddy 与项目路径后，看不到以前任务的进度、新任务情况、重新投递未开始的——
> 需要看板/可视化页面，可点击启动分析」

## 一、需求 → 数据映射（全部已有，零新增采集）

| 你想知道的 | 数据源（磁盘，无 DB） | 判定逻辑 |
|---|---|---|
| 以前的任务与进度 | `projects/*/*/*/.meta.yaml` 的 `status`/`updated` | 五态直接渲染 |
| 新任务情况 | `.inbox/*_dispatch.yaml` | 每卡一条 |
| 重新投递但未开始 | 卡 ↔ 任务目录对账 | 卡内 taskPath 存在→看其 status（planned=已建未开工）；不存在或卡无 taskPath → 未受理（重新投递） |
| 哪些做完了 | status=done/delivered + packed | done 未交付提示"该打包了" |
| 回执情况 | `.outbox/*.yaml` | 每任务最新回执 |

结论：看板所需事实全部在磁盘上，扫描即可，不需要新存储——与「META 唯一事实」哲学一致。

## 二、方案评估

| 方案 | 形态 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| 一 静态看板 | ws_board.sh 扫描 → .ws/board/index.html，走现有 8792 | 零依赖、零服务改动、纯只读、半天可交付 | "点击启动"= 复制受理指令（clipboard 复制 buddycn chat 命令），需粘贴 | P1 先做 |
| 二 轻量后端 | ws_server.py（标准库）+ GET /api/state + POST /api/accept | 点击"启动"= 真受理（服务器端建项目/任务/回执，全自动） | 常驻服务；写操作需护栏（只调既有 ws_* 脚本） | P2 升级 |
| 三 IDE 深链 | 看板直拉 buddycn chat 会话 | 体验最好 | chat 的工作目录解析未验证；浏览器无法执行本机命令 | 暂缓 |

推荐两阶段：P1 满足"看得见"，P2 满足"点得动"，共用同一份扫描代码。

## 三、"点击启动"的三种语义（P2 按钮分层）

1. [受理]（卡→任务）：POST /api/accept → 执行 ws_new_project/new_task（卡含 taskPath 则跳过）+ ws_receipt.sh accepted
2. [开工]（任务→会话）：生成并复制 buddycn chat "继续 <taskPath>"——IDE 会话在用户本机，此步必然人工
3. [交付]（done→包）：POST /api/deliver → ws_pack.sh + ws_receipt.sh delivered

## 四、页面设计（单页）

概览条：批次 N · 任务 N（wip/planned/done/delivered 分布）· 待受理 N
🔴 待受理（每卡一行：批次 · 产品 · 需求摘要 · [受理] [查看卡] [忽略]；同 batch+slug 多卡自动归组标"疑似重复"）
🟡 进行中（任务 · 状态 · 更新时间 · 需求摘要 · [开工]）
🟢 已交付（任务 · 包路径 · 回执状态）

## 五、实施清单

P1 静态版（半天）：
1. .ws/bin/ws_board.sh：Python 扫描（复用 ws_meta.py scan + 新增 inbox 对账）→ 渲染 .ws/board/index.html
2. 入口：http://<服务器>:8792/.ws/board/index.html（8792 服务根已是工作空间根）
3. 验收：三态数字与 ws_check.sh/INDEX.md 一致；重复投递被标出

P2 后端版（1-2 天）：
1. .ws/bin/ws_server.py：标准库 ThreadingHTTPServer 扩展；只读路由 / 与 /api/state；
   写路由白名单 /api/accept /api/deliver —— 内部只调用 ws_new_*.sh / ws_pack.sh / ws_receipt.sh，不绕过规则
2. 前端 fetch 调 API
3. 验收：点 [受理] → 卡消失 + 任务目录出现 + 回执产生；安全：绑定 127.0.0.1 或 token；写操作幂等

P3 附加：[开工] 按钮直连 buddycn chat（待 chat 远程目录验证）。

## 六、风险与边界

- 看板只读项目数据；P2 写操作仅触发既有脚本（自带不覆盖/先问保护），不引入第二事实源
- pwb 投递的无 taskPath 卡，受理逻辑与 README 7.2 信息卡协议一致
- 并发：P1 只读无冲突；P2 受理过的卡移入 .inbox/accepted/ 归档目录防重复受理
