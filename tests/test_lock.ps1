# 실행 잠금 판단 테스트.
#
#   pwsh -NoProfile -File tests\test_lock.ps1
#
# 이 로직이 틀리면 둘 중 하나가 된다: 수집 둘이 동시에 돌아 git이 엉키거나,
# 죽은 프로세스의 잠금에 막혀 파이프라인이 조용히 멈춘다. 후자가 실제로
# 2026-09-23에 11시간 정지를 냈다.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. (Join-Path $root 'lock.ps1')

$script:failed = 0
$script:ran = 0

function Check($name, $actual, $expected) {
    $script:ran++
    if ($actual -eq $expected) {
        Write-Host "  OK   $name"
    } else {
        $script:failed++
        Write-Host "  FAIL $name (기대 $expected, 실제 $actual)" -ForegroundColor Red
    }
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("locktest-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
$lock = Join-Path $tmp '.run.lock'

try {
    Check '잠금 파일이 없으면 비어 있다' (Test-RunLockHeld $lock) $false

    # 지금 이 프로세스가 쥔 잠금은 유효하다.
    Set-RunLock $lock
    Check '살아 있는 주인의 잠금은 유효하다' (Test-RunLockHeld $lock) $true

    # 없는 PID를 적어 두면 주인이 죽은 것이다.
    Set-Content -Path $lock -Value 'PID=999999 START=2026-09-23T07:00:00.0000000+09:00' -Encoding utf8
    Check '없는 PID의 잠금은 무효다' (Test-RunLockHeld $lock) $false

    # PID는 살아 있지만 시작 시각이 다르면 PID가 재사용된 것이다.
    Set-Content -Path $lock -Value "PID=$PID START=1999-01-01T00:00:00.0000000+09:00" -Encoding utf8
    Check 'PID가 재사용된 잠금은 무효다' (Test-RunLockHeld $lock) $false

    # PID를 못 읽는 옛 형식은 나이로 판단한다.
    Set-Content -Path $lock -Value '' -Encoding utf8
    (Get-Item $lock).LastWriteTime = (Get-Date).AddMinutes(-2)
    Check '옛 형식 잠금은 최근 것이면 유효하다' (Test-RunLockHeld $lock) $true

    (Get-Item $lock).LastWriteTime = (Get-Date).AddMinutes(-40)
    Check '옛 형식 잠금은 오래된 것이면 무효다' (Test-RunLockHeld $lock) $false

    # Reason은 로그에 남는 진단이다. 몇 분째인지 숫자가 반드시 들어가야 한다.
    Set-RunLock $lock
    (Get-Item $lock).LastWriteTime = (Get-Date).AddMinutes(-7)
    Check 'Reason에 경과 분이 들어간다' ((Get-RunLockState $lock).Reason -match '7분') $true

    Set-Content -Path $lock -Value '' -Encoding utf8
    (Get-Item $lock).LastWriteTime = (Get-Date).AddMinutes(-40)
    Check '옛 형식 Reason에도 경과 분이 들어간다' ((Get-RunLockState $lock).Reason -match '40분') $true

    # 해제하면 파일이 사라진다.
    Set-RunLock $lock
    Remove-RunLock $lock
    Check '잠금을 풀면 파일이 사라진다' (Test-Path $lock) $false
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
if ($script:failed -gt 0) {
    Write-Host "${script:ran}개 중 ${script:failed}개 실패" -ForegroundColor Red
    exit 1
}
Write-Host "${script:ran}개 모두 통과"
exit 0
