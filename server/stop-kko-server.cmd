@echo off
setlocal
title Stop KKO Server

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$listeners = @(Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue);" ^
  "if (-not $listeners.Count) { Write-Host 'KKO server is already stopped (port 8787 is free).' -ForegroundColor Yellow; exit 0 };" ^
  "$stopped = 0;" ^
  "foreach ($listener in $listeners) {" ^
  "  $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue;" ^
  "  if (-not $process) { continue };" ^
  "  if ($process.ProcessName -notmatch '^python') { Write-Host ('Port 8787 is used by ' + $process.ProcessName + '. Nothing was stopped.') -ForegroundColor Red; continue };" ^
  "  Stop-Process -Id $process.Id -Force;" ^
  "  Write-Host ('KKO server stopped (PID ' + $process.Id + ').') -ForegroundColor Green;" ^
  "  $stopped++" ^
  "};" ^
  "if (-not $stopped) { exit 1 }"

echo.
pause
endlocal
