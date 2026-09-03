@echo off
REM ============================================================
REM looma-zervi ServBay 仿真环境一键启动（天翼云本地替身）
REM 前置：1) hosts 已加 looma-zervi.local -> 127.0.0.1
REM       2) 前端已构建（pnpm build:all）生成 planetx/saas dist
REM ============================================================
cd /d "%~dp0backend"

REM 清除 CodeBuddy shim 干扰（pip/python 子进程必需）
set PYTHONPATH=

REM 检查 venv
if not exist "venv\Scripts\python.exe" (
  echo [ERROR] venv 不存在，请先: python -m venv venv
  exit /b 1
)

REM 启动后端（后台最小化窗口）
start "looma-backend" /min venv\Scripts\python.exe run.py

timeout /t 3 >nul
echo.
echo [OK] looma-backend 已启动
echo      API:      http://looma-zervi.local/v1/  (或 http://127.0.0.1:5200)
echo      Health:   http://looma-zervi.local/health
echo      PlanetX:  http://looma-zervi.local/
echo      T-space:  http://looma-zervi.local/tspace/
echo.
echo 停止后端: 任务管理器结束 looma-backend 进程，或
echo           taskkill /FI "WINDOWTITLE eq looma-backend" /F
pause
