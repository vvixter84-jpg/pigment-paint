import sys
from pathlib import Path


def _resource_root() -> Path:
    """Return the folder that contains the bundled assets.

    PyInstaller one-file builds unpack the application into ``sys._MEIPASS``;
    a normal source checkout keeps everything next to the ``app`` package.
    """
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            return Path(bundle)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _resource_root()
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
ICONS = ASSETS / "icons"
EXAMPLES = ASSETS / "examples"
