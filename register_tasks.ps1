# 수집을 돌리는 작업 스케줄러 작업 두 개를 등록하거나 고친다.
#
#   pwsh -NoProfile -File register_tasks.ps1          # 등록 / 복구
#   pwsh -NoProfile -File register_tasks.ps1 -Check   # 검사만, 고치지 않음
#
# 왜 이 파일이 있나 ─────────────────────────────────────────────
# 2026-10-15에 PowerShell이 7.6.6.0에서 7.6.7.0으로 올라갔다. 작업이 부르던
# 실행 파일 경로에 버전 번호가 박혀 있어서(.../Microsoft.PowerShell_7.6.6.0_x64.../pwsh.exe)
# 업데이트와 동시에 그 폴더가 사라졌다. 작업은 ERROR_FILE_NOT_FOUND로 즉사했고,
# 실행 파일을 못 찾았으니 로그조차 남기지 못했다. 파이프라인이 엿새를 멈췄다.
#
# 설정이 어디에도 적혀 있지 않으면 작업을 다시 만들 때 같은 경로가 또 들어간다.
# 그래서 등록 절차를 여기 두고, 버전이 박힌 경로는 아예 거부한다.

[CmdletBinding()]
param([switch]$Check)

$ErrorActionPreference = 'Stop'

function Test-VersionPinned {
    <# 경로에 1.2.3 꼴의 버전이 박혀 있나. 업데이트가 오면 사라질 경로다. #>
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return [bool]($Path -match '\d+\.\d+\.\d+')
}

function Test-StablePwshPath {
    <# 작업에 적어도 되는 경로인가. 지금 존재하고, 업데이트에도 살아남아야 한다. #>
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (Test-VersionPinned $Path) { return $false }
    return (Test-Path -LiteralPath $Path -PathType Leaf)
}

function Resolve-StablePwsh {
    <# 쓸 만한 pwsh를 앞에서부터 고른다. 없으면 빈 문자열. #>
    $candidates = @(
        # Store판의 앱 실행 별칭. 버전이 올라가도 이 경로는 그대로다.
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\Microsoft.PowerShell_8wekyb3d8bbwe\pwsh.exe'),
        # MSI판. 설치돼 있으면 7 아래에 버전 없이 놓인다.
        'C:\Program Files\PowerShell\7\pwsh.exe'
    )
    foreach ($c in $candidates) {
        if (Test-StablePwshPath $c) { return $c }
    }
    return ''
}

# ── 작업 정의 ─────────────────────────────────────────────────
# 2026-10-21 시점의 실제 설정을 그대로 옮긴 것이다. 바꾸려면 여기를 고친다.
function Get-TaskPlan {
    param([string]$Root)
    @(
        [PSCustomObject]@{
            Name       = '퇴직연금 주요 이슈 게이트'
            Script     = Join-Path $Root 'run_gate.ps1'
            StartTime  = '07:00'
            Interval   = (New-TimeSpan -Minutes 15)
            Duration   = (New-TimeSpan -Hours 13)
            OnBattery  = $false   # 배터리로 바뀌면 멈춘다(데스크톱이라 무관)
        },
        [PSCustomObject]@{
            Name       = '퇴직연금 주요 이슈 데일리'
            Script     = Join-Path $Root 'run_daily.ps1'
            StartTime  = '07:37'
            Interval   = (New-TimeSpan -Hours 3)
            Duration   = (New-TimeSpan -Hours 12)
            OnBattery  = $true    # 안전망이라 전원 상태와 무관하게 돈다
        }
    )
}

