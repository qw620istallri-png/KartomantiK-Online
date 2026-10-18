@echo off
setlocal
title KKO - bac a sable des cartes
cd /d "%~dp0.."
set KKO_SANDBOX=1
set PORT=8788
start "" "http://localhost:8788/?sandbox"
py server\main.py
endlocal
