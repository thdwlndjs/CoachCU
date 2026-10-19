from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable, Optional

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


class WindowsSessionEventMonitor:
    """Registers a Qt window handle for Windows session unlock notifications."""

    def __init__(self, hwnd: int, on_unlock: Callable[[], None]) -> None:
        self.hwnd = hwnd
        self.on_unlock = on_unlock
        self._registered = False

    def start(self) -> bool:
        wtsapi32 = ctypes.windll.wtsapi32
        result = wtsapi32.WTSRegisterSessionNotification(
            wintypes.HWND(self.hwnd),
            wintypes.DWORD(NOTIFY_FOR_THIS_SESSION),
        )
        self._registered = bool(result)
        return self._registered

    def stop(self) -> None:
        if self._registered:
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(wintypes.HWND(self.hwnd))
            self._registered = False

    def handle_native_message(self, message: int, w_param: int) -> None:
        if message == WM_WTSSESSION_CHANGE and w_param == WTS_SESSION_UNLOCK:
            self.on_unlock()
