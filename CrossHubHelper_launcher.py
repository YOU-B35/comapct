"""
CrossHub Helper — Windows 应用启动器
这个脚本被编译成 CrossHubHelper.exe
用户只需双击 .exe 文件即可启动应用
"""
import sys
import os
from pathlib import Path

# 获取应用根目录（.exe 所在位置）
if getattr(sys, 'frozen', False):
    app_root = Path(sys.executable).parent
else:
    app_root = Path(__file__).parent

# 设置环境变量
project_root = app_root / '..' / '..'
if project_root.exists():
    project_root = project_root.resolve()
    os.environ['PROJECT_ROOT'] = str(project_root)

# 添加 Python 路径
python_backend = app_root / 'backend' / 'python'
if not python_backend.exists():
    python_backend = Path(__file__).parent.parent / 'backend' / 'python'

if python_backend.exists():
    sys.path.insert(0, str(python_backend))

# 隐藏控制台（仅在 frozen 模式下有效）
if getattr(sys, 'frozen', False):
    try:
        import ctypes
        import windll
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except:
        pass

# 启动应用
if __name__ == '__main__':
    try:
        from agent.desktop_app import run_desktop_mode
        from scripts.sync_helper_app import load_config, setup_runtime_log

        cfg = load_config()
        if not cfg:
            raise RuntimeError("配置加载失败")

        setup_runtime_log(str(cfg.get("project_root") or ""))

        # 运行桌面应用
        exit_code = run_desktop_mode(cfg)
        sys.exit(exit_code)

    except Exception as e:
        # 显示错误对话框
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"启动失败:\n\n{str(e)}", "CrossHub Helper", 0x10)
        except:
            print(f"错误: {e}")
        sys.exit(1)
