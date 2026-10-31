# Harness 事件/错误契约 v1（P1-6.1/6.4 落地，来源：OpenHands/BioMCP/ToolUniverse）

## 一、写操作统一输出（事件契约）

所有**新增**的写型脚本/接口，输出一律为事件契约 JSON（动作/观察成对同构）：

```json
{
  "ok": true,              // 执行结果
  "action": "add",         // 动作类型（add/update/delete/search/pack/grade/…）
  "is_error": false,       // OpenHands 范式：观察侧错误标记
  "error": null,           // 或 {message, retriable, next_steps[]}
  "data": {…}              // 动作产物
}
```

## 二、错误协议（三要素，缺一不可）

| 字段 | 作用 | 来源范式 |
|---|---|---|
| message | 人类可读原因 | BioMCP（错误必须可行动） |
| retriable | 是否值得重试（false=需人改输入） | ToolUniverse（None 强转 error 并标注） |
| next_steps[] | 给 Agent 的下一步建议（自愈入口） | ToolUniverse next_steps、BioMCP SourceContext |

已接入：`ws_memory.py`（全命令）、看板全部 POST 接口（字符串错误自动补 next_steps）。
存量脚本（bash 系）暂保留文本输出，逐步迁移，**不一次性重写**。

## 三、护栏约定

- 写响应一律 `Cache-Control: no-store`（认证/写操作禁缓存）
- 破坏性操作（delete/purge）必须带显式确认参数（confirm=DELETE / --reason），fail-closed
- 记忆入库：MD5 精确去重 + 语义相似度 ≥0.85 拒绝 + 矛盾删除必须写原因（审计要求）

## 四、迁移原则

- 新工具全部走契约；旧工具在被触碰时顺手迁移
- 看板是契约的第一消费者（按钮失败时直接把 next_steps 渲染给用户）
