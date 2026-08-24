"""
CrossHub Helper — 轻量级 .exe 启动器
"""
import sys
import os
from pathlib import Path

# 设置工作目录
if getattr(sys, 'frozen', False):
    app_root = Path(sys.executable).parent.parent
    os.chdir(app_root)
else:
    app_root = Path(__file__).parent
    os.chdir(app_root)

# 设置 PYTHONPATH
sys.path.insert(0, str(app_root / 'backend' / 'python'))
os.environ['PYTHONPATH'] = str(app_root / 'backend' / 'python')

if __name__ == '__main__':
    try:
        from scripts.sync_helper_app import load_config, setup_runtime_log
        from agent.desktop_app import run_desktop_mode

        cfg = load_config()
        if not cfg:
            raise RuntimeError("Config load failed")

        setup_runtime_log(str(cfg.get("project_root") or ""))
        exit_code = run_desktop_mode(cfg)
        sys.exit(exit_code)

    except Exception as e:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Error: {str(e)}", "CrossHub Helper", 0x10)
        except:
            print(f"Error: {e}")
        sys.exit(1)
