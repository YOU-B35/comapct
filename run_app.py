"""
CrossHub Helper — 完整应用打包脚本
"""
import sys
import os
from pathlib import Path

# 获取应用根目录
if getattr(sys, 'frozen', False):
    # .exe 运行时
    app_root = Path(sys.executable).parent
else:
    # 开发时
    app_root = Path(__file__).parent.parent

# 设置工作目录为项目根目录
os.chdir(app_root)

# 添加 backend/python 到 Python 路径
backend_python = app_root / 'backend' / 'python'
sys.path.insert(0, str(backend_python))
os.environ['PYTHONPATH'] = str(backend_python)

if __name__ == '__main__':
    try:
        # 导入并运行应用
        from scripts.sync_helper_app import load_config, setup_runtime_log
        from agent.desktop_app import run_desktop_mode

        # 加载配置
        cfg = load_config()
        if not cfg:
            raise RuntimeError("Failed to load configuration")

        # 设置日志
        setup_runtime_log(str(cfg.get("project_root") or ""))

        # 运行应用
        exit_code = run_desktop_mode(cfg)
        sys.exit(exit_code)

    except Exception as e:
        # 错误处理
        try:
            import ctypes
            msg = f"Application Error:\n\n{str(e)}"
            ctypes.windll.user32.MessageBoxW(0, msg, "CrossHub Helper", 0x10)
        except:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(1)
