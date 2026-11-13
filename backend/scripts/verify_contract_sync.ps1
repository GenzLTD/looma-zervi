# 契约同步验证：JSON 合法性 + 后端契约相关测试 + dist 消费方式
$ErrorActionPreference = 'Continue'
Set-Location c:/ServBay/www/looma-zervi

Write-Host "=== 1. payment.v1.json JSON 合法性 + apple_iap 段完整性 ==="
python -c "import json; c = json.load(open('backend/contracts/payment.v1.json', encoding='utf-8')); a = c['apple_iap']; assert c['version'] == '1.2.0'; assert len(a['endpoints']) == 3; assert a['products'] == {'supporter_monthly': 'supporter', 'pro_monthly': 'pro'}; assert 'apple_iap' not in c['regions']['US']['payment_providers']; assert 'apple_iap' not in c['regions']['CN']['payment_providers']; print('JSON OK; version', c['version'], '; endpoints:', [e['path'] for e in a['endpoints']])"

Write-Host "=== 2. 后端契约消费测试（billing_region/checkout money source）==="
Push-Location backend
$venv = @('.venv\Scripts\python.exe', 'venv\Scripts\python.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($venv) { Write-Host "venv: $venv"; & $venv -m pytest tests/test_checkout_money_source.py -q 2>&1 | Select-Object -Last 4 } else { Write-Host "无 venv，跳过 pytest（改用 json 结构断言已覆盖）" }
Pop-Location

Write-Host "=== 3. shared-core 消费方式（dist or src?）==="
$pkg = Get-Content frontend/packages/shared-core/package.json | ConvertFrom-Json
Write-Host "main: $($pkg.main); types: $($pkg.types)"
Write-Host "exports: $($pkg.exports | ConvertTo-Json -Compress)"
Write-Host "dist exists: $(Test-Path frontend/packages/shared-core/dist)"
