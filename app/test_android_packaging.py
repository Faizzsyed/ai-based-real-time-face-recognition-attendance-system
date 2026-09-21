import os
import subprocess
import sys

def test_android_packaged_runtime_imports():
    """
    Test that the app can be run as if it was packaged by Flet for Android.
    Flet Android build extracts the contents of 'app/' into the root of the serious_python environment.
    Therefore, there is no parent 'app' package. 
    This test verifies that the sys.modules alias in main.py correctly allows 'import app.xxx' to succeed.
    """
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(app_dir)
    
    # Run python in the app_dir, and just try to import main.
    # We must unset PYTHONPATH so it doesn't inherit the project root from the pytest env!
    
    env = os.environ.copy()
    if "PYTHONPATH" in env:
        del env["PYTHONPATH"]
        
    code = (
        "import sys\n"
        "import main\n"
        "print('Android import runtime fix is working')\n"
    )
    
    # We use the python executable from the environment, assuming pytest is run in the venv
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=app_dir,
        env=env,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Simulated Android runtime failed:\n{result.stderr}\n{result.stdout}"
    assert "Android import runtime fix is working" in result.stdout
