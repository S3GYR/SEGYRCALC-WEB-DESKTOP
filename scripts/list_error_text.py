import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32


def text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


tops: list[int] = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def top(hwnd, _lparam):
    if user32.IsWindowVisible(hwnd) and text(hwnd) == "SEGYRCALC":
        tops.append(hwnd)
    return True


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def child(hwnd, _lparam):
    value = text(hwnd)
    if value:
        print("CHILD", value)
    return True


user32.EnumWindows(top, 0)
for item in tops:
    print("TOP", item)
    user32.EnumChildWindows(item, child, 0)
