#!/usr/bin/env bash
# ControlTower 看板：扫描磁盘 → board.db（SQLite 派生缓存）→ index.html
# 用法：ws_board.sh          # 生成/刷新看板
#       sqlite3 .ws/board/board.db "SELECT ..."   # 直接 SQL 查询缓存
exec python3 "$(dirname "$0")/ws_board.py"
