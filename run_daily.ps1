# 퇴직연금 주요 이슈를 수집해 화면을 갱신하고 GitHub Pages에 올린다.
# Windows 작업 스케줄러가 이 스크립트를 호출한다.
#
# 절차 자체는 daily_update.md에 있고, 이 파일은 그걸 실행시키는 역할만 한다.
# 게시(publish.ps1)는 Claude가 아니라 스크립트가 맡는다 — 헤드리스 세션에는
# Artifact 도구가 주입되지 않아 Claude가 웹에 올릴 방법이 없기 때문이다.

$ErrorActionPreference = 'Continue'

# claude.exe가 한글을 뱉으므로 콘솔 입출력을 UTF-8로 고정한다.
# 이걸 빼면 로그가 깨져 문제가 생겼을 때 원인을 볼 수 없다.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$log = Join-Path $logDir ('daily-' + (Get-Date -Format 'yyyy-MM') + '.log')

$utf8 = [System.Text.UTF8Encoding]::new($false)

function Write-Log($message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message"
    [System.IO.File]::AppendAllText($log, $line + [Environment]::NewLine, $utf8)
}

$claude = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
if (-not (Test-Path $claude)) {
    Write-Log "claude.exe를 찾지 못했습니다: $claude"
    exit 1
}

$prompt = 'daily_update.md 파일을 읽고 1번부터 8번까지의 절차를 그대로 수행하라. 오늘 날짜(KST) 기준으로 수집한다. 웹 게시(9번)는 스크립트가 따로 처리하므로 하지 않는다.'

Write-Log '수집 시작'

$output = & $claude -p $prompt `
    --permission-mode acceptEdits `
    --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch 2>&1

[System.IO.File]::AppendAllText($log, ($output | Out-String), $utf8)
Write-Log "수집 종료 (exit $LASTEXITCODE)"

# 수집이 실패했어도 이전 빌드 결과가 남아 있으면 게시는 시도한다.
& (Join-Path $root 'publish.ps1')
