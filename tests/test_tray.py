import time

import pytest

from imefocus.tray import Tray


def test_tray_starts_toggles_and_stops():
    tray = Tray("ime-focus", on_show=lambda: None, on_toggle=lambda: None, on_quit=lambda: None)
    if not tray.start():
        pytest.skip(f"当前桌面没有通知区: {tray.error}")

    assert tray.available
    tray.set_enabled(False)
    time.sleep(0.2)
    tray.set_enabled(True)
    time.sleep(0.2)

    tray.stop()
    assert not tray.available
