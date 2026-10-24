"""Windows 侧胶水：UI Automation 焦点读取 + 键盘布局切换。"""

from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
from dataclasses import replace

from .rules import FocusInfo

WM_INPUTLANGCHANGEREQUEST = 0x0050
KLF_ACTIVATE = 0x00000001
EN_US_KLID = "00000409"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

UIA_EDIT_CONTROL_TYPE_ID = 50004
UIA_DOCUMENT_CONTROL_TYPE_ID = 50030

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.LoadKeyboardLayoutW.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
user32.LoadKeyboardLayoutW.restype = wintypes.HKL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
user32.GetKeyboardLayout.restype = wintypes.HKL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

_automation = None


def _uia():
    """惰性创建 UIA 对象（首次调用约 100ms）。"""
    global _automation
    if _automation is None:
        import comtypes.client as cc

        cc.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA

        _automation = cc.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
    return _automation


def process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        kernel32.CloseHandle(handle)


def focused() -> FocusInfo:
    """取当前焦点元素。UIA 不可用时退化成只有进程名。"""
    hwnd = user32.GetForegroundWindow() or 0
    info = FocusInfo(hwnd=hwnd, process=process_name(hwnd) if hwnd else "")
    if not hwnd:
        return info

    try:
        element = _uia().GetFocusedElement()
    except Exception:
        return info
    if element is None:
        return info

    with contextlib.suppress(Exception):
        info = replace(
            info,
            class_name=element.CurrentClassName or "",
            is_password=bool(element.CurrentIsPassword),
            is_editable=element.CurrentControlType
            in (UIA_EDIT_CONTROL_TYPE_ID, UIA_DOCUMENT_CONTROL_TYPE_ID),
        )
    return info


def activate_layout(hwnd: int, klid: str) -> int:
    """请求把窗口所在线程切到 klid 布局，返回 hkl；0 表示该布局不可用。"""
    hkl = user32.LoadKeyboardLayoutW(klid, KLF_ACTIVATE)
    if not hkl:
        return 0
    user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
    return hkl


def current_layout(hwnd: int) -> int:
    thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    return user32.GetKeyboardLayout(thread_id) or 0


def installed_layouts() -> list[int]:
    count = user32.GetKeyboardLayoutList(0, None)
    if count <= 0:
        return []
    buf = (wintypes.HKL * count)()
    got = user32.GetKeyboardLayoutList(count, buf)
    return [buf[i] for i in range(max(0, got))]
