import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
windows: list[tuple[int, str]] = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def callback(hwnd, _lparam):
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            windows.append((int(hwnd), buffer.value))
    return True


user32.EnumWindows(callback, 0)
for item in windows:
    print(item)
