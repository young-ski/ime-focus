import ctypes, subprocess, time
from ctypes import wintypes

from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

u = ctypes.WinDLL("user32")
k = ctypes.WinDLL("kernel32")

subprocess.Popen([
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "--force-renderer-accessibility",
    f"--user-data-dir={OUT / 'edgeprof'}",
    (OUT / "pw.html").as_uri(),
])
time.sleep(6)
hits = []
PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _l):
    n = u.GetWindowTextLengthW(h)
    if n:
        b = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, b, n + 1)
        if "pw test" in b.value:
            hits.append(h)
    return True
u.EnumWindows(PROC(cb), 0)
open(str(OUT / "edgeopen.out"), "w", encoding="utf-8").write(str([hex(h) for h in hits]))
if hits:
    h = hits[0]
    u.ShowWindow(h, 9)
    u.SetForegroundWindow(h)
