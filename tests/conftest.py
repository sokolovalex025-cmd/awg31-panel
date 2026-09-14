import importlib
import os
import pytest

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")

@pytest.fixture(autouse=True)
def reset_panel_modules():
    # app9 registers Flask routes at import time. Ensure each test gets a fresh
    # app module so a previous test request cannot lock Flask setup.
    for name in ("app9",):
        importlib.sys.modules.pop(name, None)
    yield
    importlib.sys.modules.pop("app9", None)
