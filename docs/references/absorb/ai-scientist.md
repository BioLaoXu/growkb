# 吸收笔记：AI-Scientist（自动科研闭环，D4）

## 1. 提示词（py 内嵌字符串常量）
- 实验编码 coder_prompt（ai_scientist/perform_experiments.py:12-26）："最多 {max_runs} 次运行""必须用 python experiment.py --out_dir=run_i 格式"；完成信号 ALL_COMPLETED（:77）
- 选题 idea_first_prompt/idea_reflection_prompt（generate_ideas.py:14-72）：固定 JSON 输出（Name/Title/Experiment/Interestingness/Feasibility/Novelty 各 1-10 打分，:41-51）
- 审稿 reviewer_system_prompt_neg/pos（perform_review.py:13-25，正负倾向集成评审），16 字段结构化审稿表单（:43-61）
- 每模板配 templates/*/prompt.json（system 角色）+ seed_ideas.json（种子想法）

## 2. 流程
- 主管线 launch_scientist.py：选题（新颖性查重 check_idea_novelty，Semantic Scholar/OpenAlex）→实验（Aider 编码+MAX_RUNS=5、MAX_ITERS=4 重试 while 循环，perform_experiments.py:126-141）→绘图→写作（LaTeX）→评审→可选改进闭环（--improvement）
- 状态管理极简：run 计数+失败清空 run_{i} 目录重试（:54-55）；断点续跑=文件系统即状态：ideas.json 落盘、--skip-idea-generation 跳过已完成阶段（launch_scientist.py:31-40）、每次 run 复制代码快照为 run_{i}.py（:33-36）

## 3. 工具
- subprocess.run 执行实验/绘图（超时 7200s/600s，:30,88）；代码修改外包 Aider（launch_scientist.py:11-13）；LLM 网关 ai_scientist/llm.py 统一 30+ 模型带 backoff 限流重试（llm.py:66）；文献检索 Semantic Scholar/OpenAlex API

## 4. 记忆
- 对话历史 msg_history 逐轮累积（llm.py:73,77-78）；跨阶段记忆=notes.txt（实验结果留档供写作）+ run_{i}/final_info.json（结构化指标）+ ideas.json（既往想法注入下轮选题，generate_ideas.py:19-23）。无向量库

## 5. 护栏
- extract_json_between_markers 结构化校验+解析失败重试；预算护栏 MAX_RUNS/MAX_ITERS/超时；执行隔离：每次 run 独立目录、失败即删（防脏状态）；评审防自恋：正/负倾向多评审员集成（perform_review.py:18-25）+ 评审可被元评审校准（review_iclr_bench/）

## 6. 可移植清单
1. "循环编码→执行→反馈 stderr→重试，含硬预算上限" → 收件箱任务重试策略模板（MAX_ITERS 即熔断器）
2. notes.txt + final_info.json "结果留档给下游阶段"约定 → 收件箱任务产物规范（结构化指标+自由说明双通道）
3. 文件系统即断点（阶段产物落盘+skip 已完成阶段）→ 看板任务恢复最简实现
4. 结构化 JSON 输出+标记提取重试 → 所有 Agent 输出解析护栏
5. LLM 网关统一多模型+backoff → Hook 中 LLM 调用层封装

## 7. 知识库/技能清单
- templates/：12 个实验模板目录（nanoGPT/2d_diffusion/seir 等），每个含 experiment.py（实验代码=技能载体）、prompt.json（system 角色）、seed_ideas.json（种子想法）、ideas.json（历史想法库）、latex/（ICLR 模板）；example_papers/（已生成论文范例，可作 few-shot）
- 外部依赖：Semantic Scholar/OpenAlex 文献 API、Aider 代码编辑
- 组织方式：一个模板=一个自包含科研领域包，数据集由 experiment.py 内嵌生成或下载
