from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ActivitySnapshot:
    process_name: str
    window_title: str
    idle_seconds: int


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class WindowsActivityTracker:
    def __init__(self, capture_window_title: bool = False) -> None:
        self.capture_window_title = capture_window_title

    def snapshot(self) -> ActivitySnapshot:
        if os.name != "nt":
            return ActivitySnapshot("unsupported-platform", "", 0)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = self._process_name(pid.value)
        title = self._window_title(hwnd) if self.capture_window_title else ""
        return ActivitySnapshot(process_name, title, self._idle_seconds())

    def _process_name(self, pid: int) -> str:
        if not pid:
            return "unknown"
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return f"pid-{pid}"
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            if not ok:
                return f"pid-{pid}"
            return Path(buffer.value).name or f"pid-{pid}"
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def _window_title(self, hwnd: int) -> str:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def _idle_seconds(self) -> int:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        tick_count = ctypes.windll.kernel32.GetTickCount()
        return max(0, int((tick_count - info.dwTime) / 1000))
