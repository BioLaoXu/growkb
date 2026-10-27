---
name: fix-preview-server-8792
overview: 重启失效的 8792 预览服务，把服务根目录固定为工作空间根（URL 从此稳定），并验证三个页面可访问。
todos:
  - id: kill-zombie-server
    content: 终止失效的预览进程 pid 285798（仅此一个，8765/8791 不动）
    status: completed
  - id: restart-preview
    content: 以工作空间根为服务根，后台重启 8792 预览服务并确认监听
    status: completed
    dependencies:
      - kill-zombie-server
  - id: verify-urls
    content: curl 验证三张架构图与 README 均返回 200，并输出稳定 URL 清单
    status: completed
    dependencies:
      - restart-preview
---

## 问题描述

用户访问 http://localhost:8792/.ws/docs/workspace-tree.html 始终无法打开。

## 诊断结论（已完成，只读核实）

- 端口 8792 上的预览服务（pid 285798，`python3 -m http.server 8792`）是 2026-10-26 11:05 以旧目录 `workspace/docs` 为根启动的僵尸服务
- 该目录经历「docs→.ws/docs 迁移」后已不在磁盘上（进程 cwd inode=146057325 ≠ 当前 .ws/docs inode=33523510），进程持失效句柄，所有请求（含根路径）均返回 404
- 端口 8765、8791 为其他用途的旧服务，本次不触碰

## 目标

- 杀掉失效进程，以工作空间根 `/data/Agent/xufa/workspace` 为服务根重启预览服务
- 使 `.ws/docs/` 前缀的 URL 从此稳定可用（后续目录再整理也不会失效）
- 验证架构图、README 均可正常访问

## 修复方式（纯运维操作，不涉及代码改动）

1. `kill 285798` 仅终止该失效进程（8765/8791 两个旧服务不碰）
2. 在工作空间根目录后台重启：`cd /data/Agent/xufa/workspace && nohup python3 -m http.server 8792 >> /tmp/ws_docs_preview.log 2>&1 &`，日志沿用原文件
3. 用 `curl` 逐一验证返回 HTTP 200：

    - `/.ws/docs/workspace-tree.html`（目录管理架构主图）
    - `/.ws/docs/workspace-structure.html`（交付链路图）
    - `/.ws/docs/workspace-lifecycle.html`（作业流程图）
    - `/README.md`（工作空间规范）

4. 向用户输出最终可用的稳定 URL 清单

## 明确不做

- 不改防火墙、不换端口、不更换服务器软件
- 不做成开机自启（如需常驻可后续另议 systemd/cron 方案）