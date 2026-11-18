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
        desktop = os.path.join(tmp, "Desktop")
        for d in (addons, panels, cep, desktop):
            os.makedirs(d)
        env = {"AMVFX_BLENDER_ADDONS_DIRS": addons,
               "AMVFX_AE_PANEL_DIRS": panels,
               "AMVFX_CEP_DIR": cep,
               "AMVFX_DESKTOP_DIR": desktop}
        r = _run(["--target", target, "--skip-venv", "--no-models",
                  "--with-blender", "--with-ae-panel", "--with-cep"], env)
        assert r.returncode == 0, r.stderr + r.stdout
        assert os.path.isfile(os.path.join(target, "app.py"))
        assert os.path.isfile(os.path.join(target, "launch_amvfx.py"))
        assert os.path.isfile(os.path.join(target, "amvfx", "pipeline.py"))
        assert os.path.isfile(os.path.join(
            addons, "amvfx_blender_export", "__init__.py")), r.stdout
        assert os.path.isfile(os.path.join(panels, "AMVFX_Panel.jsx"))
        assert os.path.isfile(os.path.join(
            cep, "com.amvfx.panel", "CSXS", "manifest.xml"))
        # desktop shortcut (default on): one of the per-OS artifacts
        names = os.listdir(desktop)
        assert any(n.startswith("AMVFX") for n in names), (names, r.stdout)
        entry = os.path.join(desktop, "AMVFX.desktop")
        if os.path.isfile(entry):
            with open(entry) as f:
                body = f.read()
            assert "launch_amvfx.py" in body and target in body
    print("PASS test_install_into_fake_hosts")


def test_repair_keeps_venv_and_models():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "AMVFX")
        addons = os.path.join(tmp, "blender_addons")
        desktop = os.path.join(tmp, "Desktop")
        for d in (addons, desktop):
            os.makedirs(d)
        env = {"AMVFX_BLENDER_ADDONS_DIRS": addons,
               "AMVFX_DESKTOP_DIR": desktop}
        r = _run(["--target", target, "--skip-venv", "--no-models",
                  "--with-blender"], env)
        assert r.returncode == 0, r.stderr + r.stdout
        # plant a fake venv marker + a stale app file, as a real install has
        venv = os.path.join(target, ".venv")
        os.makedirs(venv)
        marker = os.path.join(venv, "KEEP_ME")
        with open(marker, "w") as f:
            f.write("venv contents")
        app_py = os.path.join(target, "app.py")
        with open(app_py, "w") as f:
            f.write("STALE")
        r = _run(["--target", target, "--repair", "--skip-venv",
                  "--no-models", "--with-blender"], env)
        assert r.returncode == 0, r.stderr + r.stdout
        assert "Repair mode" in r.stdout, r.stdout
        assert "keeping the venv" in r.stdout, r.stdout
        with open(marker) as f:
            assert f.read() == "venv contents", "repair must not touch .venv"
        with open(app_py) as f:
            body = f.read()
        assert "STALE" not in body and "AMVFX" in body, \
            "repair must refresh app files"
        # add-on refreshed too
        assert os.path.isfile(os.path.join(
            addons, "amvfx_blender_export", "__init__.py"))
    print("PASS test_repair_keeps_venv_and_models")


def test_repair_on_fresh_target_fails():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "AMVFX")
        r = _run(["--target", target, "--repair", "--skip-venv",
                  "--no-models"], {})
        assert r.returncode != 0, r.stdout
        assert "no existing install" in (r.stdout + r.stderr).lower()
    print("PASS test_repair_on_fresh_target_fails")


def test_second_plain_install_hints_at_repair():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "AMVFX")
        r = _run(["--target", target, "--skip-venv", "--no-models"], {})
        assert r.returncode == 0, r.stderr + r.stdout
        r = _run(["--target", target, "--skip-venv", "--no-models"], {})
        assert r.returncode == 0, r.stderr + r.stdout
        assert "--repair" in r.stdout, r.stdout
    print("PASS test_second_plain_install_hints_at_repair")


def test_ps_quote_escapes_single_quotes():
    sys.path.insert(0, os.path.join(ROOT, "installer"))
    import install as installer_mod
    q = installer_mod._ps_quote
    assert q(r"C:\AMVFX") == r"'C:\AMVFX'"
    # a ' in a username/folder must be doubled (PowerShell escape),
    # otherwise the .lnk creation command breaks
    assert q(r"C:\Users\O'Brien\AMVFX") == r"'C:\Users\O''Brien\AMVFX'"
    assert q("plain") == "'plain'"
    print("PASS test_ps_quote_escapes_single_quotes")


if __name__ == "__main__":
    test_dry_run_plans_without_touching_disk()
    test_install_into_fake_hosts()
    test_repair_keeps_venv_and_models()
    test_repair_on_fresh_target_fails()
    test_second_plain_install_hints_at_repair()
    test_ps_quote_escapes_single_quotes()
    print("all installer tests passed")
