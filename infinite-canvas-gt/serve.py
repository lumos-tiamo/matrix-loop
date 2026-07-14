#!/usr/bin/env python3
"""无头启动入口 —— 不开浏览器、监听可配置、随进程拉起作业执行器。

用法:
    python3 serve.py                 # 读 .env / 环境变量
    HOST=0.0.0.0 APP_TOKEN=xxx python3 serve.py   # 局域网(需 token)

设计成服务化常驻（见 launchd/）。默认无头 + 关闭 GitHub 自更新。
"""

import os

# 在 import main 之前设默认（main 在 import 时即读取这些环境变量）
os.environ.setdefault("HEADLESS", "1")
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("ENABLE_SELF_UPDATE", "0")

import uvicorn  # noqa: E402

from main import app, SERVER_HOST, SERVER_PORT  # noqa: E402

if __name__ == "__main__":
    print(f"[infinite-canvas-gt] 无头服务启动于 http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        ws_ping_interval=None,
        ws_ping_timeout=None,
    )
