from imefocus import win
from imefocus.engine import Engine
from imefocus.rules import Action, FocusInfo, Rules

PW = FocusInfo(hwnd=7, process="chrome.exe", class_name="Edit", is_password=True, is_editable=True)
TEXT = FocusInfo(hwnd=7, process="chrome.exe", class_name="Document", is_editable=True)


def _focus_sequence(monkeypatch, sequence):
    """按顺序返回焦点元素，走完后停在最后一个。"""
    frames = iter(sequence)
    last = sequence[-1]
    monkeypatch.setattr(win, "focused", lambda: next(frames, last))


def test_switches_then_restores(monkeypatch):
    _focus_sequence(monkeypatch, [PW, TEXT])
    switched: list[str] = []
    posted: list[tuple] = []
    monkeypatch.setattr(win, "current_layout", lambda _hwnd: 0x4090409)
    monkeypatch.setattr(win, "activate_layout", lambda _hwnd, klid: switched.append(klid) or 1)
    monkeypatch.setattr(win.user32, "PostMessageW", lambda *args: posted.append(args))
    monkeypatch.setattr(win.user32, "GetForegroundWindow", lambda: 7)

    events: list = []
    engine = Engine(Rules(), on_event=events.append)

    engine.tick()
    engine.tick()

    assert [e.action for e in events] == [Action.TO_EN, Action.RESTORE]
    assert switched == ["00000409"]
    assert posted and posted[0][3] == 0x4090409


def test_staying_in_password_field_emits_once(monkeypatch):
    _focus_sequence(monkeypatch, [PW, PW, PW])
    monkeypatch.setattr(win, "current_layout", lambda _hwnd: 0x4090409)
    monkeypatch.setattr(win, "activate_layout", lambda _hwnd, _klid: 1)

    events: list = []
    engine = Engine(Rules(), on_event=events.append)
    for _ in range(3):
        engine.tick()

    assert [e.action for e in events] == [Action.TO_EN]


def test_dry_run_does_not_touch_keyboard(monkeypatch):
    _focus_sequence(monkeypatch, [PW])

    def boom(*_args):
        raise AssertionError("试跑不应切换布局")

    monkeypatch.setattr(win, "activate_layout", boom)

    events: list = []
    engine = Engine(Rules(), dry_run=True, on_event=events.append)
    engine.tick()

    assert [e.action for e in events] == [Action.TO_EN]


def test_paused_engine_stays_quiet(monkeypatch):
    _focus_sequence(monkeypatch, [PW])
    events: list = []
    engine = Engine(Rules(enabled=False), on_event=events.append)
    engine.tick()
    assert events == []


def test_failure_in_one_tick_is_reported_not_raised(monkeypatch):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(win, "focused", boom)

    events: list = []
    Engine(Rules(), on_event=events.append).tick()

    assert events and "boom" in events[0].reason
