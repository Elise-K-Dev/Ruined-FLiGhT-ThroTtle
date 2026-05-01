param(
  [string]$Port,
  [int]$Baud,
  [int]$Device
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$OutLog = Join-Path $Root "vjoy-bridge.out.log"
$ErrLog = Join-Path $Root "vjoy-bridge.err.log"
$Script = Join-Path $PSScriptRoot "mega_to_vjoy.py"
$SettingsPath = Join-Path $PSScriptRoot "vjoy_settings.json"

$Settings = $null
if (Test-Path $SettingsPath) {
  $Settings = Get-Content -Raw $SettingsPath | ConvertFrom-Json
}

if (-not $Port) {
  $Port = if ($Settings -and $Settings.serial_port) { $Settings.serial_port } else { "COM5" }
}
if (-not $Baud) {
  $Baud = if ($Settings -and $Settings.baud) { [int]$Settings.baud } else { 19200 }
}
if (-not $Device) {
  $Device = if ($Settings -and $Settings.vjoy_device) { [int]$Settings.vjoy_device } else { 1 }
}

Start-Process `
  -FilePath "python" `
  -ArgumentList @($Script, "--port", $Port, "--baud", "$Baud", "--device", "$Device", "--quiet") `
  -WorkingDirectory $Root `
  -RedirectStandardOutput $OutLog `
  -RedirectStandardError $ErrLog `
  -WindowStyle Hidden

Write-Host "vJoy bridge started on $Port. Logs: $OutLog / $ErrLog"
