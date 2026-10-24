"""Windows 侧胶水：UI Automation 焦点读取 + 键盘布局切换。"""

from __future__ import annotations

import contextlib
import ctypes
import threading
from ctypes import wintypes
from dataclasses import replace

import comtypes.client as cc

from .rules import FocusInfo

WM_INPUTLANGCHANGEREQUEST = 0x0050
KLF_ACTIVATE = 0x00000001
EN_US_KLID = "00000409"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

UIA_EDIT_CONTROL_TYPE_ID = 50004
UIA_DOCUMENT_CONTROL_TYPE_ID = 50030
UIA_WINDOW_CONTROL_TYPE_ID = 50032

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
_tls = threading.local()

ole32 = ctypes.WinDLL("ole32")


def prepare_thread() -> None:
    """把当前线程切到 MTA 并初始化 COM。

    引擎跑在自己的线程里，不初始化 COM 时 UIA 调用会静默失败；而 UIA 官方
    推荐 MTA（STA 还需要消息泵，引擎线程没有）。comtypes 在本模块 import 时
    已经于主线程做过 STA 初始化，所以这里只负责当前线程。
    """
    if getattr(_tls, "ready", False):
        return
    ole32.CoInitializeEx(None, 0x0)  # COINIT_MULTITHREADED，重复初始化返回 S_FALSE
    _tls.ready = True


def _uia():
    """惰性创建 UIA 对象（首次调用约 100ms）。"""
    global _automation
    prepare_thread()
    if _automation is None:
        module = cc.GetModule("UIAutomationCore.dll")
        _automation = cc.CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
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


def _read(getter, default):
    """单个属性读失败就给默认值。

    UIA 元素（尤其跨进程的）常有属性返回 NULL BSTR，整块 try 会把
    已经读到的字段一起丢掉，所以逐个读。
    """
    try:
        value = getter()
    except Exception:
        return default
    return default if value is None else value


def focused() -> FocusInfo:
    """取当前焦点元素。UIA 不可用时退化成只有进程名。"""
    hwnd = user32.GetForegroundWindow() or 0
    info = FocusInfo(hwnd=hwnd, process=process_name(hwnd) if hwnd else "")
    if not hwnd:
        return info

    with contextlib.suppress(Exception):
        element = _uia().GetFocusedElement()
        if element is None:
            return info
        target = _real_control(element)
        return replace(
            info,
            class_name=_read(lambda: target.CurrentClassName, ""),
            is_password=bool(_read(lambda: target.CurrentIsPassword, 0)),
            is_editable=_read(lambda: target.CurrentControlType, 0)
            in (UIA_EDIT_CONTROL_TYPE_ID, UIA_DOCUMENT_CONTROL_TYPE_ID),
        )
    return info


def _real_control(element):
    """把焦点元素还原成真正持有 IsPassword 的控件。

    对 Win32 编辑框，GetFocusedElement 常常返回 ``InputSiteWindowClass``
    这层包装（IsPassword 恒为 false），真正的 Edit 在它的祖先上。
    """
    if _read(lambda: element.CurrentIsPassword, 0):
        return element
    try:
        walker = _uia().RawViewWalker
    except Exception:
        return element

    node = element
    for _ in range(3):
        try:
            node = walker.GetParentElement(node)
        except Exception:
            return element
        if node is None:
            return element
        if _read(lambda n=node: n.CurrentIsPassword, 0):
            return node
        # 已经走到窗口/桌面层就没必要再往上
        if _read(lambda n=node: n.CurrentControlType, 0) in (
            UIA_EDIT_CONTROL_TYPE_ID,
            UIA_DOCUMENT_CONTROL_TYPE_ID,
            UIA_WINDOW_CONTROL_TYPE_ID,
        ):
            return element
    return element


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
