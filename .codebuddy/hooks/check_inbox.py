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
    """从信息卡提取 batch/contract/product/taskPath/request 首行。"""
    info = {'file': os.path.basename(path)}
    req_lines = []
    in_request = False
    for line in open(path, encoding='utf-8'):
        line = line.strip()          # 兼容缩进式 YAML（工作台生成的卡键前带空格）
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^(\w+):\s*(.*?)\s*(?:#.*)?$', line)
        if m and m.group(1) in ('batch', 'contract', 'product', 'taskPath'):
            info[m.group(1)] = m.group(2).strip().strip("'\"")
            in_request = False
            continue
        if re.match(r'^request:\s*>-?\s*$', line):
            in_request = True
            continue
        if in_request:
            if line.startswith((' ', '\t')) and line.strip():
                req_lines.append(line.strip())
            else:
                in_request = False
    info['request'] = ' '.join(req_lines)[:80] or '（详见卡文件）'
    return info


def main():
    project = os.environ.get('CODEBUDDY_PROJECT_DIR') or os.getcwd()
    inbox = os.path.join(project, '.inbox')
    cards = sorted(glob.glob(os.path.join(inbox, '*_dispatch.yaml')), reverse=True)

    if os.environ.get('KB_HOOK_DEBUG'):
        sys.stderr.write('[check_inbox] project=%s cards=%d\n' % (project, len(cards)))

    if not cards:
        ctx = '收件箱 .inbox/ 当前无待受理的分析请求。'
    else:
        lines = ['.inbox/ 有 %d 张待受理的分析信息卡（最新在前）——'
                 '用户说「受理」即按 README 第七节流程处理：' % len(cards)]
        for card in cards[:5]:
            info = parse_card(card)
            lines.append('- [%s] 批次=%s 合同=%s 产品=%s 需求：%s（卡：%s）' % (
                info.get('taskPath', '?'), info.get('batch', '?'),
                info.get('contract', '?'), info.get('product', '?'),
                info.get('request', ''), info['file']))
        # 会话命名约定：样本批次号（IDE 标题取自首条消息，受理时带上批次号即可自动命名）
        batch = ''
        for card in cards[:5]:
            b = parse_card(card).get('batch', '')
            if b and b != '?':
                batch = b
                break
        if batch:
            lines.append('会话命名约定：本会话若用于受理任务，'
                         '请提醒用户在首条消息带上批次号（如「受理 %s」），'
                         '使 IDE 会话标题自动含批次号，便于历史检索；'
                         'Agent 受理后也应主动按「批次号_产品」建议命名。'
                         % batch)
        ctx = '\n'.join(lines)
        ctx = '\n'.join(lines)

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
