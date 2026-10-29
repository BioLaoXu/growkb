#!/usr/bin/env bash
# ControlTower 看板服务：start / stop / restart
# 页面：http://localhost:8792/   （静态文件 + /api/state + 写操作 API，绑定 127.0.0.1）
BIN="$(cd "$(dirname "$0")" && pwd)"
case "${1:-start}" in
  start)
    PID=$(ss -ltnp 2>/dev/null | grep ':8792 ' | grep -oP 'pid=\K[0-9]+' | head -1)
    [[ -n "$PID" ]] && { echo "8792 已被 pid=$PID 占用，先停止"; kill "$PID"; sleep 1; }
    nohup python3 "$BIN/ws_board.py" >> /tmp/ws_board.log 2>&1 &
    sleep 1
    curl -s -o /dev/null -w "看板服务：HTTP %{http_code}\n" http://127.0.0.1:8792/api/state
    echo "页面：http://localhost:8792/   日志：/tmp/ws_board.log" ;;
  stop)
    PID=$(ss -ltnp 2>/dev/null | grep ':8792 ' | grep -oP 'pid=\K[0-9]+' | head -1)
    [[ -n "$PID" ]] && { kill "$PID"; echo "已停止 pid=$PID"; } || echo "未在运行" ;;
  restart) "$0" stop; sleep 1; "$0" start ;;
  *) echo "用法：ws_board.sh start|stop|restart" ;;
esac
