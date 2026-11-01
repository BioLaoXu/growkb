#!/usr/bin/env python3
"""SessionStart Hook：新会话自动查收 .inbox/ 待受理的分析信息卡。

输出 additionalContext 注入会话，使 Agent 开场即知道有待办请求；
无待办时提示收件箱为空。stdout 必须保持纯 JSON，调试信息走 stderr。
"""
import glob
import json
import os
import re
import sys


def parse_card(path):
    """解析信息卡：yaml 优先（兼容缩进式与平铺式），失败时逐行提取标量字段。"""
    info = {'file': os.path.basename(path)}
    data = {}
    try:
        import yaml
        raw = yaml.safe_load(open(path, encoding='utf-8')) or {}
        if isinstance(raw, dict):
            data = raw.get('【分析请求】', raw)
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    if not data:
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(\w+):\s*(.*?)\s*(?:#.*)?$', line)
            if m and m.group(2) and m.group(2) not in ('null', '>-', '|'):
                info[m.group(1)] = m.group(2).strip().strip("'\"")
    for k, v in data.items():
        if k == 'inputs' or not isinstance(v, (str, int, float)):
            continue
        v = str(v).strip().strip("'\"")
        if v and v != 'null':
            info[k] = v
    if 'request' in info:
        info['request'] = info['request'].replace('\n', ' ')[:200]
    return info


def main():
    project = os.environ.get('CODEBUDDY_PROJECT_DIR') or os.getcwd()
    inbox = os.path.join(project, '.inbox')

    # 哨兵计数：收件箱待受理 + 活跃 wip（轻量 grep，不展开任何卡内容）
    pending = len(glob.glob(os.path.join(inbox, '*_dispatch.yaml')))
    wip = 0
    for mp in glob.glob(os.path.join(project, 'projects', '*', '*', '*', '.meta.yaml')):
        try:
            if re.search(r'^status:\s*wip', open(mp, encoding='utf-8').read(), re.M):
                wip += 1
        except Exception:
            pass

    if os.environ.get('KB_HOOK_DEBUG'):
        sys.stderr.write('[check_inbox] project=%s pending=%d wip=%d\n'
                         % (project, pending, wip))

    # P1-02 单行计数哨兵：只报数，不展开卡内容——避免续跑/修复会话被收件箱劫持。
    # 用户要求接单（说「查看收件箱」「受理」）时，Agent 再主动扫描并展开详情。
    ctx = ('$$ Workspace Sentinel $$  Inbox pending: %d | Active WIP: %d —— '
           '如需接单请说「查看收件箱」或「受理 <卡文件名>」；'
           '与本任务无关的会话禁止主动展开收件箱详情。' % (pending, wip))

    output = {
        'continue': True,
        'hookSpecificOutput': {
            'hookEventName': 'SessionStart',
            'additionalContext': ctx,
        },
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
