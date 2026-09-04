# PyInstaller spec: one-file Linux binary with GTK 4 / Adwaita GI hooks.
from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).resolve().parent
src = root / "src"
entry = Path(SPECPATH) / "entry.py"

datas = collect_data_files("monitorcontrol")

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
