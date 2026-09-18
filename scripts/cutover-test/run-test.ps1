# ============================================================================
# 摘块预演门禁（Windows / ServBay）
# ============================================================================
#
# 与 run-test.sh 同口径：证明摘掉 nginx 里 genz.ltd / www.genz.ltd 的 server 块
# 之后，① api /health 与 /v1/payment/webhook/* 仍可达；② tspace 不受影响；
# ③ 裸域落 catch-all → 404 Unknown host。
#
# 形态：用 ServBay 自带 nginx 在 18080 加载「摘块后」的 HTTP 配置
#       （对应 Cloudflare Flexible 回源 :80），用 127.0.0.1:15200 的 stub 顶 :5200。
#
# 用法（管理员或普通用户均可，需能监听 18080/15200）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\cutover-test\run-test.ps1
#
# 可选参数：
#   -NginxPort 18080  -StubPort 15200
#   -NginxExe  C:\ServBay\packages\nginx\nginx.exe
#   -PythonExe <python.exe 路径>
#
# 退出码：0 = 全绿；1 = 有断言失败或前置检查不过。
# ============================================================================

[CmdletBinding()]
param(
    [int]$NginxPort = 18080,
    [int]$StubPort  = 15200,
    [string]$NginxExe = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$Here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $Here "..\..")).Path
$Work     = Join-Path $Here ".generated"

$ConfMain     = Join-Path $RepoRoot "docker\nginx.conf"
$ConfVultr    = Join-Path $RepoRoot "nginx-vultr.conf"
$ConfTemplate = Join-Path $Here "nginx-cutover-http.conf"

$script:Failed = $false
$nginxProc = $null
$stubProc  = $null

function Write-Pass($msg) { Write-Host "  PASS  $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL  $msg" -ForegroundColor Red; $script:Failed = $true }
function Write-Note($msg) { Write-Host "        $msg" -ForegroundColor DarkGray }

# ---------------------------------------------------------------- 工具函数
function Get-ServerNameTokens([string]$Path) {
    $out = @()
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        if ($line -match '^\s*server_name\s+') {
            $body = $line -replace ';.*$', '' -replace '^\s*server_name\s+', ''
            $out += ($body -split '\s+' | Where-Object { $_ -ne '' })
        }
    }
    return ($out | Sort-Object -Unique)
}

function Get-BareDomainHits([string]$Path) {
    $hits = @()
    $n = 0
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        $n++
        if ($line -match '^\s*server_name\s+') {
            $body = $line -replace ';.*$', '' -replace '^\s*server_name\s+', ''
            $tokens = ($body -split '\s+' | Where-Object { $_ -ne '' })
            if ($tokens -contains 'genz.ltd' -or $tokens -contains 'www.genz.ltd') {
                $hits += "$n : $line"
            }
        }
    }
    return $hits
}

