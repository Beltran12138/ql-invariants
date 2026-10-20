@echo off
rem One-off scheduled run of positions.py (outside Claude Code, so idle-memory reaping does not apply).
set HTTPS_PROXY=
set HTTP_PROXY=
set https_proxy=
set http_proxy=
cd /d D:\dev\ql-invariants\audit_hegic
echo start %date% %time% > positions.log
"C:\Users\lenovo\AppData\Local\Programs\Python\Python311\python.exe" -I -u positions.py >> positions.log 2>&1
echo exit %errorlevel% %date% %time% >> positions.log
