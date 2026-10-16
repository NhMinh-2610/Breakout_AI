param([ValidateSet('Install','Status','Remove')][string]$Mode = 'Status')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskPythonw = Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPythonw)) { throw 'Run scripts/setup.ps1 first; pythonw.exe is required.' }
Push-Location -LiteralPath $taskRoot
try {
    $taskMetadata = & $taskPython -m breakout_ai.schedule
    if ($LASTEXITCODE -ne 0) { throw 'Cannot load Breakout AI settings.' }
    $taskConfig = $taskMetadata | ConvertFrom-Json
    Import-Module ScheduledTasks
    $taskExisting = $null
    try {
        $taskExisting = Get-ScheduledTask -TaskName $taskConfig.task_name -ErrorAction Stop
    } catch {
        if ($_.CategoryInfo.Category -ne 'ObjectNotFound') { throw }
    }
    if ($taskExisting -and ($taskExisting.Description -ne $taskConfig.marker)) {
        throw 'An unrelated task uses this name. It will not be changed.'
    }
    $taskManifest = Join-Path $taskRoot 'data\schedule.json'
    if ($Mode -eq 'Remove') {
        if ($taskExisting) {
            Unregister-ScheduledTask -TaskName $taskConfig.task_name -Confirm:$false
        }
        if (Test-Path -LiteralPath $taskManifest) {
            $taskSaved = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
            if ($taskSaved.task_name -eq $taskConfig.task_name) { Remove-Item -LiteralPath $taskManifest }
        }
        Write-Output 'Breakout AI morning schedule removed.'
        return
    }
    if ($Mode -eq 'Install') {
        if ((Get-TimeZone).Id -ne 'SE Asia Standard Time') {
            throw 'Set Windows time zone to UTC+07 Hanoi before installing the 07:30 local task.'
        }
        $taskAction = New-ScheduledTaskAction -Execute $taskPythonw -Argument '-m breakout_ai.daily --refresh' -WorkingDirectory $taskRoot
        $taskTrigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(7).AddMinutes(30))
        $taskAccount = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskAccount -LogonType Interactive -RunLevel Limited
        $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
        $taskDefinition = New-ScheduledTask -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Description $taskConfig.marker
        Register-ScheduledTask -TaskName $taskConfig.task_name -InputObject $taskDefinition -Force | Out-Null
        $taskExisting = Get-ScheduledTask -TaskName $taskConfig.task_name
    }
    if (-not $taskExisting) { Write-Output 'Breakout AI morning schedule is not installed.'; return }
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskConfig.task_name
    $taskState = [ordered]@{
        task_name = $taskConfig.task_name; workspace = $taskConfig.workspace; database = $taskConfig.database
        time = '07:30'; timezone = 'Asia/Ho_Chi_Minh'; state = [string]$taskExisting.State
        checked_at = [datetime]::Now.ToString('o'); next_run = $taskInfo.NextRunTime.ToString('o')
        last_result = $taskInfo.LastTaskResult
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $taskManifest) -Force | Out-Null
    $taskState | ConvertTo-Json | Set-Content -LiteralPath $taskManifest -Encoding UTF8
    $taskState | ConvertTo-Json
} finally { Pop-Location }
