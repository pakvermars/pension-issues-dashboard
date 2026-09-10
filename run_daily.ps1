# 매일 아침 퇴직연금 주요 이슈를 수집해 화면을 갱신한다.
# Windows 작업 스케줄러가 이 스크립트를 호출한다.
# 절차 자체는 daily_update.md에 있고, 이 파일은 그걸 실행시키는 역할만 한다.

$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$log = Join-Path $logDir ('daily-' + (Get-Date -Format 'yyyy-MM') + '.log')

function Write-Log($message) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message" |
        Out-File -FilePath $log -Append -Encoding utf8
}

$claude = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
if (-not (Test-Path $claude)) {
    Write-Log "claude.exe를 찾지 못했습니다: $claude"
    exit 1
}

$prompt = 'daily_update.md 파일을 읽고 1번부터 9번까지의 절차를 그대로 수행하라. 오늘 날짜(KST) 기준으로 수집한다.'

Write-Log '수집 시작'

& $claude -p $prompt `
    --permission-mode acceptEdits `
    --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch Artifact `
    2>&1 | Out-File -FilePath $log -Append -Encoding utf8

Write-Log "수집 종료 (exit $LASTEXITCODE)"
