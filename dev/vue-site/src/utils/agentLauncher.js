import { TEMU_API_BASE_URL } from '@/api/config'

/** 全平台统一启动脚本（Temu / Amazon 等共用同一 Agent 进程） */
export const CROSSHUB_SYNC_HELPER_FILENAME = 'CrossHub-Sync-Helper.exe'

/** @deprecated 运营前端不再提供下载；运维请用 scripts/build-sync-helper-exe.ps1 打包 */

const BAT_BOM = '\uFEFF'

function escapeBatValue(value = '') {
  return String(value).replace(/"/g, '""')
}

function resolveLauncherRoot() {
  const configured = import.meta.env.VITE_AGENT_LAUNCHER_ROOT
  if (configured) return configured.replace(/\//g, '\\')
  return 'D:\\NIUBI\\SaaS-HZ_WEB_Demo'
}

function resolveJavaApiUrl() {
  return TEMU_API_BASE_URL.replace(/\/$/, '')
}

function downloadTextFile(filename, content) {
  const blob = new Blob([`${BAT_BOM}${content}`], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function batHeader(title) {
  return `@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title ${title}
`
}

function buildZiniaoOptionalSection() {
  return `echo [1/2] Ziniao WebDriver (Amazon only, port 16851)...
set "ZINIAO_EXE=C:\\Program Files\\ziniao\\ziniao.exe"
if not exist "%ZINIAO_EXE%" (
  echo [SKIP] Ziniao not installed. Amazon sync needs it; Temu is unaffected.
  echo.
  goto agent_start
)
echo       Quit normal Ziniao first, including the tray icon.
netstat -ano | findstr ":16851" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "" "%ZINIAO_EXE%" --run_type=web_driver --ipc_type=http --port=16851
  echo Waiting for Ziniao WebDriver...
  timeout /t 8 /nobreak >nul
  netstat -ano | findstr ":16851" | findstr "LISTENING" >nul
  if errorlevel 1 (
    echo [WARN] Port 16851 is not listening. Amazon sync may fail; Temu can still work.
  ) else (
    echo Ziniao WebDriver is ready.
  )
) else (
  echo Ziniao WebDriver is already running.
)
echo.
:agent_start
`
}

function buildAgentSection({ agentToken, projectRoot, javaApiUrl }) {
  const root = escapeBatValue(projectRoot)
  const token = escapeBatValue(agentToken)
  const apiUrl = escapeBatValue(javaApiUrl)
  return `echo [2/2] CrossHub sync agent (Temu / Amazon / ...)...
echo       Run once per PC. Keep this window open.
echo API: ${apiUrl}
echo Health: http://127.0.0.1:18765/health
echo.
set "AGENT_TOKEN=${token}"
set "JAVA_API_URL=${apiUrl}"
set "AGENT_HEALTH_PORT=18765"
set "PYTHONPATH=${root}\\backend\\python"
cd /d "${root}"
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3 and add it to PATH.
  pause
  exit /b 5
)
if not exist "${root}\\backend\\python\\scripts\\run_agent.py" (
  echo [ERROR] Agent script not found. Check project path: ${root}
  pause
  exit /b 6
)
:agent_loop
py "${root}\\backend\\python\\scripts\\run_agent.py"
if errorlevel 1 (
  echo.
  echo [WARN] Agent exited unexpectedly. Retrying in 5 seconds...
  timeout /t 5 /nobreak >nul
  goto agent_loop
)
echo.
echo Agent stopped.
pause`
}

export function buildCrossHubSyncHelperBat({
  agentToken,
  projectRoot = resolveLauncherRoot(),
  javaApiUrl = resolveJavaApiUrl(),
}) {
  return `${batHeader('CrossHub Sync Helper')}${buildZiniaoOptionalSection()}${buildAgentSection({
    agentToken,
    projectRoot,
    javaApiUrl,
  })}
`
}

export function downloadCrossHubSyncHelper(setupData) {
  const token = setupData?.agent_token || setupData?.token
  if (!token) {
    throw new Error('未获取到同步助手凭证')
  }
  downloadTextFile(
    CROSSHUB_SYNC_HELPER_FILENAME,
    buildCrossHubSyncHelperBat({ agentToken: token }),
  )
}

/** @deprecated 请使用 downloadCrossHubSyncHelper */
export function downloadCombinedLauncher(setupData) {
  return downloadCrossHubSyncHelper(setupData)
}

/** @deprecated 请使用 downloadCrossHubSyncHelper */
export function downloadCrossHubAgentLauncher(setupData) {
  return downloadCrossHubSyncHelper(setupData)
}

/** @deprecated 请使用 downloadCrossHubSyncHelper */
export function downloadAmazonAgentLauncher(setupData) {
  return downloadCrossHubSyncHelper(setupData)
}

/** @deprecated 仅 IT 调试用 */
export function buildZiniaoLauncherBat(projectRoot = resolveLauncherRoot()) {
  return `${batHeader('CrossHub Ziniao Launcher')}${buildZiniaoOptionalSection()}
echo Ziniao check done.
pause
`
}

export function downloadZiniaoLauncher() {
  downloadTextFile('CrossHub-Ziniao-Launcher.bat', buildZiniaoLauncherBat())
}

export function getLauncherRootHint() {
  return resolveLauncherRoot()
}
