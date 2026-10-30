#!/usr/bin/env python3
"""UserPromptSubmit Hook：从首条任务相关消息提取 批次/合同/日期，给出会话命名建议。

命名格式（用户约定）：批次_合同号_<日期>
- 触发：消息含任务路径（projects/<年>/<批次>/…）或「受理 <批次>」指令
- 每个会话只建议一次（/tmp 标记文件，按 conversation_id 去重）
- 合同号从项目 .project.yaml 反查；查不到时用批次号充当并去重
"""
import json
import os
import re
import sys
import glob
import datetime

ROOT = os.environ.get('CODEBUDDY_PROJECT_DIR') or os.getcwd()

def contract_of(batch):
    for pj in glob.glob(os.path.join(ROOT, 'projects', '*', batch, '.project.yaml')):
        m = re.search(r'^contract:\s*(.+)$', open(pj, encoding='utf-8').read(), re.M)
        if m:
            return m.group(1).split('#')[0].strip().strip("'\"")   # 剥行内注释
    return batch

def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        data = {}
    prompt = data.get('prompt') or ''
    conv = data.get('conversation_id') or data.get('sessionId') or ''
    batch = None
    date = None
    m = re.search(r'projects/\d{4}/([\w\-.]+?)/', prompt)
    if m:
        batch = m.group(1)
        dm = re.search(r'(\d{8})', prompt)
        if dm:
            date = dm.group(1)
    else:
        m2 = re.search(r'受理\s+([\w\-.]+)', prompt)
        if m2:
            batch = m2.group(1)
    if not batch:
        print(json.dumps({'continue': True}))
        return
    marker = '/tmp/ws-title-' + re.sub(r'[^\w-]', '', conv or prompt[:40])
    if os.path.exists(marker):
        print(json.dumps({'continue': True}))
        return
    open(marker, 'w').write('1')
    contract = contract_of(batch)
    date = date or datetime.date.today().strftime('%Y%m%d')
    name = ('%s_%s_%s' % (batch, contract, date)) if contract != batch \
        else ('%s_%s' % (batch, date))
    out = {'continue': True,
           'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                                  'additionalContext':
                                  '会话命名建议（历史记录中重命名时复制）：%s' % name}}
    print(json.dumps(out, ensure_ascii=False))

if __name__ == '__main__':
    sys.exit(main())
