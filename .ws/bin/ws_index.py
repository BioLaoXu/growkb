#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 .index.md（项目级 + 全局，含按合同聚合）。

入口是 .ws/bin/ws_index.sh（薄封装）；解析逻辑在 ws_meta.py，与任务受理共用。
"""

import argparse
import os
import sys
from datetime import datetime

sys.dont_write_bytecode = True          # 不在 .ws/bin 里留 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ws_meta import STATUS_ORDER, cut, groups_of, methods_of, scan  # noqa: E402


def project_index(root, group, items, now):
    gdir = os.path.join(root, group)
    src = os.path.join(gdir, '.source')
    src_txt = os.readlink(src) if os.path.islink(src) else '（未关联生产目录）'
    contract = items[0].get('contract') or '(无)'
    body = [
        '# %s 分析任务索引' % os.path.basename(group),
        '',
        '> 由 `.ws/bin/ws_index.sh` 自动生成于 %s，**请勿手工编辑**（改 .meta.yaml 后重跑）。' % now,
        '',
        '- 生产标准分析目录：`%s`' % src_txt,
        '- 合同号：**%s**　任务数：**%d**' % (contract, len(items)),
        '',
    ]
    notes = os.path.join(gdir, '.notes.md')
    if os.path.isfile(notes):
        with open(notes, encoding='utf-8') as fh:
            body += ['---', '', fh.read().rstrip(), '']
    body += [
        '## 任务清单',
        '',
        '| 批次 | 任务 | 状态 | 创建 | 分析方法 | 需求摘要 |',
        '|---|---|---|---|---|---|',
    ]
    for task in sorted(items, key=lambda t: (t.get('batch') or '', t['task_id'])):
        body.append('| %s | %s | %s | %s | %s | %s |' % (
            task.get('batch') or '—', task['task_id'], task['status'],
            task.get('created') or '', methods_of(task), cut(task.get('request'), 70)))
    body.append('')
    with open(os.path.join(gdir, '.index.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(body))


def global_index(root, projects, tasks, groups, now):
    stat = {}
    for task in tasks:
        stat[task['status']] = stat.get(task['status'], 0) + 1

    out = [
        '# 工作空间分析任务总索引',
        '',
        '> 由 `.ws/bin/ws_index.sh` 自动生成于 %s，**请勿手工编辑**。（来源：各任务 `.meta.yaml`）' % now,
        '',
        '## 概览',
        '',
        '- 项目/分组数：**%d**　任务数：**%d**' % (len(groups), len(tasks)),
        '- 状态分布：%s' % ('、'.join('%s %d' % (k, v) for k, v in sorted(stat.items())) or '无'),
        '',
        '## 按合同聚合',
        '',
    ]
    if not tasks:
        out += ['> 当前没有任何任务。用 `.ws/bin/ws_new_project.sh` + `.ws/bin/ws_new_task.sh` 开始。', '']
    else:
        out += ['| 合同号 | 项目 | 批次 | 任务 | 状态 | 分析方法 |', '|---|---|---|---|---|---|']
        for task in sorted(tasks, key=lambda t: (str(t.get('contract') or ''),
                                                 t['group'], t.get('batch') or '')):
            out.append('| %s | %s | %s | [%s](%s/) | %s | %s |' % (
                task.get('contract') or '—', task['group'], task.get('batch') or '—',
                task['task_id'], task['rel_path'], task['status'], methods_of(task)))
        out.append('')

    out += ['## 分项目明细', '']
    for group in sorted(groups):
        items = groups[group]
        out += ['### %s' % group, '',
                '| 批次 | 任务 | 状态 | 更新 | 分析方法 | 需求摘要 |',
                '|---|---|---|---|---|---|']
        for task in sorted(items, key=lambda t: (STATUS_ORDER.get(t['status'], 9), t['task_id'])):
            out.append('| %s | [%s](%s/) | %s | %s | %s | %s |' % (
                task.get('batch') or '—', task['task_id'], task['rel_path'],
                task['status'], task.get('updated') or '',
                methods_of(task), cut(task.get('request'), 70)))
        out.append('')

    out += [
        '## 检索与维护',
        '',
        '```bash',
        '.ws/bin/ws_find.sh "motif"             # 关键词回溯',
        '.ws/bin/ws_find.sh -p cut_tag -s wip   # 按产品+状态过滤',
        '.ws/bin/ws_receipt.sh -T <任务> -s accepted   # 写受理/完成/交付回执到 .outbox/',
        '.ws/bin/ws_deliver.sh -T <任务>               # 同步到生产目录（默认预演）',
        '.ws/bin/ws_backup.sh                          # 备份 .meta.yaml 等元数据',
        '.ws/bin/ws_kb.sh index                        # 重建知识库索引 .kb/.index.md',
        '.ws/bin/ws_kb.sh check                        # 知识库语法体检（R parse / py_compile）',
        '.ws/bin/ws_check.sh                    # 一致性校验 + 空间占用',
        '```',
        '',
    ]
    # 全局索引不属于业务内容，落在隐藏的 .ws/ 下
    ws_dir = os.path.join(root, '.ws')
    os.makedirs(ws_dir, exist_ok=True)
    with open(os.path.join(ws_dir, '.index.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out))


def main():
    # 脚本位于 <工作空间>/.ws/bin/，往上三级才是工作空间根
    default_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=default_root)
    args = ap.parse_args()
    root = args.root

    projects, tasks = scan(root)
    groups = groups_of(tasks)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    for group, items in groups.items():
        if os.path.isdir(os.path.join(root, group)):
            project_index(root, group, items, now)
    global_index(root, projects, tasks, groups, now)
    print('[INFO] 索引已重建：%d 个分组 / %d 个任务' % (len(groups), len(tasks)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
