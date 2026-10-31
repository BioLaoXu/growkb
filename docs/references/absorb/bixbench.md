# 吸收笔记：BixBench（Future House 生信智能体基准）

## 总体架构
仓库仅含驱动/评分代码；数据集（61 胶囊 zip + 问题 JSON：question_id/question/ideal/distractors/data_folder/capsule_uuid/eval_mode）托管 HF futurehouse/bixbench。执行环境在外部包 fhda（pyproject.toml:14），胶囊系统提示词（CAPSULE_SYSTEM_PROMPT_OPEN/OPEN_PROMPT_TEMPLATE/HYPOTHESIS_PROMPT_TEMPLATE）定义在 fhda.prompts——本地仓库看不到原文。

## 1. 提示词（仓库内可见的评测提示词，bixbench/prompts.py）
- MCQ 答案抽取（L1-7）："Extract the single letter answer… You must pick one answer even if you are unsure… only output a single letter answer in XML format. Example Output: <answer> X </answer>"；带拒答变体（L9-15）
- 开放题作答（L17-23）："Answer to the best of your knowledge. Keep concise… output in <answer>…</answer>"
- 开放题 LLM 判分（L25-32）："compare the target answer with the predicted and assess if correct, incorrect or refused… output one from correct/incorrect/refused between <grade> tags"
- 数值区间判分（L34-41）：目标 (lower,upper) 区间内即 correct
- Notebook→MCQ 评测（L43-89 MCQ_EVAL_PROMPT）：agent 完整 notebook（markdown 化）+问题+其开放题答案喂给判分 LLM，先在 <question_analysis> 引用 notebook 证据、列各选项正反论据，再输出 <answer>A</answer>。开放题二值判分 L91-98（0/1 等价性）

## 2. 流程（胶囊结构与评测循环）
- 胶囊加载（generate_trajectories.py:135-206）：HF 拉 zip→解压 data/capsules/<名>/→找 *Data* 目录把数据上移到根、**删除 *Notebook* 目录和所有 *.ipynb（防标准 notebook 泄漏答案，L182-200）**
- 评测循环（run() L444-469）：批量建环境→vanilla_rollout（L352-393，env.reset→agent→env.step 循环至 done 或 max_steps=40）→store_trajectory 存 {problem_id}[_replica_N].json（答案/notebook/动作数）→事后 postprocessing.py 评分（开放题 0/1；MCQ 用 MCQ_EVAL_PROMPT+xml_extract 比对字母），5 replica 多数投票（models.py:187-192 MajorityVoteConfig）。复现脚本 4 配置×5 replica 全跑
- 题型 YAML 驱动（run_configuration/generate_trajectories.yaml）：mode: open/mcq/hypothesis、include_refusal_option、eval_mode: None

## 3. 工具（执行环境与数据挂载）
每题独立工作目录 workspace/<run_name>/<capsule_uuid>/<question_id>（L296-302），胶囊数据**文件级复制**进工作目录；执行环境=fhda.DataAnalysisEnv（Jupyter，默认 Docker futurehouse/bixbench:aviary-notebook-env，语言 Python/R）；agent 由 ldp ReActAgent 构造（hide_old_env_states: True）

## 4. 记忆（跨题污染控制）
- **每题全新环境**：environment_factory 每题新建 DataAnalysisEnv，agent 状态不跨题传递（rollout_with_saving L435-442）
- 工作目录按 capsule_uuid/question_id 隔离；轨迹按题命名可断点续跑（filter_completed L427-433）；序列化剔除本地路径（L218-222）
- MCQ 选项随机洗牌防位置偏置：种子固定为问题本身保证可复现（generate_trajectories.py:482）

## 5. 护栏（判分与防污染）
- 仓库代码内未见 canary GUID（在 HF 数据集卡片层面）；防泄漏=解压即删 Notebook/ 与 *.ipynb
- 三级判分梯度（graders.py:65-108）：归一化精确匹配→部分匹配→LLM verifier；拒答判定 refusal = predicted == unsure；GradeType 三态 correct/incorrect/refused（L14-37）
- MCQ 评分 LLM 可参考 agent 开放题答案但"不必采信"（MCQ_EVAL_PROMPT L62）；强制结构化输出+XML 提取防格式漂移；拒答选项使可算 precision/coverage（utils.py:77-102）

## 6. 可移植清单
1. 胶囊数据消毒：打包剔除作者 notebook/答案目录，加载时再删 *.ipynb → 内部胶囊制作 SOP
2. 三层判分协议：exact→partial→LLM verifier 梯度 + 三态(correct/incorrect/refused) + 区间题型 → 内部评分协议（移植 graders.py 的 GradingFunction）
3. "开放题先答、MCQ 后判"双轨：判分 LLM 读 notebook 证据再选字母，即评"分析过程"而非裸答案 → 评分协议
4. replica+多数投票+精度/覆盖率指标：k=5 replica、accuracy/precision/coverage → 内部基准运行配置
5. 每题独立工作区 + 题级断点续跑：<run>/<capsule_uuid>/<question_id> 目录契约与 filter_completed → 任务收件箱/工作区管理
6. YAML 全配置驱动：模型/prompt 模板名/步数上限/批大小/拒答开关全外置 YAML → 内部基准 run 配置层
