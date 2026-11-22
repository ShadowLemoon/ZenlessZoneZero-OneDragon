@echo off
cd /d D:\Code\ZenlessZoneZero-OneDragon\.pai\.worktree\plugin-dev-switch
set PYTHONPATH=D:\Code\ZenlessZoneZero-OneDragon\.pai\.worktree\plugin-dev-switch\src
set PYTHONIOENCODING=utf-8
D:\Code\ZenlessZoneZero-OneDragon\.venv\Scripts\python.exe src\zzz_od\gui\app.py > plugin-dev-switch-run.log 2>&1
