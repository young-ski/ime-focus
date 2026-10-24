"""Windows 托盘图标（shell 通知区），纯 ctypes 实现。

pystray 在部分机器上于 `ChangeWindowMessageFilterEx` 处报 WinError 5，
建窗口阶段就抛异常，这里自己接管：注册窗口类 → 隐藏窗口 → Shell_NotifyIcon。
"""

from __future__ import annotations

import base64
import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_TRAY = 0x8000 + 1

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0x0, 0x1, 0x2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100

ID_SHOW, ID_TOGGLE, ID_QUIT = 1001, 1002, 1003
ICON_SIZE = 32


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


user32.CreateIconFromResourceEx.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.CreateIconFromResourceEx.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.TrackPopupMenu.restype = ctypes.c_int
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]

# 这些参数是 64 位量，不声明 argtypes 会让 lparam 被截断成 int
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                               wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
# HMODULE 是 64 位指针，不声明 restype 会被截断成 int
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

_ICON_ON = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAB+0lEQVR4nGNgGGDAiE9SNfn1"
    "f2pYcnuuKE57GGlpMTEOYaKX5bjMZqKX5bjsYKKn5djsYmIYYMBEb9/DAMxOJoYBBkyjDmAY"
    "6VHAgk+SmYmBIcuHiyHEhoNBhI+J4cGrvwyzd3xj2HDsJ1zNnnZBBjlRZoacaZ/A6sw1WBl+"
    "/PrPsObIT4betV8Z/v2nwAH10TwMEfYccL6qFDNDVxIvAzsLI8PKQz9Q1Pan8TGwQk3jZGNk"
    "SPXgZLj99A/DhuMIx5IUBXKizAzhdhwMn779Zwhq/sCgnfGGIan/I9hHef5c4NBBBi/e/2Xw"
    "qnvP4FD2juHR679gMVsdNgZCgAWXBCgoGRkZGPi4GBnW1QqgyInyMzHIizEz3HsBsQgElu7/"
    "wXDnGYS/9/wvhkQ3TgZuDry1Pf4QEODGr1mYD1Xrqw//4OyvPyERz0TYfgacIfDmE8TABy//"
    "MrhVvydo0B9EYDD8J6FgZ8Ilcf7uH7BBCuLMDFEOHODgBNG35ogwHOsTYmBhZqAKYMElAfL5"
    "ppM/Gfwt2BkaYnjAGAYmb/qG4mOaOAAEqhd8YXj+9i+DrwUHgyg/I8PTN/8Y5u36jpEFKQGM"
    "A1Udw9qITAwDDJgGhQNu42m30wrA7GRiGGDABGPQMxSQ7WLCJUEPyzEcQGtHYDObEZ8GenRO"
    "BxwAAOIYqSFOFaNKAAAAAElFTkSuQmCC"
)
_ICON_OFF = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAB4klEQVR4nO1Xu4oyMRg983lD"
    "vFQqPoAW1gripRFBsNdO8A0sxFawUGxstLGz9QEsbAQLQQSx8gEsvaKihYiIywRmWFkzLu46"
    "s/D/B4Z8yUlyzpdJmAygMQQlMpfL3X5DpNFocHWEdwp/xwipJc6bm9QS52mQmuKPtAgag9TO"
    "XoKkSdAY9N8A/vVXoFciiQiJRAKhUAg2mw3r9Rq9Xg/j8VjuUywW4XA40Gq1EAwG4fV6cblc"
    "MBqN0Ol0cLvdXjeQSqUQiUTkutvtRiaTgcFgwHA4vOubzWah0+lYbDQaEY/HMZ/P78w+TBIc"
    "iFmFw2GcTifUajXk83k0m02WUTKZZKvzGfv9HtVqFaVSCZvNhrX5fD48g55HeDweCIIAs9mM"
    "QqFwx9ntdjidTiyXS7ltMBhgsViweDqdIhaLwWQyPTVAPMJisSgOtFqtd/XD4SDH5/OZlWIC"
    "L6/A8Xhk5Wq1QqVSeTrR9XrFKyAeMZvN2Pt2uVyIRqNsOcWyXq+jXC7LG+6n0PMI8chNJhME"
    "AgGk02n2SOh2uy9n/G0DItrtNna7Hfx+P9t42+0W/X7/yxH8CQStPsfSHZGgMehPGGgo3Nvf"
    "BUmToDFICtRchc9axCPUEP9i4N0mHs0tKA1Q4+dUc3wA4qesNRg2lTcAAAAASUVORK5CYII="
)


