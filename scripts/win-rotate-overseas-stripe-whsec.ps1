# Win-side: Owner Roll 之后，把新 Live whsec 写入 GitHub + Vultr。
# 禁止把密钥贴进聊天。从 stdin 读入，用完不回显。
#
# 用法（PowerShell）:
#   Get-Content -Raw .\whsec.txt | .\scripts\win-rotate-overseas-stripe-whsec.ps1
#   然后立即删除 whsec.txt
#
# 本脚本:
#   1) gh secret set ENV_STRIPE_WEBHOOK_SECRET
#   2) ssh vultr 覆盖机器 .env 中这一键
#   3) 只 recreate looma-backend
#   4) 打印 sha256[:12] 供与 Owner 口头对账
#
# 若 rotate-overseas-stripe.yml 已合入 main，也可只做第 1 步，再:
#   gh workflow run "Rotate Overseas Stripe webhook" -R GenzLTD/looma-zervi -f confirm=rotate-stripe

[CmdletBinding()]
param(
    [string]$Repo = "GenzLTD/looma-zervi",
    [string]$SshHostAlias = "vultr",
    [string]$EnvFile = "/opt/looma-zervi/backend/.env"
)

$ErrorActionPreference = "Stop"

$raw = [Console]::In.ReadToEnd()
if (-not $raw) {
    throw "stdin empty. Pipe the new Live whsec; do not pass as argument."
}
$whsec = $raw.Trim()
if (-not $whsec.StartsWith("whsec_")) {
    throw "refuse: value does not look like a Stripe signing secret"
}

$sha = [System.BitConverter]::ToString(
    [System.Security.Cryptography.SHA256]::Create().ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes($whsec)
    )
).Replace("-", "").ToLower().Substring(0, 12)

Write-Host "local sha256[:12]=$sha (not the secret)"

$whsec | gh secret set ENV_STRIPE_WEBHOOK_SECRET -R $Repo
Write-Host "GitHub ENV_STRIPE_WEBHOOK_SECRET updated for $Repo"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($whsec))

$remote = @'
set -euo pipefail
python3 - <<PY
import base64, hashlib, pathlib
val = base64.b64decode("__B64__").decode("utf-8").strip()
if not val.startswith("whsec_"):
    raise SystemExit("refuse: not a whsec")
p = pathlib.Path("__ENV_FILE__")
lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
out, found = [], False
for line in lines:
    if line.startswith("STRIPE_WEBHOOK_SECRET="):
        out.append("STRIPE_WEBHOOK_SECRET=" + val)
        found = True
    else:
        out.append(line)
if not found:
    out.append("STRIPE_WEBHOOK_SECRET=" + val)
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("machine sha256[:12]=%s" % hashlib.sha256(val.encode()).hexdigest()[:12])
PY
docker compose --env-file /opt/looma-zervi/backend/.env \
  -f /opt/looma-zervi/docker/docker-compose.yml \
  -p looma-zervi \
  up -d --no-build --force-recreate backend
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:5200/health >/dev/null 2>&1; then
    echo "backend healthy after ${i}s"
    curl -sf http://127.0.0.1:5200/health; echo
    exit 0
  fi
  sleep 2
done
echo "backend failed to become healthy"
exit 1
'@

$remote = $remote.Replace("__B64__", $b64).Replace("__ENV_FILE__", $EnvFile)
$remote = $remote -replace "`r`n", "`n"
$remote | ssh -o BatchMode=yes $SshHostAlias "tr -d '\r' | bash"

Write-Host "done. Owner: Dashboard Send test webhook, expect 200, then Resend evt_1UGgHB."
Write-Host "Do not type the secret here. Compare only sha256[:12]=$sha"
