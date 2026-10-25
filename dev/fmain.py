import ctypes, time
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
    open(str(OUT / "fmain.out"), "w", encoding="utf-8").write("\n".join(out))

h = u.CreateWindowExW(0, "EDIT", "", 0x10000000 | 0x00CF0000 | 0x20, 500, 300, 420, 90,
                      None, None, None, None)
u.ShowWindow(h, 5); u.BringWindowToTop(h)
u.AllowSetForegroundWindow(-1)
u.SetForegroundWindow(h); u.SetFocus(h)
time.sleep(0.4)
log("fg ours:", u.GetForegroundWindow() == h)

t0 = time.time()
info = win.focused()
log("elapsed:", round(time.time() - t0, 2), "cls:", repr(info.class_name), "pw:", info.is_password,
    "editable:", info.is_editable, "ours:", info.hwnd == h)
time.sleep(15)
