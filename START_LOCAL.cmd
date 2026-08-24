@echo off
REM CrossHub 本地启动脚本（Windows CMD 兼容版）
REM 启动三个终端窗口分别运行 Java + Express + Vue

cd /d "%~dp0"

REM 配置 JDK 环境
set JAVA_HOME=%CD%\tools\jdk-17
set MAVEN_HOME=%CD%\tools\maven
set PATH=%JAVA_HOME%\bin;%MAVEN_HOME%\bin;%PATH%

echo.
echo ====================================
echo CrossHub 本地启动
echo ====================================
echo.

REM 窗口1: Java API
echo [1/3] 启动 Java API 后端 (:18080) ...
start "CrossHub - Java API" cmd /k "cd backend\java && set SPRING_PROFILES_ACTIVE=dev && set JAVA_TOOL_OPTIONS=-Duser.timezone=Asia/Shanghai && mvn spring-boot:run"

REM 等待 2 秒
timeout /t 2 /nobreak

REM 窗口2: Express
echo [2/3] 启动 Express 演示接口 (:3000) ...
start "CrossHub - Express" cmd /k "cd script\api-server && npm install >nul 2>&1 && npm start"

REM 等待 2 秒
timeout /t 2 /nobreak

REM 窗口3: Vue
echo [3/3] 启动 Vue 前端 (:5174) ...
start "CrossHub - Vue Dev" cmd /k "cd dev\vue-site && npm run dev -- --port 5174 --strictPort"

echo.
echo ====================================
echo 服务启动中，请等待 30-60 秒...
echo ====================================
echo.
echo 访问地址:
echo   Web:     http://localhost:5174
echo   Java:    http://localhost:18080/api/temu/shops
echo   Express: http://localhost:3000/api/health
echo.
echo 演示账号（admin@crosshub.cn / 12345678）
echo.
pause
