$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Torsionfield Autogenic Runtime installation requires an elevated PowerShell. No reduced-privilege fallback is installed.'
}

$Source = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Root = Join-Path $env:ProgramData 'Torsionfield\AutogenicRuntime'
$State = Join-Path $Root 'state'
$Resident = Join-Path $Root 'resident'
$Extension = Join-Path $Root 'extension'
$Userscript = Join-Path $Root 'userscript'
New-Item -ItemType Directory -Force -Path $Root,$State,$Resident,$Extension,$Userscript | Out-Null

Copy-Item -Force (Join-Path $Source 'resident\tf_resident.py') $Resident
Copy-Item -Force (Join-Path $Source 'extension\manifest.json') $Extension
Copy-Item -Force (Join-Path $Source 'extension\service_worker.js') $Extension
Copy-Item -Force (Join-Path $Source 'extension\content_bridge.js') $Extension
Copy-Item -Force (Join-Path $Source 'extension\runtime_config.js') $Extension
Copy-Item -Force (Join-Path $Source 'userscript\torsionfield-autogenic.user.js') $Userscript

$TokenPath = Join-Path $State 'token'
if (-not (Test-Path $TokenPath)) {
  $bytes = New-Object byte[] 48
  [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  [IO.File]::WriteAllText($TokenPath, $token + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}
$Token = (Get-Content -Raw $TokenPath).Trim()

$RuntimeConfig = Join-Path $Extension 'runtime_config.js'
(Get-Content -Raw $RuntimeConfig).Replace('__TF_RESIDENT_TOKEN__', $Token) | Set-Content -NoNewline -Encoding utf8 $RuntimeConfig
$UserScriptPath = Join-Path $Userscript 'torsionfield-autogenic.user.js'
(Get-Content -Raw $UserScriptPath).Replace('__TF_RESIDENT_TOKEN__', $Token) | Set-Content -NoNewline -Encoding utf8 $UserScriptPath

$Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = (Get-Command python3.exe -ErrorAction SilentlyContinue).Source }
if (-not $Python) { throw 'Python 3 executable not found.' }

$Launcher = Join-Path $Root 'start-resident.cmd'
@"
@echo off
set TF_RESIDENT_STATE=$State
"$Python" "$Resident\tf_resident.py"
"@ | Set-Content -Encoding ascii $Launcher

$TaskName = 'Torsionfield Autogenic Resident'
$Action = New-ScheduledTaskAction -Execute $Launcher
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$TaskPrincipal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Principal $TaskPrincipal
Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds(15)
do {
  Start-Sleep -Milliseconds 250
  try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:17373/v1/health' -TimeoutSec 2 } catch { $health = $null }
} until ($health -or (Get-Date) -gt $deadline)
if (-not $health.ok) { throw 'Resident did not become healthy after Scheduled Task start.' }
if (-not $health.elevated) { throw 'Resident is running but did not prove elevated execution.' }

$Bootstrap = Join-Path $Root 'bootstrap-browser.ps1'
@"
`$ErrorActionPreference = 'Stop'
`$token = (Get-Content -Raw '$TokenPath').Trim()
`$headers = @{ Authorization = "Bearer `$token" }
`$body = @{
  url = 'https://chatgpt.com/'
  profile = (Join-Path `$env:LOCALAPPDATA 'Torsionfield\ChromeProfile')
  args = @('--load-extension=$Extension')
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:17373/v1/browser/restart' -Headers `$headers -ContentType 'application/json' -Body `$body
"@ | Set-Content -Encoding utf8 $Bootstrap

[pscustomobject]@{ Installed=$true; Root=$Root; Resident='http://127.0.0.1:17373'; Task=$TaskName; Extension=$Extension; Userscript=$UserScriptPath; BrowserBootstrap=$Bootstrap; Health=$health } | ConvertTo-Json -Depth 8
