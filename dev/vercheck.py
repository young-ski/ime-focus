import comtypes.client as cc
cc.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient as UIA

from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


uia = cc.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
el = uia.GetFocusedElement()
out = []
for name in ("CurrentClassName", "CurrentControlType", "CurrentIsPassword"):
    try:
        out.append(f"{name}={getattr(el, name)!r}")
    except Exception as exc:
        out.append(f"{name}=<{type(exc).__name__}>")
open(str(OUT / "vercheck.out"), "w", encoding="utf-8").write("\n".join(out))
