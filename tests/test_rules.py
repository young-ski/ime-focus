import pytest

from imefocus.rules import EN, IDLE, Action, FocusInfo, Rules, decide

PW = FocusInfo(hwnd=1, process="chrome.exe", class_name="Edit", is_password=True, is_editable=True)
TEXT = FocusInfo(hwnd=1, process="chrome.exe", class_name="Document", is_editable=True)
BG = FocusInfo(hwnd=1, process="chrome.exe", class_name="Chrome_WidgetWin_1")

RULES = Rules()


@pytest.mark.parametrize(
    ("info", "state", "expected"),
    [
        (PW, IDLE, Action.TO_EN),
        (PW, EN, Action.NOOP),
        (TEXT, EN, Action.RESTORE),
        (TEXT, IDLE, Action.NOOP),
        (BG, EN, Action.RESTORE),
        (BG, IDLE, Action.NOOP),
        (FocusInfo(), IDLE, Action.NOOP),
    ],
)
def test_transitions(info, state, expected):
    assert decide(info, state, RULES).action is expected


def test_disabled_never_acts():
    assert decide(PW, IDLE, Rules(enabled=False)).action is Action.NOOP


def test_ignore_list_is_case_insensitive():
    rules = Rules(ignore=("KeePass.exe",))
    keepass = FocusInfo(hwnd=1, process="KEEPASS.EXE", is_password=True, is_editable=True)
    assert decide(keepass, IDLE, rules).action is Action.NOOP


def test_allowlist_blocks_other_processes():
    rules = Rules(only_in=("firefox.exe",))
    assert decide(PW, IDLE, rules).action is Action.NOOP


def test_allowlist_lets_listed_process_through():
    rules = Rules(only_in=("Chrome.exe",))
    assert decide(PW, IDLE, rules).action is Action.TO_EN
