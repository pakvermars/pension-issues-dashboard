# 빌드 결과를 GitHub Pages에 올린다.
#
# run_daily.ps1이 수집·빌드를 마친 뒤 이 스크립트를 부른다.
# claude -p 헤드리스 세션에는 Artifact 도구가 주입되지 않아 웹 게시를 할 수 없다.
# 그래서 게시는 Claude가 아니라 이 결정적인 스크립트가 맡는다.

$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$log = Join-Path $logDir ('daily-' + (Get-Date -Format 'yyyy-MM') + '.log')

function Write-Log($message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message"
    [System.IO.File]::AppendAllText($log, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

if (-not (Test-Path (Join-Path $root 'index.html'))) {
    Write-Log '게시 중단: index.html이 없다'
    exit 1
}

# 원격이 없으면 아직 설정 전이다. 조용히 넘어간다.
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Log '게시 건너뜀: git 원격(origin)이 설정되지 않았다'
    exit 0
}

git add -A 2>&1 | Out-Null

# 바뀐 게 없으면 커밋하지 않는다. 빈 커밋이 쌓이면 이력이 지저분해진다.
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log '게시 건너뜀: 변경 사항 없음'
    exit 0
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
git commit -q -m "data: $stamp 이슈 갱신" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log "게시 실패: 커밋 오류 (exit $LASTEXITCODE)"
    exit 1
}

$push = git push origin HEAD 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "게시 실패: push 오류 (exit $LASTEXITCODE) $push"
    exit 1
}

Write-Log "게시 완료: $stamp"
exit 0