def _new_hicon(png_b64: str) -> int:
    """PNG 数据直接交给 CreateIconFromResourceEx（0x30000 版式即 PNG 图标）。

    注意要传图片数据本身，不是包了 ICO 头的一整个文件，否则返回 NULL。
    """
    png = base64.b64decode(png_b64)
    buffer = ctypes.create_string_buffer(png, len(png))
    icon = user32.CreateIconFromResourceEx(
        buffer, len(png), True, 0x00030000, ICON_SIZE, ICON_SIZE, 0
    )
    return icon or 0


class Tray:
    """托盘图标。回调在托盘线程上触发，调用方自行切回 UI 线程。"""

    def __init__(self, title: str, *, on_show, on_toggle, on_quit) -> None:
        self.title = title
        self._on_show = on_show
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._enabled = True
        self._hwnd = 0
        self._icons: dict[bool, int] = {}
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)

    # ---------- 生命周期 ----------

    @property
    def error(self) -> Exception | None:
        return self._error

    @property
    def available(self) -> bool:
        return bool(self._hwnd)

    def start(self) -> bool:
        self._thread.start()
        self._ready.wait(timeout=3)
        return self.available

    def stop(self) -> None:
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        self._thread.join(timeout=2)

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if self._hwnd:
            self._notify(NIM_MODIFY)

    # ---------- 内部 ----------

    def _notify(self, action: int) -> None:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self._icons[self._enabled]
        data.szTip = f"{self.title}（{'监视中' if self._enabled else '已暂停'}）"
        shell32.Shell_NotifyIconW(action, ctypes.byref(data))

    def _run(self) -> None:
        try:
            self._icons = {True: _new_hicon(_ICON_ON), False: _new_hicon(_ICON_OFF)}
            self._proc = WNDPROC(self._wndproc)
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = self._proc
            wc.hInstance = kernel32.GetModuleHandleW(None)
            wc.hIcon = self._icons[True]
            wc.lpszClassName = "imefocus_tray"
            if not user32.RegisterClassExW(ctypes.byref(wc)):
                raise ctypes.WinError(ctypes.get_last_error())

            hwnd = user32.CreateWindowExW(0, wc.lpszClassName, self.title, 0x80000000,
                                          0, 0, 0, 0, None, None, wc.hInstance, None)
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hwnd = hwnd
            self._notify(NIM_ADD)
            self._ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            self._error = exc
            self._ready.set()
        finally:
            if self._hwnd:
                self._notify(NIM_DELETE)
                user32.DestroyWindow(self._hwnd)
                self._hwnd = 0
            for icon in self._icons.values():
                if icon:
                    user32.DestroyIcon(icon)
            self._icons = {}

    def _menu(self) -> None:
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_SHOW, "显示窗口")
        flags = MF_STRING | (MF_CHECKED if self._enabled else 0)
        user32.AppendMenuW(menu, flags, ID_TOGGLE, "启用")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "退出")

        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self._hwnd)
        chosen = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
            point.x, point.y, 0, self._hwnd, None,
        )
        user32.PostMessageW(self._hwnd, 0x0000, 0, 0)  # WM_NULL：让菜单正常消失
        user32.DestroyMenu(menu)

        if chosen == ID_SHOW:
            self._on_show()
        elif chosen == ID_TOGGLE:
            self._on_toggle()
        elif chosen == ID_QUIT:
            self._on_quit()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            event = lparam & 0xFFFF
            if event == WM_LBUTTONUP:
                self._on_show()
            elif event == WM_RBUTTONUP:
                self._menu()
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