function Invoke-Check {
    param([string]$Root)

    $bad = 0
    foreach ($plan in Get-TaskPlan $Root) {
        $task = Get-ScheduledTask -TaskName $plan.Name -ErrorAction SilentlyContinue
        if (-not $task) {
            Write-Host ("  NG   {0} — 작업이 등록돼 있지 않다" -f $plan.Name) -ForegroundColor Red
            $bad++
            continue
        }

        # 지금 설정이 틀렸는가 — 이것만 실패로 센다.
        $cmd = $task.Actions[0].Execute
        $problems = @()
        if (Test-VersionPinned $cmd) { $problems += '실행 파일 경로에 버전이 박혀 있다' }
        if (-not (Test-Path -LiteralPath $cmd -PathType Leaf)) { $problems += "실행 파일이 없다: $cmd" }
        if (-not (Test-Path -LiteralPath $plan.Script -PathType Leaf)) { $problems += "스크립트가 없다: $($plan.Script)" }

        # 지난 실행이 어땠는가 — 참고일 뿐이다. 방금 고쳤다면 다음 실행 전까지
        # 옛 실패 코드가 그대로 남아 있어, 이걸로 실패를 매기면 헛경보가 된다.
        $info = $task | Get-ScheduledTaskInfo
        $warnings = @()
        if ($info.LastTaskResult -eq 2147942402) {
            $warnings += ('마지막 실행({0})이 ERROR_FILE_NOT_FOUND로 실패했다. 다음 실행에서 풀리는지 보라.' -f $info.LastRunTime)
        }

        if ($problems.Count -eq 0) {
            Write-Host ("  OK   {0}" -f $plan.Name)
        } else {
            $bad++
            Write-Host ("  NG   {0}" -f $plan.Name) -ForegroundColor Red
            $problems | ForEach-Object { Write-Host ("         - {0}" -f $_) -ForegroundColor Red }
        }
        $warnings | ForEach-Object { Write-Host ("       참고 {0}" -f $_) -ForegroundColor Yellow }
    }
    return $bad
}

function Invoke-Register {
    param([string]$Root, [string]$Pwsh)

    foreach ($plan in Get-TaskPlan $Root) {
        if (-not (Test-Path -LiteralPath $plan.Script -PathType Leaf)) {
            throw "스크립트를 찾지 못했습니다: $($plan.Script)"
        }

        $action = New-ScheduledTaskAction -Execute $Pwsh -WorkingDirectory $Root `
            -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $plan.Script)

        $trigger = New-ScheduledTaskTrigger -Daily -At $plan.StartTime
        $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $plan.StartTime `
            -RepetitionInterval $plan.Interval -RepetitionDuration $plan.Duration).Repetition

        $settings = New-ScheduledTaskSettingsSet `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
            -MultipleInstances IgnoreNew `
            -StartWhenAvailable `
            -AllowStartIfOnBatteries:$plan.OnBattery `
            -DontStopIfGoingOnBatteries:$plan.OnBattery

        Register-ScheduledTask -TaskName $plan.Name -Action $action -Trigger $trigger `
            -Settings $settings -User $env:USERNAME -RunLevel Limited -Force | Out-Null

        Write-Host ("  등록 {0}" -f $plan.Name)
    }
}

function Invoke-Main {
    $root = $PSScriptRoot

    $pwshPath = Resolve-StablePwsh
    if (-not $pwshPath) {
        Write-Host '쓸 수 있는 pwsh를 찾지 못했습니다.' -ForegroundColor Red
        Write-Host '버전이 박히지 않은 경로여야 합니다 — 업데이트가 오면 사라지기 때문입니다.' -ForegroundColor Red
        exit 1
    }

    if ($Check) {
        Write-Host '작업 상태를 검사합니다.'
        $bad = Invoke-Check $root
        Write-Host ''
        if ($bad -gt 0) {
            Write-Host "${bad}개 작업에 문제가 있습니다. 고치려면 -Check 없이 다시 실행하세요." -ForegroundColor Red
            exit 1
        }
        Write-Host '두 작업 모두 정상입니다.'
        exit 0
    }

    Write-Host "실행 파일: $pwshPath"
    Invoke-Register $root $pwshPath
    Write-Host ''
    Write-Host '등록 결과를 검사합니다.'
    $bad = Invoke-Check $root
    if ($bad -gt 0) { exit 1 }
    Write-Host ''
    Write-Host '완료했습니다.'
    exit 0
}

# 테스트가 점 소스로 함수만 가져갈 때는 본문을 돌리지 않는다.
if ($MyInvocation.InvocationName -ne '.') { Invoke-Main }
