Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*mega_to_vjoy.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "vJoy bridge stopped."
