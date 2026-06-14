# Registers a Windows Scheduled Task to run the apartment digest daily at 10am.
# Run once in PowerShell from the project folder:  ./schedule-daily.ps1
param(
  [string]$ProjectDir = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [string]$Python = "python",
  [string]$Time = "10:00",
  [string]$TaskName = "ApartmentHuntDaily"
)

$action = New-ScheduledTaskAction -Execute $Python -Argument "src\daily.py" -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
# StartWhenAvailable => if the PC was asleep/off at 10am, it runs at next wake.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "Daily apartment hunt brief (Facebook + apartment sites)" -Force

Write-Host "Registered '$TaskName': runs '$Python src\daily.py' daily at $Time in $ProjectDir"
Write-Host "Test it now with:  python src\daily.py"
Write-Host "Remove later with: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
