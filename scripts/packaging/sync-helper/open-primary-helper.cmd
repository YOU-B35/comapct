@echo off
cd /d D:\YOTO-SASS\SaaS-HZ_WEB_Demo
set PYTHONPATH=D:\YOTO-SASS\SaaS-HZ_WEB_Demo\backend\python
set JAVA_API_URL=http://127.0.0.1:18080
set CROSSHUB_ALLOW_LOCAL_JAVA=1
set CROSSHUB_HELPER_CONFIG=D:\YOTO-SASS\SaaS-HZ_WEB_Demo\backend\python\.sync-helper-local\config.json
start "" py -u D:\YOTO-SASS\SaaS-HZ_WEB_Demo\backend\python\scripts\sync_helper_app.py
