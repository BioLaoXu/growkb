# 吸收笔记：MetaGPT（SOP 驱动多智能体：Role/Action/消息池）

## 1. 提示词：Role 与 Action 的 prompt 设计
- Role 前缀模板（metagpt/roles/role.py:51-79）："You are a {profile}, named {name}, your goal is {goal}. the constraint is {constraints}."；_get_prefix() 拼接环境与队友名："You are in {env.desc} with roles(...)"——组织架构注入 system prompt
- 新式 RoleZero（roles/product_manager.py:32-47）：类属性声明式编码 SOP——name/profile/goal/constraints/instruction/tools 全是字段；_think 按项目状态切 _set_state
- 指令体（prompts/product_manager.py）：ROLE_INSTRUCTION + EXTRA_INSTRUCTION，后者用"Mode 1/Mode 2"双模式 + 必填字段清单（"User Stories: 3-5 scenarios in As a [role], I want… format"）+ 触发条件编码 SOP
- ActionNode 结构化输出（actions/write_prd_an.py:12-53）：每字段一个节点，三元组 key/expected_type/instruction/example；编译进五段式模板（action_node.py:56-73）：## context / ## format example / ## nodes / ## constraint / ## action

## 2. 流程：SOP 流水线与消息池
- 消息即路由单元（schema.py:232-242）：Message 携带 cause_by（产生它的 Action 类名）、sent_from、send_to（默认广播）；路由靠"动作类型订阅"
- 订阅机制（role.py:284-291,399-427）：_watch([WriteTasks…]) 存入 rc.watch；_observe() 从 msg_buffer 取消息，filter: cause_by in watch or name in send_to——SOP 粘合剂：上游输出 Action 类型自动触发下游角色
- 消息池/环境（environment/base_env.py:124-195）：Environment 持 roles + 共享 history；publish_message 命中订阅则入私有缓冲并写共享 history；run(k) 并发 gather
- 固定 SOP 模式：set_actions([PrepareDocuments, WritePRD]); _watch([UserRequirement]); react_mode = BY_ORDER——流水线=动作序列+订阅关系

## 3. 工具抽象
- Action 是 pydantic 模型，prefix 作 system prompt；@register_tool(include_functions=["run"]) 把 Action 注册为工具，docstring 即 schema（actions/write_prd.py:75）

## 4. 记忆
memory/memory.py:20-107：storage list[Message] + 按 cause_by 建倒排索引 index；检索 API：get(k)/get_by_actions(actions)（支撑"只看关注动作"的最小充分上下文，role.py:116-118）/get_by_content 关键词过滤；无向量检索；去重靠 message in storage

## 5. 护栏
- 输出修复：utils/repair_llm_raw_output.py 四类修复 RepairType{CS 大小写/RKPM 缺键对/SCM 缺特殊字符/JSON}+ CustomDecoder 宽容解析
- 重试：_aask_v1 @retry(wait_random_exponential(1,20), stop_after_attempt(6))，每次先 llm_output_postprocess 再 pydantic 校验（action_node.py:423-427）
- 状态机容错：_think 非法状态号降级 -1 终止（role.py:371-373）
- 断点续跑：role_raise_decorator 异常时 rc.memory.delete(latest_observed_msg) 使消息可重新观察（common.py:689-714）

## 6. 可移植清单
1. cause_by 类型化消息订阅 → 受理协议/看板：消息带任务事件类型，角色声明 watch 集合，"任务完成→触发下游"替代轮询
2. 五段式 ActionNode prompt + 字段三元组（key/type/instruction/example）→ .kb 模板与角色化提示词：NGS 报告 schema 拆节点数组自动编译并 pydantic 校验
3. Memory 按 Action 类型倒排索引 → .kb 检索层：条目按"产生动作/阶段"索引，取 get_by_actions(watch) 作最小充分上下文
4. 类属性声明式 SOP → 角色提示词配置文件：每个 NGS 角色一个声明式配置，指令内用 Mode+触发条件+必填字段清单写 SOP
5. RepairType 输出修复 + retry(6) + 非法状态降级 → Hook 体系：解析失败先正则修复再重试，仍败降级挂起不崩溃
6. 异常时删除最近观察消息实现可重放 → 看板状态机：任务失败回滚"已投递未消费"态
