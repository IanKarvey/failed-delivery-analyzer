"""
Failed Delivery and Redelivery Pattern Analyzer

    python main.py             opens the window (graphical interface)
    python main.py --console   runs the menu in this terminal instead

Both versions use the same delivery_records.csv file. Most people just
double-click run.bat (or the .exe in the no-install version).
"""

import sys
import traceback


def _tell_user(title, message):
    """Show a message box. A packaged .exe has no console, so print() alone would be invisible."""
    print(f"{title}: {message}")
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:  # nothing more we can do
        pass


def _make_dpi_aware():
    try:  # sharper text on high-DPI Windows screens; must happen before the first window
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError, ImportError):
        pass


def _show_splash():
    """A small 'Starting up...' box while the charting libraries load (the first start takes a few seconds)."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.overrideredirect(True)
        root.configure(bg="#ebeaf8")
        width, height = 380, 130
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 3
        root.geometry(f"{width}x{height}+{x}+{y}")
        tkinter.Label(root, text="Delivery Analyzer", font=("Segoe UI", 18, "bold"),
                      fg="#4f35c9", bg="#ebeaf8").pack(pady=(28, 4))
        tkinter.Label(root, text="Starting up...", font=("Segoe UI", 11),
                      fg="#5b5878", bg="#ebeaf8").pack()
        root.update()
        return root
    except Exception:
        return None


def _close_splash(splash):
    if splash is not None:
        try:
            splash.destroy()
        except Exception:
            pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--console" in argv or "-c" in argv:
        import delivery_console
        delivery_console.main()
        return

    _make_dpi_aware()
    splash = _show_splash()
    try:
        import delivery_gui
    except ImportError as error:  # e.g. Pillow or Tkinter is missing
        _close_splash(splash)
        _tell_user("Delivery Analyzer could not start",
                   f"A required part is missing ({error}).\n"
                   "Double-click run.bat: it installs what is missing.")
        return
    _close_splash(splash)
    try:
        delivery_gui.main()
    except Exception as error:
        import delivery_core
        log = delivery_core.log_error(traceback.format_exc())
        _tell_user("Delivery Analyzer stopped unexpectedly",
                   f"{error}\n\nYour records are safe. Details were saved to:\n{log}")


if __name__ == "__main__":
    main()
