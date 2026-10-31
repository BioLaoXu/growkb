# 吸收笔记：lm-evaluation-harness（评测基准工程，D2）

## 1. 提示词
- 提示词不硬编码，YAML 声明式模板：`doc_to_text: "Question: {{question}}\nAnswer:"`（lm_eval/tasks/gsm8k/gsm8k.yaml:10）；few-shot 采样器 lm_eval/api/samplers.py；系统指令/聊天模板参数在 evaluate(system_instruction=..., apply_chat_template=...)（lm_eval/evaluator.py:439-440）
- 停止串控生成边界：generation_kwargs: until: ["Question:", "</s>", "<|im_end|>"]

## 2. 流程
- simple_evaluate → evaluate 两段式（evaluator.py:55/:429）：构建模型→TaskManager 加载任务→构造 Instance→推理→filter→metric→聚合；纯函数式批处理，无长程状态机
- 断点续跑=请求级缓存：use_cache/cache_requests/rewrite_requests_cache（evaluator.py:63-65）+ caching/cache.py；结果落盘 loggers/evaluation_tracker.py

## 3. 工具
- 任务注册=目录即注册表：lm_eval/tasks/<bench>/<task>.yaml+组配置；抽象基类 Task（api/task.py:64）与 YAML 驱动 ConfigurableTask（task.py:618）；插件式模型后端统一 LM 接口（api/model.py）+ registry（api/registry.py）；CLI 校验子命令 _cli/validate.py

## 4. 记忆
无会话记忆；few-shot 由 samplers 构造；历史仅经请求缓存复用——有意为之：评测需可复现、无状态

## 5. 护栏
- 多路 filter（strict-match/flexible-extract 双重抽取对照，gsm8k.yaml:32-43）；指标与聚合分离（api/metrics.py）
- 去污染子系统：lm_eval/decontamination/{janitor.py,decontaminate.py}（docs/decontamination.md）——评测集与训练集 n-gram 重叠检测，防刷分污染

## 6. 可移植清单
1. YAML 声明式"评分项"（prompt 模板+metric+filter 三分离）→ 评分基准层配置化
2. strict/flexible 双重抽取对照并标注分歧 → 评分时同答双解析
3. 去污染 janitor 思路 → 知识库入库查重防污染（Hook）
4. 请求级缓存 → 收件箱任务幂等重跑（失败任务不重算已成功子步骤）
5. _cli/validate.py 任务校验 → 新评分项入库前 Hook 校验 schema

## 7. 知识库/技能清单
- lm_eval/tasks/：约数百个基准目录（每个 yaml+README），顶层 tasks/README.md（135KB 汇总索引）
- docs/（task_guide/new_task_guide/model_guide 等 11 篇）；templates/new_yaml_task/（新任务脚手架）
- 数据集经 HF datasets 在线拉取（dataset_path 字段），不本地存储
