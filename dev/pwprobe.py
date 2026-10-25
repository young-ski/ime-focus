import ctypes, threading, time
from ctypes import wintypes
from imefocus import win

from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


u = ctypes.WinDLL("user32"); k = ctypes.WinDLL("kernel32")
u.CreateWindowExW.restype = wintypes.HWND

out = []
def log(*a):
    out.append(" ".join(map(str, a)))
    open(str(OUT / "pwprobe.out"), "w", encoding="utf-8").write("\n".join(out))

WS_VISIBLE, WS_OVERLAPPEDWINDOW, ES_PASSWORD, WS_EX_TOPMOST = 0x10000000, 0x00CF0000, 0x20, 0x8
h = u.CreateWindowExW(WS_EX_TOPMOST, "EDIT", "", WS_VISIBLE | WS_OVERLAPPEDWINDOW | ES_PASSWORD,
                      500, 300, 420, 90, None, None, None, None)
u.ShowWindow(h, 5)
u.SetWindowPos(h, -1, 500, 300, 420, 90, 0x0040)
time.sleep(0.4)

def click_and_focus() -> bool:
    before = u.GetForegroundWindow()
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    u.SetCursorPos(cx, cy)
    time.sleep(0.1)
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.4)
    u.SetFocus(h)
    after = u.GetForegroundWindow()
    log("click: rect", r.left, r.top, r.right, r.bottom, "->", cx, cy, "cursor", pt.x, pt.y,
        "before", hex(before), "after", hex(after), "match", after == h)
    return after == h

u.AllowSetForegroundWindow(-1)   # ASFW_ANY
ok = False
for _ in range(10):
    if click_and_focus():
        ok = True
        break
log("front ok:", ok, "class:", (lambda b: (u.GetClassNameW(u.GetForegroundWindow(), b, 64), b.value)[1])(ctypes.create_unicode_buffer(64)))

def work():
    win.prepare_thread()
    info = win.focused()
    for i in range(15):
        log("sample", i, "ours", info.hwnd == h, "cls", repr(info.class_name),
            "pw", info.is_password, "editable", info.is_editable)
        if info.hwnd == h and info.is_password:
            log("RESULT: detected password field")
            break
        time.sleep(0.12)
        info = win.focused()

t = threading.Thread(target=work); t.start(); t.join()
time.sleep(25)
