# 새 기사가 있을 때만 수집을 돌린다.
#
# 작업 스케줄러가 15분마다 이 스크립트를 부른다. 대부분은 20초쯤 긁어 보고
# 새 기사가 없어 그냥 끝난다. 비싼 단계(claude -p 수집 세션, 2~3분)는
# 실제로 새 기사가 있을 때만 run_daily.ps1을 통해 돈다.
#
# 판단은 gate.py가 하고, 이 파일은 종료 코드로 갈림길만 고른다.
#   0  → 수집한다    10 → 건너뛴다

$ErrorActionPreference = 'Continue'

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# 게이트는 하루 50번 넘게 돈다. 일간 로그에 섞으면 수집 기록이 묻히므로
# 따로 쌓는다.
$log = Join-Path $logDir ('gate-' + (Get-Date -Format 'yyyy-MM') + '.log')
$utf8 = [System.Text.UTF8Encoding]::new($false)

function Write-Log($message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message"
    [System.IO.File]::AppendAllText($log, $line + [Environment]::NewLine, $utf8)
}

$decision = & python -X utf8 (Join-Path $root 'gate.py') 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Log ($decision.Trim())

if ($code -eq 10) {
    exit 0
}

Write-Log '수집을 부른다'
& (Join-Path $root 'run_daily.ps1')
exit 0
