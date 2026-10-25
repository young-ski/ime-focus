import ctypes, time
from ctypes import wintypes
from imefocus import win

from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


u = ctypes.WinDLL("user32")
u.CreateWindowExW.restype = wintypes.HWND
WS_VISIBLE, WS_OVERLAPPEDWINDOW, ES_PASSWORD = 0x10000000, 0x00CF0000, 0x20

out = []
def log(*a):
    out.append(" ".join(map(str, a)))
    open(str(OUT / "elem.out"), "w", encoding="utf-8").write("\n".join(out))

h = u.CreateWindowExW(0, "EDIT", "", WS_VISIBLE | WS_OVERLAPPEDWINDOW | ES_PASSWORD,
                      600, 420, 460, 90, None, None, None, None)
time.sleep(0.5)

win.prepare_thread()
uia = win._uia()
def desc(e):
    def g(n):
        try: return getattr(e, n)
        except Exception as exc: return f"<{type(exc).__name__}>"
    return f"type={g('CurrentControlType')} cls={g('CurrentClassName')!r} pw={g('CurrentIsPassword')} name={str(g('CurrentName'))[:20]!r}"

el = uia.ElementFromHandle(h)
log("handle el:", desc(el))
walker = uia.RawViewWalker
child = None
try: child = walker.GetFirstChildElement(el)
except Exception as exc: log("child err", type(exc).__name__)
n = 0
while child is not None and n < 4:
    log("  child:", desc(child))
    try: child = walker.GetNextSiblingElement(child)
    except Exception: break
    n += 1
par = None
try: par = walker.GetParentElement(el)
except Exception as exc: log("parent err", type(exc).__name__)
if par is not None:
    log("  parent:", desc(par))
time.sleep(2)
