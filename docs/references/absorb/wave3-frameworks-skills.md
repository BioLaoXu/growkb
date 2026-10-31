# 吸收笔记（Wave 3 要点级）：crewAI/smolagents/scientific-agent-skills/SkillHub 技能族/Galaxy

## crewAI（30k★）
- 底层逻辑：角色化多智能体（Agent{role,goal,backstory}+Task+Process{sequential/hierarchical}+Flow 事件流）；轻量、快速原型友好
- 边界：深度控制弱于 LangGraph；分层少
- 可移植：role/goal/backstory 三元组可作为我们角色提示词的填写模板

## smolagents（HF，~15k★）
- 底层逻辑：**CodeAgent——用代码表达行动**而非 JSON 工具调用；循环极简（think→act(code)→observe）
- 可移植："代码即行动"范式适合我们分析类任务（生成一段 R/Python 而非逐参数调工具）；沙箱需自配（e2b/docker）
- 边界：生态薄

## scientific-agent-skills（K-Dense-AI，25.8k★）
- 底层逻辑：Claude Code 技能套件（SKILL.md 集），装完把通用编码 Agent 变科研专用：生信（序列/蛋白结构/代谢组）、化学信息、临床文献
- 可移植：技能分类目录结构（按学科域分层）可直接映射我们 .kb/code 的主题组织
- 边界：绑定 Claude Code 宿主

## SkillHub bio-* 技能族（本次实测解包，结构确凿）
- 三件套结构：SKILL.md（frontmatter：name/slug/displayName/version/license/summary/description/tags）+ references/feedback.md + references/command-recovery.md
- **关键边界（源码确凿）**：这类技能是**托管执行器 API 包装**——"The registered hosted executor accepts the documented JSON input and returns structured content... It does not run the upstream local toolchain"。即它们不跑本地管线，只调云端服务
- 可移植：SKILL.md frontmatter 字段集（含 version/license/tags）与三件套组织可直接用于我们 .kb 方案库的打包规范；"hosted executor"模式提示我们未来可把 ws_* 做成云端执行入口
- 语言：summary/description 中英双语并列——对国内团队分发友好

## Galaxy（文档级，仓库过大未克隆）
- 底层逻辑：Web 平台，工具封装+历史（workflow+所有参数+输入快照）+ 可复现分享
- 可移植：**历史=完整审计链**的设计对应我们 META+回执；工具重试/失败可见性
- 边界：重平台，非 Agent 形态
