"""Installer tests: dry-run planning + add-on placement into fake
Blender / After Effects folders (detection overridden via env vars).
No network, no venv: --skip-venv --no-models.
Run: python tests/test_installer.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(ROOT, "installer", "install.py")


def _run(args, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run([sys.executable, INSTALLER] + args, env=env,
                          capture_output=True, text=True, timeout=300)


def test_dry_run_plans_without_touching_disk():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "AMVFX")
        r = _run(["--dry-run", "--yes", "--target", target], {})
        assert r.returncode == 0, r.stderr
        assert "Blender add-on" in r.stdout
        assert not os.path.exists(target), "dry-run must not create files"
    print("PASS test_dry_run_plans_without_touching_disk")


def test_install_into_fake_hosts():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "AMVFX")
        addons = os.path.join(tmp, "blender_addons")
        panels = os.path.join(tmp, "ae_panels")
        cep = os.path.join(tmp, "cep_extensions")
        for d in (addons, panels, cep):
            os.makedirs(d)
        env = {"AMVFX_BLENDER_ADDONS_DIRS": addons,
               "AMVFX_AE_PANEL_DIRS": panels,
               "AMVFX_CEP_DIR": cep}
        r = _run(["--target", target, "--skip-venv", "--no-models",
                  "--with-blender", "--with-ae-panel", "--with-cep"], env)
        assert r.returncode == 0, r.stderr + r.stdout
        assert os.path.isfile(os.path.join(target, "app.py"))
        assert os.path.isfile(os.path.join(target, "amvfx", "pipeline.py"))
        assert os.path.isfile(os.path.join(
            addons, "amvfx_blender_export", "__init__.py")), r.stdout
        assert os.path.isfile(os.path.join(panels, "AMVFX_Panel.jsx"))
        assert os.path.isfile(os.path.join(
            cep, "com.amvfx.panel", "CSXS", "manifest.xml"))
    print("PASS test_install_into_fake_hosts")


if __name__ == "__main__":
    test_dry_run_plans_without_touching_disk()
    test_install_into_fake_hosts()
    print("all installer tests passed")
