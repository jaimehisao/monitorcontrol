# PyInstaller spec: one-file Linux binary with GTK 4 / Adwaita GI hooks.
import sys
from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).resolve().parent
src = root / "src"
entry = Path(SPECPATH) / "entry.py"

# collect_data_files() imports the package. During a freeze it is not
# pip-installed, so src/ has to be on sys.path or CSS and the GNOME
# extension are left out and the GUI crashes on startup.
sys.path.insert(0, str(src))
datas = collect_data_files("monitorcontrol")
if not any(Path(src_path).name == "style.css" for src_path, _dest in datas):
    raise SystemExit(
        "PyInstaller did not collect monitorcontrol data files (style.css missing)"
    )

a = Analysis(
    [str(entry)],
    pathex=[str(src)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "gi",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Gio",
        "gi.repository.Gdk",
        "gi.repository.Gtk",
        "gi.repository.Adw",
        "gi.repository.Pango",
        "gi.repository.cairo",
        "gi.repository.GdkPixbuf",
        "cairo",
    ],
    hookspath=[],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita", "hicolor"],
            "themes": ["Adwaita"],
            "module-versions": {
                "Gtk": "4.0",
                "GtkosxApplication": "1.0",
            },
        }
    },
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="monitorcontrol",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
