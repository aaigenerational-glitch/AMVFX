"""Updater tests: version comparison + in-place apply from a local
fixture ZIP (no network). The .venv must survive an update untouched.
Run: python tests/test_updater.py
"""
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from amvfx import updater  # noqa: E402


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def test_version_compare():
    assert updater.is_newer("0.2.1", "0.2.0")
    assert updater.is_newer("1.0.0", "0.9.9")
    assert not updater.is_newer("0.2.0", "0.2.0")
    assert not updater.is_newer("0.1.9", "0.2.0")
    print("PASS test_version_compare")


def test_apply_update_in_place():
    with tempfile.TemporaryDirectory() as tmp:
        # fake installed app at v0.2.0 with a venv that must survive
        app = os.path.join(tmp, "AMVFX")
        _write(os.path.join(app, "VERSION"), "0.2.0\n")
        _write(os.path.join(app, "app.py"), "# old app\n")
        _write(os.path.join(app, ".venv", "keep.txt"), "precious\n")
        # fixture update archive, GitHub-zipball layout (one top folder)
        src = os.path.join(tmp, "src", "AMVFX-main")
        _write(os.path.join(src, "VERSION"), "9.9.9\n")
        _write(os.path.join(src, "app.py"), "# new app\n")
        _write(os.path.join(src, "amvfx", "newtool.py"), "# new\n")
        zpath = os.path.join(tmp, "update.zip")
        with zipfile.ZipFile(zpath, "w") as z:
            for root, _dirs, files in os.walk(os.path.join(tmp, "src")):
                for fn in files:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full,
                                                  os.path.join(tmp, "src")))
        new = updater.apply_update(app, source=zpath, log=lambda m: None)
        assert new == "9.9.9", new
        with open(os.path.join(app, "app.py")) as f:
            assert "new app" in f.read()
        assert os.path.isfile(os.path.join(app, "amvfx", "newtool.py"))
        with open(os.path.join(app, ".venv", "keep.txt")) as f:
            assert "precious" in f.read(), "update must never touch .venv"
        assert updater.local_version(app) == "9.9.9"
    print("PASS test_apply_update_in_place")


if __name__ == "__main__":
    test_version_compare()
    test_apply_update_in_place()
    print("all updater tests passed")
