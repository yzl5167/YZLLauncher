"""YZL 启动器入口。"""
import sys


def _enable_windows_dpi() -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _init_x_threads() -> None:
    """tkinter 多线程调用需要 XInitThreads（Linux/X11）。"""
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            lib = ctypes.CDLL("libX11.so.6")
            lib.XInitThreads()
        except Exception:
            pass


def _log_error(tb: str) -> None:
    """把未捕获异常写到 yzl_error.log，避免 windowed exe 里静默崩溃。"""
    try:
        import datetime

        from yzl.constants import app_root

        with open(app_root() / "yzl_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.datetime.now()} =====\n{tb}\n")
    except Exception:
        pass


def _install_excepthook() -> None:
    def hook(t, v, tb):
        try:
            import traceback

            _log_error("".join(traceback.format_exception(t, v, tb)))
        except Exception:
            pass

    sys.excepthook = hook


def main() -> None:
    # 自检模式：不启动图形界面，仅验证打包完整性（供打包产物自测用）
    if "--selftest" in sys.argv:
        import yzl  # noqa: F401
        import yzl.core.config
        import yzl.core.net
        import yzl.core.versions
        import yzl.core.mods
        import yzl.core.auth
        import yzl.core.launcher
        import yzl.core.microsoft
        import yzl.core.shaders
        import yzl.core.javamgr
        import yzl.core.updater
        import yzl.ui.app
        from yzl.core.net import CURRENT_OS
        from yzl.core.versions import CURRENT_ARCH
        from yzl.constants import APP_VERSION
        print(f"YZL {APP_VERSION} selftest OK (os={CURRENT_OS} arch={CURRENT_ARCH})")
        sys.exit(0)
    _enable_windows_dpi()
    _init_x_threads()
    from yzl.ui.app import run

    _install_excepthook()
    run()


if __name__ == "__main__":
    main()
