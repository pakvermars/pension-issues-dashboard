# 수집 실행 잠금. run_daily.ps1이 점 소스로 읽어 쓴다.
#
# 게이트와 안전망 작업이 동시에 터질 수 있어 잠금이 필요하다. 문제는 잠금을
# 어떻게 푸느냐다. 프로세스가 급사하면 finally가 돌지 못해 파일이 남는데,
# 그걸 "진행 중"으로 읽으면 파이프라인이 조용히 멈춘다. 2026-09-23에 실제로
# 그렇게 11시간을 멈췄다.
#
# 그래서 나이가 아니라 주인의 생사로 판단한다. 잠금 파일에 PID와 그 프로세스의
# 시작 시각을 적어 두고, 주인이 살아 있을 때만 잠금으로 인정한다.
# 시작 시각까지 보는 것은 PID가 돌려 쓰이기 때문이다.

# PID를 적지 않던 옛 잠금 파일에만 쓰는 값. 그때는 나이로 짐작하는 수밖에 없다.
$script:LegacyStaleMinutes = 15

function Get-RunLockState {
    <#
        잠금 상태를 Held(유효한가)와 Reason(왜 그렇게 봤나)으로 돌려준다.
        Reason은 로그에 그대로 남겨 나중에 원인을 볼 수 있게 한다.
    #>
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path $Path)) {
        return [PSCustomObject]@{ Held = $false; Reason = '잠금 없음' }
    }

    $minutes = [int]((Get-Date) - (Get-Item $Path).LastWriteTime).TotalMinutes

    $raw = ''
    try { $raw = Get-Content -Path $Path -Raw -ErrorAction Stop } catch { $raw = '' }
    if ($null -eq $raw) { $raw = '' }

    $ownerPid = 0
    $ownerStart = ''
    if ($raw -match 'PID=(\d+)') { $ownerPid = [int]$Matches[1] }
    if ($raw -match 'START=(\S+)') { $ownerStart = $Matches[1] }

    if ($ownerPid -le 0) {
        if ($minutes -lt $script:LegacyStaleMinutes) {
            return [PSCustomObject]@{ Held = $true; Reason = "PID 없는 잠금, ${minutes}분 전 것" }
        }
        return [PSCustomObject]@{ Held = $false; Reason = "PID 없는 잠금이 ${minutes}분째 남아 있다" }
    }

    $proc = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    if (-not $proc) {
        return [PSCustomObject]@{ Held = $false; Reason = "주인 프로세스(PID $ownerPid)가 없다" }
    }

    if ($ownerStart) {
        $procStart = ''
        try { $procStart = $proc.StartTime.ToString('o') } catch { $procStart = '' }
        if ($procStart -and $procStart -ne $ownerStart) {
            return [PSCustomObject]@{ Held = $false; Reason = "PID $ownerPid 가 다른 프로세스로 재사용됐다" }
        }
    }

    # 주인이 살아 있으면 오래 걸리는 중일 뿐이다. 시간으로 잠금을 빼앗지 않는다.
    # 예약 실행은 작업 스케줄러의 30분 제한이 따로 끊어 준다.
    return [PSCustomObject]@{ Held = $true; Reason = "PID $ownerPid 가 ${minutes}분째 수집 중" }
}

function Test-RunLockHeld {
    param([Parameter(Mandatory)][string]$Path)
    (Get-RunLockState -Path $Path).Held
}

function Set-RunLock {
    param([Parameter(Mandatory)][string]$Path)

    $start = ''
    try { $start = (Get-Process -Id $PID).StartTime.ToString('o') } catch { $start = '' }

    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -Path $Path -Value "PID=$PID START=$start" -Encoding utf8 -Force
}

function Remove-RunLock {
    param([Parameter(Mandatory)][string]$Path)
    Remove-Item $Path -Force -ErrorAction SilentlyContinue
}
