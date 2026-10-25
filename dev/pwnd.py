import ctypes, time
from ctypes import wintypes

from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

u = ctypes.WinDLL("user32"); k = ctypes.WinDLL("kernel32")
u.CreateWindowExW.restype = wintypes.HWND

WS_VISIBLE, WS_OVERLAPPEDWINDOW, ES_PASSWORD = 0x10000000, 0x00CF0000, 0x20
h = u.CreateWindowExW(0, "EDIT", "", WS_VISIBLE | WS_OVERLAPPEDWINDOW | ES_PASSWORD,
                      760, 470, 420, 90, None, None, None, None)
u.ShowWindow(h, 5)
u.BringWindowToTop(h)
u.AllowSetForegroundWindow(-1)
fg = u.GetForegroundWindow()
t1 = u.GetWindowThreadProcessId(fg, None); t2 = k.GetCurrentThreadId()
u.AttachThreadInput(t2, t1, True); u.SetForegroundWindow(h); u.SetFocus(h)
u.AttachThreadInput(t2, t1, False)
open(str(OUT / "pwnd.out"), "w", encoding="utf-8").write(f"hwnd={h} fg={u.GetForegroundWindow()}")

# 真正的消息循环：不泵消息的话前台会被系统收回
msg = wintypes.MSG()
end = time.time() + 40
while time.time() < end:
    if u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))
    else:
        time.sleep(0.01)
