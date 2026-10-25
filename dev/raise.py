import ctypes, sys, time
from ctypes import wintypes
u = ctypes.WinDLL("user32"); k = ctypes.WinDLL("kernel32")
hits = []
PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _l):
    n = u.GetWindowTextLengthW(h)
    if n:
        b = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, b, n + 1)
        if b.value == sys.argv[1]:
            hits.append(h)
    return True
u.EnumWindows(PROC(cb), 0)
if not hits:
    print("not found"); sys.exit(1)
h = hits[0]
u.ShowWindow(h, 9)          # SW_RESTORE
u.MoveWindow(h, 60, 60, 600, 700, True)
u.BringWindowToTop(h)
fg = u.GetForegroundWindow()
t1 = u.GetWindowThreadProcessId(fg, None); t2 = k.GetCurrentThreadId()
u.AttachThreadInput(t2, t1, True); u.SetForegroundWindow(h); u.AttachThreadInput(t2, t1, False)
print("raised", h)
