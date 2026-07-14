#!/usr/bin/env bash
# 安装 Infinite-Canvas-GT 无头服务为 macOS launchd 常驻服务（开机自启 + 崩溃重拉）。
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${APP_DIR}/.venv/bin/python"
LABEL="com.matrixloop.infinite-canvas-gt"
DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
TEMPLATE="${APP_DIR}/launchd/${LABEL}.plist"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "❌ 未找到虚拟环境 python：${VENV_PYTHON}"
  echo "   先建环境：cd ${APP_DIR} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "${APP_DIR}/data" "${HOME}/Library/LaunchAgents"
sed -e "s#__VENV_PYTHON__#${VENV_PYTHON}#g" \
    -e "s#__APP_DIR__#${APP_DIR}#g" \
    "${TEMPLATE}" > "${DEST}"

launchctl unload "${DEST}" 2>/dev/null || true
launchctl load "${DEST}"
echo "✅ 已安装并启动：${LABEL}"
echo "   查看状态: launchctl list | grep infinite-canvas-gt"
echo "   停止:     launchctl unload ${DEST}"
echo "   日志:     ${APP_DIR}/data/infinite-canvas-gt.{out,err}.log"
