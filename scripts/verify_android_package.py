"""Verify the actual Android payload and import its configured client in isolation."""
import argparse
import ast
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import runpy
import zipfile
import xml.etree.ElementTree as ET


def verify_package(artifact: Path, api_url: str) -> None:
    normalize_api_url = runpy.run_path(str(Path(__file__).resolve().parents[1] / "app/core/api_config.py"))["normalize_api_url"]
    api_url = normalize_api_url(api_url, android=True)
    with zipfile.ZipFile(artifact) as package:
        candidates = [name for name in package.namelist() if name.endswith("assets/app.zip")]
        if len(candidates) != 1:
            raise ValueError("Expected one embedded Python app.zip")
        payload = package.read(candidates[0])
    with zipfile.ZipFile(io.BytesIO(payload)) as app_zip:
        if any(Path(name).name == ".env" or Path(name).name.startswith(".env.") for name in app_zip.namelist()):
            raise ValueError("Android payload must not contain dotenv files")
        source = app_zip.read("core/build_config.py").decode("utf-8-sig")
        assignment = ast.parse(source).body[0]
        if not isinstance(assignment, ast.Assign) or ast.literal_eval(assignment.value) != api_url:
            raise ValueError("Packaged API URL does not match -ApiUrl")
        # A successful incremental build must contain this working tree's sources.
        app_root = Path(__file__).resolve().parents[1] / "app"
        sources = [app_root / "main.py"]
        for folder in ("components", "core", "routing", "screens", "services", "state"):
            sources.extend((app_root / folder).rglob("*.py"))
        checked_sources = 0
        for current in sources:
            if current.name == "build_config.py":
                continue
            name = current.relative_to(app_root).as_posix()
            if app_zip.read(name) != current.read_bytes():
                raise ValueError(f"APK contains outdated app source: {name}")
            checked_sources += 1
        with tempfile.TemporaryDirectory(prefix="attendai-apk-check-") as directory:
            root = Path(directory)
            for name in app_zip.namelist():
                # Only app sources, with no archive path traversal or site packages.
                target = (root / name).resolve()
                if name.endswith(".py") and root.resolve() in target.parents and not name.startswith("__pypackages__/"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(app_zip.read(name))
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["API_BASE_URL"] = "http://127.0.0.1:9999"  # Build config must win.
            env["APP_ENV"] = "development"  # HTTPS build policy must win, too.
            env["ALLOW_INSECURE_DEV_API"] = "true"
            env["FLET_PLATFORM"] = "android"
            code = (
                "import main, sys\n"
                "from app.core.config import get_settings, normalize_api_url\n"
                "from app.services.api_client import ApiClient\n"
                "expected = normalize_api_url(sys.argv[1], android=True)\n"
                "assert get_settings().api_base_url == expected\n"
                "assert get_settings().allow_insecure_dev_api == expected.startswith('http://')\n"
                "assert ApiClient()._url('/api/v1/health') == expected + '/api/v1/health'\n"
                "assert not expected.startswith('https://') or not ApiClient().set_base_url('http://192.168.1.50:8000')\n"
            )
            subprocess.run([sys.executable, "-c", code, api_url], cwd=root, env=env, check=True)

    # This is the release manifest used by Gradle for this artifact.
    manifest = Path(__file__).resolve().parents[1] / "app/build/flutter/build/app/intermediates/merged_manifests/release/processReleaseManifest/AndroidManifest.xml"
    document = ET.parse(manifest).getroot()
    android = "{http://schemas.android.com/apk/res/android}"
    application = document.find("application")
    expected_cleartext = "true" if api_url.startswith("http://") else "false"
    if application is None or application.get(android + "usesCleartextTraffic") != expected_cleartext:
        raise ValueError("Release manifest has the wrong cleartext HTTP policy")
    permissions = {item.get(android + "name") for item in document.findall("uses-permission")}
    if "android.permission.INTERNET" not in permissions:
        raise ValueError("Release manifest is missing Internet permission")
    if not any(activity.get(android + "windowSoftInputMode") == "adjustResize" for activity in application.findall("activity")):
        raise ValueError("Release activity must resize for the Android keyboard")
    print(f"Verified {checked_sources} current app sources, packaged API URL, isolated runtime imports, Internet permission, cleartext={expected_cleartext}, keyboard resize: {artifact.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--api-url", required=True)
    args = parser.parse_args()
    verify_package(args.artifact, args.api_url)
