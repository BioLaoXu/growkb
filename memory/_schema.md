# MEMEX 经验条目规范 v1（定稿，来源：mem0/OmicsClaw 吸收）

每条经验一个文件：`.kb/memory/<YYYYMMDD>-<slug>.yaml`

```yaml
id: mem-20261031-001
type: knowhow          # knowhow | pitfall | preference | reference
scope: atac            # 产品线 / 任务类型 / global（检索范围）
task: 20261029_data-report-inhouseproject-2026-template   # 源任务（可溯）
trigger: >-            # 何时检索本条（关键词/意图，检索匹配依据）
  数据报告 promoter 口径
content: >-            # 经验本体；变更类必须写明"从 X 改为 Y，原因 Z"
  promoter 定义必须与客户确认 ±N kb；默认 TSS±3kb 时在报告声明
evidence:              # 依据（方案"有据"的强制字段）
  - <文献/文档/先例任务路径>
superseded: null       # 被本条替代的旧条目 id（冲突编辑时回填）
hits: 0                # 检索命中并采用次数（自学习信号）
created: 2026-10-31
last_verified: 2026-10-31
expiration: null       # YYYY-MM-DD；过期在读取时隐藏，不物理删
```

## 治理规则（四操作+升华）

- 提取只做加法（sole operation ADD）；变更/失效由对账判定 ADD/UPDATE/DELETE/NONE
- UPDATE 保持同一 id，记录"转变前后"；DELETE 仅当新事实与旧条目矛盾
- 读取（recall）**不刷新 last_verified**（读取不是证据）；只有重新核验才更新
- 同 type+scope+trigger 语义重复：MD5 精确去重拦截；语义重复走 UPDATE
- **升华**：同 type+scope 条目 ≥3 条 → 提示 Agent 合并升华为 `.kb/docs/methods/` 正式方案，原条目标 superseded
