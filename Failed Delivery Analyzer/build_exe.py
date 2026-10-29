"""Builds the no-install version of the program.

Run it by double-clicking build_exe.bat. When it finishes you get:

    dist\\Delivery Analyzer\\Delivery Analyzer.exe     the program (with its _internal folder)
    dist\\Delivery-Analyzer.zip                        the same folder zipped, ready to share

Copy or send either one to any Windows laptop. It does NOT need Python installed.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("DELIVERY_BUILD_DIR", HERE)  # where dist\ and build\ go (default: next to this file)
os.chdir(HERE)
sys.path.insert(0, HERE)
NAME = "Delivery Analyzer"

try:
    import PyInstaller.__main__ as pyinstaller
except ImportError:
    print("Installing the packaging tool (PyInstaller), one time only...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    import PyInstaller.__main__ as pyinstaller

from delivery_ui_kit import make_icon  # the program draws its own icon

build_dir = os.path.join(OUT, "build")
dist_dir = os.path.join(OUT, "dist")
os.makedirs(build_dir, exist_ok=True)
icon = os.path.join(build_dir, "icon.ico")
make_icon(256).save(icon, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

pyinstaller.run([
    "main.py", "--noconfirm", "--clean", "--windowed", "--name", NAME, "--icon", icon,
    "--distpath", dist_dir, "--workpath", os.path.join(build_dir, "work"), "--specpath", build_dir,
    "--add-data", f"{os.path.join(HERE, 'sample_data')}{os.pathsep}sample_data",  # first-run sample records
])

program = os.path.join(dist_dir, NAME)
with open(os.path.join(program, "READ ME FIRST.txt"), "w", encoding="utf-8") as note:
    note.write(
        "Delivery Analyzer - no-install version\n"
        "======================================\n\n"
        f"1. Double-click \"{NAME}.exe\" in this folder. No Python or internet needed.\n"
        "   (The first start takes a few seconds; a small 'Starting up...' box appears.)\n"
        "2. Windows says \"Windows protected your PC\"? The program is not digitally signed.\n"
        "   Click More info, then Run anyway.\n\n"
        "Your records are saved in delivery_records.csv, in this same folder (it appears on the\n"
        "first start, filled with sample records). Charts you save go to the 'charts' folder.\n"
        "To start with an empty list: close the program, open delivery_records.csv in Notepad,\n"
        "delete every line except the first one, and save.\n"
        "Keep the whole folder together: the _internal folder is part of the program.\n")

shutil.rmtree(build_dir, ignore_errors=True)  # temporary build files are no longer needed
archive = shutil.make_archive(os.path.join(dist_dir, "Delivery-Analyzer"), "zip", dist_dir, NAME)
print(f"\nDone. Share this folder:  {program}   (the program is {NAME}.exe inside it)")
print(f"Or send this single file: {archive}   (unzip it, then open {NAME}.exe)")