function Find-Nginx {
    if ($NginxExe -and (Test-Path $NginxExe)) { return (Resolve-Path $NginxExe).Path }
    $candidates = @(
        "C:\ServBay\packages\nginx\nginx.exe",
        "C:\ServBay\bin\nginx\nginx.exe",
        "C:\ServBay\sbin\nginx.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command nginx.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return ""
}

function Find-Python {
    if ($PythonExe -and (Test-Path $PythonExe)) { return (Resolve-Path $PythonExe).Path }
    foreach ($name in @("python.exe", "python3.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    foreach ($c in @("C:\ServBay\packages\python\python.exe", "C:\ServBay\bin\python\python.exe")) {
        if (Test-Path $c) { return $c }
    }
    return ""
}

function Invoke-HttpCheck {
    param(
        [string]$Host_,
        [string]$Method,
        [string]$Path,
        [int]$ExpectCode,
        [string]$ExpectBody
    )

    $uri = "http://127.0.0.1:$NginxPort$Path"
    $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue)
    if (-not $curl) { $curl = (Get-Command curl -ErrorAction SilentlyContinue) }

    $code = ""
    $bodyText = ""

    if ($curl) {
        # 单次请求：body 落临时文件，状态码走 stdout（避免重复打 webhook）
        $tmp = Join-Path $Work "resp.txt"
        if ($Method -eq "POST") {
            $code = & $curl.Source -s -o $tmp -w "%{http_code}" -X POST `
                    -H "Host: $Host_" -H "Content-Type: application/json" -d "{}" $uri
        } else {
            $code = & $curl.Source -s -o $tmp -w "%{http_code}" -H "Host: $Host_" $uri
        }
        $bodyText = if (Test-Path $tmp) { Get-Content $tmp -Raw } else { "" }
    } else {
        # Fallback：Invoke-WebRequest（PS 5.1 需 try/catch 读异常里的状态码）
        try {
            $resp = Invoke-WebRequest -Uri $uri -Headers @{ Host = $Host_ } -Method $Method -UseBasicParsing
            $code = [string]$resp.StatusCode
            $bodyText = [string]$resp.Content
        } catch {
            if ($_.Exception.Response) {
                $code = [string]([int]$_.Exception.Response.StatusCode)
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $bodyText = $reader.ReadToEnd()
            } else {
                $code = "ERR"
                $bodyText = $_.Exception.Message
            }
        }
    }

    $desc = "$Host_ $Method$Path → $ExpectCode"
    if ("$code" -ne "$ExpectCode") {
        Write-Fail $desc
        Write-Note "期望 HTTP $ExpectCode，实际 HTTP $code"
        Write-Note "body: $($bodyText -replace '\s+', ' ' | Select-Object -First 1)"
        return
    }
    if ($ExpectBody -and ($bodyText -notmatch [regex]::Escape($ExpectBody))) {
        Write-Fail $desc
        Write-Note "HTTP $code 正确，但 body 未含 '$ExpectBody'"
        Write-Note "body: $($bodyText -replace '\s+', ' ' | Select-Object -First 1)"
        return
    }
    Write-Pass "$desc  $code"
}

function Stop-TestProcesses {
    foreach ($p in @($nginxProc, $stubProc)) {
        if ($p -and -not $p.HasExited) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
        }
    }
    # nginx master 被强杀后可能留 worker，按 pid 文件兜底
    $pidFile = Join-Path $Work "nginx.pid"
    if (Test-Path $pidFile) {
        $p = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($p) { try { Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue } catch { } }
    }
}

# ---------------------------------------------------------------- 主流程
Write-Host ""
Write-Host "=== 摘块预演门禁 (cutover-test, Windows) ==="
Write-Host ""

try {
    foreach ($f in @($ConfMain, $ConfVultr, $ConfTemplate)) {
        if (-not (Test-Path $f)) { Write-Fail "缺少文件：$f"; exit 1 }
    }

    # A1 — 真配置里不得残留裸域 server_name（本 PR 的核心断言）
    foreach ($f in @($ConfMain, $ConfVultr)) {
        $hits = Get-BareDomainHits $f
        if ($hits.Count -gt 0) {
            Write-Fail "$(Split-Path -Leaf $f) 仍残留裸域 server 块"
            foreach ($h in $hits) { Write-Note $h }
        } else {
            Write-Pass "$(Split-Path -Leaf $f) 无 genz.ltd / www.genz.ltd server_name"
        }
    }

    # A2 — 模板与真配置的 Host 集合必须一致（防装置漂移）
    $hMain = (Get-ServerNameTokens $ConfMain) -join ' '
    $hTpl  = (Get-ServerNameTokens $ConfTemplate) -join ' '
    if ($hMain -eq $hTpl) {
        Write-Pass "预演配置 Host 集合与 docker/nginx.conf 一致"
        Write-Note $hMain
    } else {
        Write-Fail "预演配置与 docker/nginx.conf 的 Host 集合不一致（装置漂移）"
        Write-Note "真配置: $hMain"
        Write-Note "预演  : $hTpl"
        Write-Note "改了 docker/nginx.conf 的 server_name 后，请同步 nginx-cutover-http.conf"
    }

    if ($script:Failed) {
        Write-Host ""
        Write-Host "前置检查未通过，未启动预演。" -ForegroundColor Red
        exit 1
    }

    $nginx = Find-Nginx
    if (-not $nginx) { Write-Fail "找不到 nginx.exe（用 -NginxExe 指定）"; exit 1 }
    $python = Find-Python
    if (-not $python) { Write-Fail "找不到 python.exe（用 -PythonExe 指定）"; exit 1 }

    Write-Host ""
    Write-Note "nginx   : $nginx"
    Write-Note "python  : $python"
    Write-Note "nginx port=$NginxPort  stub port=$StubPort"

    # ------------------------------------------------------------ 渲染配置
    if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
    New-Item -ItemType Directory -Path (Join-Path $Work "www\tspaces") -Force | Out-Null

    @"
types {
    text/html                             html htm;
    text/css                              css;
    application/javascript                js mjs;
    application/json                      json;
    image/png                             png;
    image/svg+xml                         svg;
    font/woff2                            woff2;
}
"@ | Set-Content -Path (Join-Path $Work "mime.types") -Encoding ASCII

    @"
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>tspace stub</title></head>
<body><h1>tspace stub</h1><p>cutover-test placeholder SPA</p></body></html>
"@ | Set-Content -Path (Join-Path $Work "www\tspaces\index.html") -Encoding UTF8

    $workFwd = $Work.Replace("\", "/")
    $prefix  = "$workFwd/"

    # ------------------------------------------------------------ A3 真配置语法校验
    # 删 server 块最容易的事故是改坏大括号配对（留下孤立 } 或吞掉下一块开头）。
    # 这里对两份真配置本身跑 nginx -t：只把 include 指到本地 mime.types，
    # 并摘掉 ssl（本机没有生产证书）。
    Write-Host ""
    Write-Host "--- A3 真配置语法校验 ---"
    foreach ($f in @($ConfMain, $ConfVultr)) {
        $base = Split-Path -Leaf $f
        $rendered = Join-Path $Work "syntax-$base"
        $txt = Get-Content -LiteralPath $f -Raw
        $txt = $txt -replace 'include\s+/etc/nginx/mime\.types;', "include $workFwd/mime.types;"
        $txt = $txt -replace 'listen\s+443\s+ssl\s+http2;', 'listen 1443;'
        $txt = $txt -replace '(?m)^(\s*)ssl_certificate\s', '$1#ssl_certificate '
        $txt = $txt -replace '(?m)^(\s*)ssl_certificate_key\s', '$1#ssl_certificate_key '
        Set-Content -Path $rendered -Value $txt -Encoding UTF8

        $openN  = ([regex]::Matches($txt, '\{')).Count
        $closeN = ([regex]::Matches($txt, '\}')).Count
        if ($openN -ne $closeN) {
            Write-Fail "$base 大括号不配对：{ x$openN vs } x$closeN"
            continue
        }

        $out = & $nginx -t -p $prefix -c ("$workFwd/syntax-$base") 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "$base nginx -t 通过（braces $openN/$closeN）"
        } else {
            Write-Fail "$base nginx -t 失败"
            $out | ForEach-Object { Write-Note $_ }
        }
    }

    if ($script:Failed) {
        Write-Host ""
        Write-Host "前置检查未通过，未启动预演。" -ForegroundColor Red
        exit 1
    }

    $tpl = Get-Content -LiteralPath $ConfTemplate -Raw
    $tpl = $tpl.Replace("__WORK__",        $Work)
    $tpl = $tpl.Replace("__LISTEN__",      "$NginxPort")
    $tpl = $tpl.Replace("__UPSTREAM__",    "127.0.0.1:$StubPort")
    $tpl = $tpl.Replace("__MIME_TYPES__",  (Join-Path $Work "mime.types"))
    $tpl = $tpl.Replace("__TSPACE_ROOT__", (Join-Path $Work "www\tspaces"))
    $tpl = $tpl.Replace("\", "/")
    Set-Content -Path (Join-Path $Work "nginx.conf") -Value $tpl -Encoding UTF8

    # ------------------------------------------------------------ 起 stub
    Write-Host ""
    Write-Host "--- 启动 stub (127.0.0.1:$StubPort) ---"
    $stubProc = Start-Process -FilePath $python `
        -ArgumentList @((Join-Path $Here "stub_api.py"), "--host", "127.0.0.1", "--port", "$StubPort") `
        -RedirectStandardOutput (Join-Path $Work "stub.log") `
        -RedirectStandardError  (Join-Path $Work "stub.err.log") `
        -PassThru -WindowStyle Hidden

    $stubReady = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$StubPort/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $stubReady = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (-not $stubReady) {
        Write-Fail "stub 未在 10s 内就绪"
        Write-Note "日志：$Work\stub.log / stub.err.log"
        exit 1
    }
    Write-Pass "stub 就绪"

    # ------------------------------------------------------------ 起 nginx
    Write-Host ""
    Write-Host "--- 校验并启动 nginx (端口 $NginxPort) ---"
    $confArg = "$workFwd/nginx.conf"

    $t = & $nginx -t -p $prefix -c $confArg 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "nginx -t 配置校验失败"
        $t | ForEach-Object { Write-Note $_ }
        exit 1
    }
    Write-Pass "nginx -t 通过"

    $nginxProc = Start-Process -FilePath $nginx -ArgumentList @("-p", $prefix, "-c", $confArg) `
        -RedirectStandardOutput (Join-Path $Work "nginx.log") `
        -RedirectStandardError  (Join-Path $Work "nginx.err.log") `
        -PassThru -WindowStyle Hidden

    $nginxReady = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$NginxPort/health" -Headers @{ Host = "api.genz.ltd" } -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $nginxReady = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (-not $nginxReady) {
        Write-Fail "nginx 未在 10s 内响应"
        Write-Note "日志：$Work\nginx.err.log / error.log"
        exit 1
    }
    Write-Pass "nginx 就绪 (pid $($nginxProc.Id))"

    # ------------------------------------------------------------ 断言
    Write-Host ""
    Write-Host "--- Host 探测断言 ---"

    Invoke-HttpCheck -Host_ "api.genz.ltd"    -Method "GET"  -Path "/health"                       -ExpectCode 200 -ExpectBody '"status": "ok"'
    Invoke-HttpCheck -Host_ "api.genz.ltd"    -Method "GET"  -Path "/"                             -ExpectCode 404 -ExpectBody 'Use /v1'
    Invoke-HttpCheck -Host_ "api.genz.ltd"    -Method "POST" -Path "/v1/payment/webhook/stripe"    -ExpectCode 200 -ExpectBody '"received": true'
    Invoke-HttpCheck -Host_ "tspace.genz.ltd" -Method "GET"  -Path "/"                             -ExpectCode 200 -ExpectBody 'tspace stub'
    Invoke-HttpCheck -Host_ "genz.ltd"        -Method "GET"  -Path "/"                             -ExpectCode 404 -ExpectBody 'Unknown host'
    Invoke-HttpCheck -Host_ "www.genz.ltd"    -Method "GET"  -Path "/"                             -ExpectCode 404 -ExpectBody 'Unknown host'

    Write-Host ""
    if (-not $script:Failed) {
        Write-Host "全绿：摘块不切 api webhook，不误伤 tspace，裸域落 catch-all。" -ForegroundColor Green
        Write-Host ""
        Write-Note "不能代替：真 Flask、真 SaaS 构建、HTTPS 443、DNS 真实切换。"
        Write-Host ""
        exit 0
    }
    Write-Host "有断言失败，见上。" -ForegroundColor Red
    Write-Host ""
    Write-Note "stub 日志：$Work\stub.log"
    Write-Note "nginx 日志：$Work\nginx.err.log"
    Write-Host ""
    exit 1
}
finally {
    Write-Host ""
    Write-Host "--- 清理 ---" -ForegroundColor DarkGray
    Stop-TestProcesses
    Write-Host "已停止 nginx / stub（ServBay 自身的 80/443 不受影响）。" -ForegroundColor DarkGray
}
