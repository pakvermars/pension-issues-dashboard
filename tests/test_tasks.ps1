# 작업 등록 경로 검사 테스트.
#
#   pwsh -NoProfile -File tests\test_tasks.ps1
#
# 2026-10-15에 PowerShell이 7.6.6.0에서 7.6.7.0으로 올라가면서 작업이 가리키던
# 폴더가 사라졌다. 실행 파일을 못 찾으니 로그조차 못 남기고 즉사해, 파이프라인이
# 엿새를 멈췄다. 버전이 박힌 경로가 다시 등록되는 일을 여기서 막는다.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. (Join-Path $root 'register_tasks.ps1')

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

# 실제로 사고를 낸 그 경로.
$pinned = 'C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.6.0_x64__8wekyb3d8bbwe\pwsh.exe'

Check '버전이 박힌 경로는 거부한다' (Test-StablePwshPath $pinned) $false
Check '지금 없는 파일은 거부한다' (Test-StablePwshPath 'C:\nowhere\pwsh.exe') $false
Check '빈 경로는 거부한다' (Test-StablePwshPath '') $false

# 버전이 박혔는지만 따로 본다. 파일 존재 여부와 섞이면 원인을 가린다.
Check '버전 번호를 집어낸다' (Test-VersionPinned $pinned) $true
Check '별칭 경로에는 버전이 없다' (Test-VersionPinned 'C:\x\Microsoft.PowerShell_8wekyb3d8bbwe\pwsh.exe') $false

# 스스로 고른 경로가 스스로의 검사를 통과하지 못하면 등록이 의미가 없다.
$resolved = Resolve-StablePwsh
Check '고른 경로가 비어 있지 않다' ([bool]$resolved) $true
Check '고른 경로가 검사를 통과한다' (Test-StablePwshPath $resolved) $true

Write-Host ""
if ($script:failed -gt 0) {
    Write-Host "${script:ran}개 중 ${script:failed}개 실패" -ForegroundColor Red
    exit 1
}
Write-Host "${script:ran}개 모두 통과"
exit 0
