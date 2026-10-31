#!/usr/bin/env python3
"""胶囊基准（P1-2.1，BixBench/GenoTEX 范式）：把已完成任务转化为可评测胶囊。

用法：
  ws_bench.py pack <taskPath> [--name slug]      # 打包胶囊（数据+任务书，剔除答案性文件）
  ws_bench.py list                               # 列出胶囊
  ws_bench.py grade <胶囊目录> --answer <答案.md> # 评答案（覆盖率+证据键格式三梯度 v1）

胶囊结构：.bench/capsules/<id>/
  capsule.yaml  任务书（request/标准产物清单——不含结论）
  data/         数据文件（tables/figures，单文件 >2MB 跳过）
  README.md     给受测 Agent 的任务说明
答案剔除：不复制 report.md 结论章节（受测 Agent 必须自己产出分析结论）。
"""
import json
import os
import re
import shutil
import sys
import datetime

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCH = os.path.join(ROOT, '.bench', 'capsules')
MAX_FILE = 2 * 1024 * 1024

def contract(action, ok=True, data=None, message='', next_steps=None):
    err = None if ok else {'message': message, 'next_steps': next_steps or []}
    return {'ok': ok, 'action': action, 'is_error': not ok, 'error': err, 'data': data or {}}

def out(obj):
    print(json.dumps(obj, ensure_ascii=False))

def main():
    if len(sys.argv) < 2:
        out(contract('usage', False, message='缺少子命令', next_steps=['pack | list | grade']))
        return
    cmd = sys.argv[1]
    if cmd == 'pack':
        task = (sys.argv[2] if len(sys.argv) > 2 else '').strip('/')
        name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'capsule'
        mp = os.path.join(ROOT, task, '.meta.yaml')
        if not os.path.isfile(mp):
            out(contract('pack', False, message='任务不存在：' + task,
                         next_steps=['检查 taskPath']))
            return
        meta = {}
        for line in open(mp, encoding='utf-8'):
            m = re.match(r'^(\w+):\s*(.*?)\s*(?:#.*)?$', line.strip())
            if m and m.group(2) and m.group(2) != 'null':
                meta[m.group(1)] = m.group(2)
        cid = '%s-%s' % (datetime.date.today().strftime('%Y%m%d'), name)
        cdir = os.path.join(BENCH, cid)
        if os.path.exists(cdir):
            out(contract('pack', False, message='胶囊已存在：' + cid,
                         next_steps=['换 --name']))
            return
        os.makedirs(os.path.join(cdir, 'data'), exist_ok=True)
        copied, skipped = 0, 0
        for sub in ('results/tables', 'results/figures'):
            srcd = os.path.join(ROOT, task, sub)
            if not os.path.isdir(srcd):
                continue
            for f in sorted(os.listdir(srcd)):
                fp = os.path.join(srcd, f)
                if os.path.isfile(fp) and os.path.getsize(fp) <= MAX_FILE:
                    shutil.copy(fp, os.path.join(cdir, 'data', f))
                    copied += 1
                else:
                    skipped += 1
        standard = sorted(os.listdir(os.path.join(cdir, 'data')))
        req = (meta.get('request') or '').strip().replace('\n', '\n  ')
        open(os.path.join(cdir, 'capsule.yaml'), 'w', encoding='utf-8').write(
            '# 胶囊任务书（不含结论——受测 Agent 自行产出分析）\n'
            'id: %s\nsource_task: %s\ncreated: %s\nrequest: >-\n  %s\nstandard_outputs:\n' % (
                cid, task, datetime.date.today().strftime('%Y-%m-%d'), req) +
            ''.join('  - data/%s\n' % s for s in standard))
        open(os.path.join(cdir, 'README.md'), 'w', encoding='utf-8').write(
            '# 胶囊任务：%s\n\n## 任务\n%s\n\n## 你要做的\n'
            '基于 data/ 中的分析产出撰写研发数据总结（各板块结论，每句挂证据键 '
            '`(文件名#表号/图号)`），保存为 answer.md。\n\n'
            '## 标准产物清单（答案至少引用其中大部分）\n%s\n' % (
                cid, meta.get('request') or '', '\n'.join('- data/%s' % s for s in standard)))
        out(contract('pack', data={'id': cid, 'dir': cdir, 'files': copied,
                                   'skipped_oversize': skipped, 'standard_outputs': len(standard)}))
    elif cmd == 'list':
        os.makedirs(BENCH, exist_ok=True)
        caps = [d for d in sorted(os.listdir(BENCH))
                if os.path.isfile(os.path.join(BENCH, d, 'capsule.yaml'))]
        out(contract('list', data={'capsules': caps, 'count': len(caps)}))
    elif cmd == 'grade':
        cdir = (sys.argv[2] if len(sys.argv) > 2 else '').rstrip('/')
        ans = sys.argv[sys.argv.index('--answer') + 1] if '--answer' in sys.argv else None
        if not ans:
            out(contract('grade', False, message='缺少 --answer',
                         next_steps=['--answer <答案.md>，或 standard=对标准答案回归自评']))
            return
        ans_path = os.path.join(cdir, 'answer.md') if ans == 'standard' else ans
        if not os.path.isfile(ans_path):
            out(contract('grade', False, message='答案文件不存在：' + ans_path, next_steps=[]))
            return
        text = open(ans_path, encoding='utf-8').read()
        cap = open(os.path.join(cdir, 'capsule.yaml'), encoding='utf-8').read()
        std = [os.path.basename(l.strip()[2:]) for l in cap.splitlines()
               if l.strip().startswith('- data/')]
        cited = [s for s in std if os.path.basename(s) in text]
        coverage = round(len(cited) / len(std), 2) if std else 0
        keys_ok = len(re.findall(r'\([\w.\-]+#(?:表|图)\d+\)', text))
        score = round(0.7 * coverage + 0.3 * min(1.0, keys_ok / 10), 2)
        out(contract('grade', data={'capsule': os.path.basename(cdir), 'answer': ans_path,
                                    'standard_outputs': len(std), 'cited': len(cited),
                                    'coverage': coverage, 'evidence_keys': keys_ok,
                                    'score': score,
                                    'note': '三梯度 v1：覆盖率+键格式；LLM verifier 待 P2 接入'}))
    else:
        out(contract(cmd, False, message='未知子命令', next_steps=['pack | list | grade']))

if __name__ == '__main__':
    main()
