#!/usr/bin/env bash
# 扫描所有 META.yaml，重建项目级与全局 INDEX.md
# 用法：.ws/bin/ws_index.sh
#
# 渲染逻辑在 ws_index.py，元数据解析在 ws_meta.py（与台账 ws_ledger.py 共用），
# 保证「索引」与「台账」看到的是同一份事实。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
exec python3 "$WS_ROOT/.ws/bin/ws_index.py" --root "$WS_ROOT"
