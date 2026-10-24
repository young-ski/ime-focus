from imefocus import win


class _BrokenClassName:
    """模拟跨进程元素的 CurrentClassName 返回 NULL BSTR。"""

    CurrentIsPassword = 1
    CurrentControlType = 50004

    @property
    def CurrentClassName(self):
        raise ValueError("NULL COM pointer access")


class _FakeUia:
    def GetFocusedElement(self):
        return _BrokenClassName()


def test_single_null_property_does_not_erase_password_flag(monkeypatch):
    monkeypatch.setattr(win, "_uia", lambda: _FakeUia())
    monkeypatch.setattr(win.user32, "GetForegroundWindow", lambda: 42)
    monkeypatch.setattr(win, "process_name", lambda _hwnd: "chrome.exe")

    info = win.focused()

    assert info.is_password is True
    assert info.is_editable is True
    assert info.class_name == ""
    assert info.process == "chrome.exe"


def test_no_foreground_window_is_safe(monkeypatch):
    monkeypatch.setattr(win.user32, "GetForegroundWindow", lambda: 0)
    info = win.focused()
    assert info.hwnd == 0
    assert info.is_password is False


class _InputSite:
    CurrentIsPassword = 0
    CurrentControlType = 50037
    CurrentClassName = "InputSiteWindowClass"


class _RealEdit:
    CurrentIsPassword = 1
    CurrentControlType = 50004
    CurrentClassName = "Edit"


class _Walker:
    def GetParentElement(self, _el):
        return _RealEdit()


class _SiteUia:
    RawViewWalker = _Walker()

    def GetFocusedElement(self):
        return _InputSite()


def test_input_site_wrapper_resolves_to_real_control(monkeypatch):
    monkeypatch.setattr(win, "_uia", lambda: _SiteUia())
    monkeypatch.setattr(win.user32, "GetForegroundWindow", lambda: 7)
    monkeypatch.setattr(win, "process_name", lambda _hwnd: "notepad.exe")

    info = win.focused()

    assert info.is_password is True
    assert info.class_name == "Edit"
    assert info.is_editable is True
