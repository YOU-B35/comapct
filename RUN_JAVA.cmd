@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set JAVA_HOME=%CD%\tools\jdk-17
set MAVEN_HOME=%CD%\tools\maven
set PATH=%JAVA_HOME%\bin;%MAVEN_HOME%\bin;%PATH%
set SPRING_PROFILES_ACTIVE=dev
set JAVA_TOOL_OPTIONS=-Duser.timezone=Asia/Shanghai

cd backend\java
echo.
echo ╔════════════════════════════════════════╗
echo ║     CrossHub - Java API (:18080)      ║
echo ╚════════════════════════════════════════╝
echo.
echo 正在启动 Maven...
echo.

mvn spring-boot:run

pause
