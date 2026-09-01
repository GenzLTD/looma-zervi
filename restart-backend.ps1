# looma-zervi 后端重启脚本（ServBay 仿真）
# 用法: powershell -ExecutionPolicy Bypass -File restart-backend.ps1
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'looma-zervi' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 2

$env:PYTHONPATH = ''   # 清除 CodeBuddy shim 干扰
Set-Location 'C:\ServBay\www\looma-zervi\backend'

$p = Start-Process -FilePath 'venv\Scripts\python.exe' -ArgumentList 'serve.py' `
    -RedirectStandardOutput '..\server_out.log' `
    -RedirectStandardError '..\server_err.log' `
    -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 8

# 报告实际监听 5200 的 PID（Start-Process 返回的可能是 venv launcher PID）
$listener = Get-NetTCPConnection -LocalPort 5200 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    Write-Host "BACKEND_LISTEN_PID=$($listener.OwningProcess)"
} else {
    Write-Host 'BACKEND_LISTEN_PID=NONE (启动失败?)'
}

try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:5200/health' -TimeoutSec 10
    Write-Host "HEALTH status=$($r.status) llm_configured=$($r.llm_configured)"
} catch {
    Write-Host "HEALTH_FAIL: $_"
}
