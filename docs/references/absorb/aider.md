# 吸收笔记：aider（git 原生每步回滚，D3）

## 1. 提示词
编辑格式约束是核心：aider/coders/editblock_prompts.py:8 main_system："Act as an expert software developer...ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!"；:120 system_reminder 规定 SEARCH/REPLACE 块 8 行格式（全路径独立一行、<<<<<<< SEARCH、=======、>>>>>>> REPLACE），SEARCH 与文件逐字符精确匹配、块保持简洁、新文件用空 SEARCH。格式家族：wholefile/udiff/patch/architect/ask/help 各配 _prompts.py

## 2. 流程
aider/coders/base_coder.py（84KB）编排中枢：auto_commit(:2375) 编辑后自动 git 提交，apply_edits(:2428) 落盘；每轮消息循环→LLM→解析编辑块→应用→自动 commit（commit message 由 LLM 依 diffs 生成，aider/repo.py:131 commit、:326 get_commit_message）。回滚：commands.py:553 cmd_undo——仅当 HEAD 哈希在 aider_commit_hashes（aider 自己产生的提交）中才回滚，防误撤人工提交；repo.py 用 GitPython 管脏文件

## 3. 工具
无 function-calling，靠文本协议（编辑块格式即"工具"）+ 命令系统（/undo /add /drop /run /test 等，commands.py）；search_replace.py 模糊匹配应用编辑，失败自动重试换格式

## 4. 记忆
仓库地图 aider/repomap.py——tree-sitter 抽取符号+PageRank 排序，注入相关文件签名到上下文；历史管理 aider/history.py/chat_chunks.py（system/preread/edit/files 分块，历史超限时摘要压缩）

## 5. 护栏
编辑应用失败即反馈 LLM 重试（base_coder.py 错误回传）；commit 前检查脏文件、undo 白名单校验；tests/ 全面单测（含 tests/fixtures/chat-history.md 回放用例）

## 6. 可移植清单
① 每步自动 commit+白名单 undo → 我们的 D3 每步回滚脚本族；② commit message LLM 生成（diff→摘要）→ 收尾会话自动写看板；③ 编辑格式系统提示+解析失败回传重试 → 状态机编辑节点；④ repo map 符号级上下文注入 → 知识库索引器；⑤ chat_chunks 分块+历史摘要 → 收件箱记忆管理

## 7. 知识库/技能清单
无外部依赖库；自带 website/docs/（repomap.md 等）、aider/website/ 文档站、tests fixture 聊天回放语料
