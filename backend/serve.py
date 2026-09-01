"""ServBay 仿真部署入口 — 单进程生产模式（无 werkzeug reloader）。

天翼云线上由 gunicorn 承载 (docker/nginx 反代 :5200)，
本机仿真用单进程 Flask 服务同一端口，避免 dev reloader 双进程残留。
用法: venv\Scripts\python serve.py
"""
import os

from run import app

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("FLASK_PORT", "5200")),
        debug=False,
    )
