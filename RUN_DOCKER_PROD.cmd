@echo off
REM CrossHub Docker 本地生产环境启动

cd /d "%~dp0"

echo.
echo ╔════════════════════════════════════════╗
echo ║   CrossHub Docker 本地生产环境启动      ║
echo ╚════════════════════════════════════════╝
echo.

REM 检查 Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安装！请先安装 Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo ✓ Docker 环境正常
echo.

REM 构建 Java 镜像
echo [1/4] 构建 Java 镜像...
docker build -f deploy\Dockerfile.java -t crosshub-java:latest .
if errorlevel 1 (
    echo ❌ Java 镜像构建失败
    pause
    exit /b 1
)
echo ✓ Java 镜像构建成功
echo.

REM 构建 Express 镜像
echo [2/4] 构建 Express 镜像...
docker build -f deploy\Dockerfile.express -t crosshub-express:latest .
if errorlevel 1 (
    echo ❌ Express 镜像构建失败
    pause
    exit /b 1
)
echo ✓ Express 镜像构建成功
echo.

REM 构建 Python Worker 镜像
echo [3/4] 构建 Python Worker 镜像...
docker build -f deploy\Dockerfile.python-worker -t crosshub-python-worker:latest .
if errorlevel 1 (
    echo ❌ Python Worker 镜像构建失败
    pause
    exit /b 1
)
echo ✓ Python Worker 镜像构建成功
echo.

REM 启动容器
echo [4/4] 启动容器...
docker-compose -f deploy\docker-compose.yml up -d
if errorlevel 1 (
    echo ❌ 容器启动失败
    pause
    exit /b 1
)
echo ✓ 容器启动成功
echo.

echo.
echo ╔════════════════════════════════════════╗
echo ║        生产环境容器已启动！            ║
echo ╚════════════════════════════════════════╝
echo.
echo 📍 访问地址（Docker 网络隔离）:
echo   Java API:    http://127.0.0.1:18080/api/temu/shops
echo   Express:     http://127.0.0.1:18081/api/health
echo.
echo 📋 查看日志:
echo   docker logs -f crosshub-java
echo   docker logs -f crosshub-express
echo.
echo 🛑 停止服务:
echo   docker-compose -f deploy\docker-compose.yml down
echo.
pause
