import pytest

@pytest.fixture(autouse=True)
def panel_test_marker():
    # Keep the fixture layer intentionally side-effect free. Flask route setup
    # is handled by importing app9 before the first request in test_panel.py.
    yield
