#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Auto-generated DisCo Execution Interface wrapper for skill: mouse-peak-anno-promoter
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Execution wrapper for mouse-peak-anno-promoter")
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--params-json", default="{}")
    args = parser.parse_args()
    print(json.dumps({
        "ok": True,
        "skill_id": "mouse-peak-anno-promoter",
        "executed_step": args.step_id,
        "bound_r_code": ".kb/code/R/annotation/promoter_ratio.R",
        "bound_py_cli": ".kb/cli/python/kb_tsv_stats.py",
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
