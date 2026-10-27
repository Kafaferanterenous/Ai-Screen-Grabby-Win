"""Local, dependency-free Windows window capture and MCP stdio server."""

from __future__ import annotations

import argparse
import base64
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from typing import Optional
import zlib


VERSION = "0.5.0"
PROTOCOL_VERSION = "2025-06-18"
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DEFAULT_DIR = APP_ROOT / "captures"
SETTINGS_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "Ai_Screen_Grabby" / "settings.json"
STARTUP_NAME = "Ai Screen Grabby"
THEMES = ("Light", "Dark", "Navy", "Darker Pastel")


def cli_command(*arguments: str) -> list[str]:
    if getattr(sys, "frozen", False):
        executable = APP_ROOT / "Grabby.exe"
        if not executable.is_file():
            raise FileNotFoundError(f"Grabby.exe is required beside this app: {executable}")
        return [str(executable), *map(str, arguments)]
    return [sys.executable, str(Path(__file__).resolve()), *map(str, arguments)]


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        directory = data.get("output_directory", str(DEFAULT_DIR))
        if not isinstance(directory, str) or not Path(directory).is_absolute():
            raise ValueError("Invalid output directory")
        theme = data.get("theme", "Light")
        if theme not in THEMES:
            theme = "Light"
        return {"output_directory": directory, "theme": theme}
    except (OSError, ValueError, TypeError):
        return {"output_directory": str(DEFAULT_DIR), "theme": "Light"}


def save_settings(directory: Optional[str] = None, theme: Optional[str] = None) -> dict:
    data = load_settings()
    if directory is not None:
        path = Path(directory).expanduser()
        if not path.is_absolute():
            raise ValueError("Output directory must be an absolute path")
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError("Output directory is not a directory")
        data["output_directory"] = str(path.resolve())
    if theme is not None:
        if theme not in THEMES:
            raise ValueError(f"Theme must be one of: {', '.join(THEMES)}")
        data["theme"] = theme
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=SETTINGS_PATH.parent,
                                         prefix="settings-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file, indent=2)
        os.replace(temporary, SETTINGS_PATH)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return load_settings()


def set_output_directory(directory: str) -> dict:
    return save_settings(directory=directory)


def default_output_path(hwnd: int) -> str:
    directory = Path(load_settings()["output_directory"])
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f"grabby-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{hwnd}.png")


def startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            winreg.QueryValueEx(key, STARTUP_NAME)
        return True
    except FileNotFoundError:
        return False


def set_startup(enabled: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows is required")
    import winreg
    registry_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
            if getattr(sys, "frozen", False):
                gui_executable = APP_ROOT / "GrabbyGUI.exe"
                if not gui_executable.is_file():
                    raise FileNotFoundError(f"GrabbyGUI.exe is required beside this app: {gui_executable}")
                launch = [str(gui_executable)]
            else:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                executable = pythonw if pythonw.exists() else Path(sys.executable)
                launch = [str(executable), str(Path(__file__).resolve()), "gui"]
            command = subprocess.list2cmdline(launch)
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            return
        with key:
            try:
                winreg.DeleteValue(key, STARTUP_NAME)
            except FileNotFoundError:
                pass

if sys.platform == "win32":
    user32 = C.WinDLL("user32", use_last_error=True)
    gdi32 = C.WinDLL("gdi32", use_last_error=True)
    WNDENUMPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

    class RECT(C.Structure):
        _fields_ = [("left", W.LONG), ("top", W.LONG), ("right", W.LONG), ("bottom", W.LONG)]

    class WINDOWPLACEMENT(C.Structure):
        _fields_ = [("length", W.UINT), ("flags", W.UINT), ("showCmd", W.UINT),
                    ("ptMinPosition", W.POINT), ("ptMaxPosition", W.POINT), ("rcNormalPosition", RECT)]

    class BITMAPINFOHEADER(C.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                    ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD),
                    ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG),
                    ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]

    class BITMAPINFO(C.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", W.DWORD * 3)]

    user32.EnumWindows.argtypes = [WNDENUMPROC, W.LPARAM]
    user32.EnumWindows.restype = W.BOOL
    user32.IsWindowVisible.argtypes = [W.HWND]
    user32.IsWindowVisible.restype = W.BOOL
    user32.IsWindow.argtypes = [W.HWND]
    user32.IsWindow.restype = W.BOOL
    user32.IsIconic.argtypes = [W.HWND]
    user32.IsIconic.restype = W.BOOL
    user32.GetWindowTextLengthW.argtypes = [W.HWND]
    user32.GetWindowTextLengthW.restype = C.c_int
    user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user32.GetWindowTextW.restype = C.c_int
    user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user32.GetWindowThreadProcessId.restype = W.DWORD
    user32.GetWindowRect.argtypes = [W.HWND, C.POINTER(RECT)]
    user32.GetWindowRect.restype = W.BOOL
    user32.GetWindowPlacement.argtypes = [W.HWND, C.POINTER(WINDOWPLACEMENT)]
    user32.GetWindowPlacement.restype = W.BOOL
    user32.ShowWindow.argtypes = [W.HWND, C.c_int]
    user32.ShowWindow.restype = W.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = W.HWND
    user32.GetWindowDC.argtypes = [W.HWND]
    user32.GetWindowDC.restype = W.HDC
    user32.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user32.ReleaseDC.restype = C.c_int
    user32.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    user32.PrintWindow.restype = W.BOOL
    gdi32.CreateCompatibleDC.argtypes = [W.HDC]
    gdi32.CreateCompatibleDC.restype = W.HDC
    gdi32.DeleteDC.argtypes = [W.HDC]
    gdi32.DeleteDC.restype = W.BOOL
    gdi32.CreateDIBSection.argtypes = [W.HDC, C.POINTER(BITMAPINFO), W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD]
    gdi32.CreateDIBSection.restype = W.HBITMAP
    gdi32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    gdi32.SelectObject.restype = W.HGDIOBJ
    gdi32.DeleteObject.argtypes = [W.HGDIOBJ]
    gdi32.DeleteObject.restype = W.BOOL


def _title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = C.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _window(hwnd: int) -> dict:
    if not user32.IsWindow(hwnd):
        raise ValueError("Window handle no longer exists")
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(hwnd, C.byref(pid))
    rect = RECT()
    if not user32.GetWindowRect(hwnd, C.byref(rect)):
        raise OSError(C.get_last_error(), "GetWindowRect failed")
    minimized = bool(user32.IsIconic(hwnd))
    if minimized:
        placement = WINDOWPLACEMENT()
        placement.length = C.sizeof(WINDOWPLACEMENT)
        if user32.GetWindowPlacement(hwnd, C.byref(placement)):
            rect = placement.rcNormalPosition
    return {"hwnd": hwnd, "pid": pid.value, "title": _title(hwnd),
            "visible": bool(user32.IsWindowVisible(hwnd)), "minimized": minimized,
            "width": rect.right - rect.left, "height": rect.bottom - rect.top}


def list_windows() -> list[dict]:
    if sys.platform != "win32":
        raise RuntimeError("Windows is required")
    found = []

    @WNDENUMPROC
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd) and _title(hwnd):
            item = _window(hwnd)
            if item["width"] > 0 and item["height"] > 0:
                found.append(item)
        return True

    if not user32.EnumWindows(visit, 0):
        raise OSError(C.get_last_error(), "EnumWindows failed")
    return found


def resolve_window_title(title: str, match: str = "contains", pid: Optional[int] = None) -> dict:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("A nonempty window title is required")
    if match not in ("exact", "contains"):
        raise ValueError("Match must be 'exact' or 'contains'")
    needle = title.strip().casefold()
    candidates = []
    for item in list_windows():
        actual = item["title"].casefold()
        matched = actual == needle if match == "exact" else needle in actual
        if matched and (pid is None or item["pid"] == pid):
            candidates.append(item)
    if not candidates:
        raise ValueError(f"No window matches {title!r}; list windows and try again")
    if len(candidates) > 1:
        details = ", ".join(f'PID {item["pid"]} / HWND {item["hwnd"]}' for item in candidates[:5])
        raise ValueError(f"Several windows match {title!r}: {details}. Use an exact title, PID, or HWND")
    return candidates[0]


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff)


def _png(width: int, height: int, bgra: bytes) -> bytes:
    # DIB is top-down BGRA. PNG color type 2 is RGB; alpha is not meaningful for PrintWindow.
    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)
        row = bgra[y * stride:(y + 1) * stride]
        for x in range(0, stride, 4):
            rows.extend((row[x + 2], row[x + 1], row[x]))
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(rows, 6)) + _chunk(b"IEND", b""))


def capture(hwnd: int, expected_pid: int, output_path: str, overwrite: bool = False) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("Windows is required")
    item = _window(hwnd)
    if item["pid"] != expected_pid:
        raise ValueError("Window PID changed; list windows again")
    if not item["visible"] and not item["minimized"]:
        raise ValueError("Window must be visible or minimized")
    path = _validated_output_path(output_path, overwrite)
    initially_minimized = item["minimized"]
    try:
        if initially_minimized:
            user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE: render at normal size without taking focus.
            time.sleep(0.15)
            item = _window(hwnd)
            if item["minimized"]:
                raise RuntimeError("The target could not be restored without activating it")
        if item["pid"] != expected_pid:
            raise ValueError("Window PID changed; list windows again")
        return _capture_rendered(hwnd, expected_pid, path, overwrite, item, initially_minimized)
    finally:
        if initially_minimized and user32.IsWindow(hwnd):
            try:
                if _window(hwnd)["pid"] == expected_pid:
                    user32.ShowWindow(hwnd, 7)  # SW_SHOWMINNOACTIVE
            except (ValueError, OSError):
                pass


def _validated_output_path(output_path: str, overwrite: bool) -> Path:
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".png":
        raise ValueError("Output filename must end in .png")
    if not path.parent.is_dir():
        raise ValueError("Output directory must already exist")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {path}")
    return path


def _capture_rendered(hwnd: int, expected_pid: int, path: Path, overwrite: bool, item: dict,
                      initially_minimized: bool) -> dict:
    width, height = item["width"], item["height"]
    if not (1 <= width <= 16384 and 1 <= height <= 16384 and width * height <= 30_000_000):
        raise ValueError("Window dimensions exceed capture limits")
    source = user32.GetWindowDC(hwnd)
    if not source:
        raise OSError(C.get_last_error(), "GetWindowDC failed")
    memory = None
    bitmap = None
    old = None
    try:
        memory = gdi32.CreateCompatibleDC(source)
        if not memory:
            raise OSError(C.get_last_error(), "CreateCompatibleDC failed")
        info = BITMAPINFO()
        info.bmiHeader.biSize = C.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        pixels = C.c_void_p()
        bitmap = gdi32.CreateDIBSection(source, C.byref(info), 0, C.byref(pixels), None, 0)
        if not bitmap or not pixels.value:
            raise OSError(C.get_last_error(), "CreateDIBSection failed")
        old = gdi32.SelectObject(memory, bitmap)
        if not old:
            raise OSError(C.get_last_error(), "SelectObject failed")
        if not user32.PrintWindow(hwnd, memory, 0):
            raise RuntimeError("PrintWindow failed; this window may not support window rendering")
        png = _png(width, height, C.string_at(pixels, width * height * 4))
    finally:
        if old and memory:
            gdi32.SelectObject(memory, old)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory:
            gdi32.DeleteDC(memory)
        user32.ReleaseDC(hwnd, source)
    flags = "wb" if overwrite else "xb"
    with path.open(flags) as file:
        file.write(png)
    return {"path": str(path), "format": "png", "width": width, "height": height,
            "sha256": hashlib.sha256(png).hexdigest(), "bytes": len(png),
            "window": {"hwnd": hwnd, "pid": expected_pid, "title": item["title"]},
            "temporarily_restored": initially_minimized,
            "warning": "Some GPU-rendered and protected windows may yield blank or incomplete pixels; inspect the PNG."}


TOOLS = [
    {"name": "list_windows", "description": "List visible, titled local Windows windows with handle, PID, and dimensions.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "set_output_directory", "description": "Set the local directory used for subsequent captures by the GUI, CLI, and MCP tools.",
     "inputSchema": {"type": "object", "properties": {"directory": {"type": "string", "description": "Absolute local directory"}}, "required": ["directory"]}},
    {"name": "capture_window", "description": "Capture one listed window to a local PNG, including a covered window. A minimized window is briefly restored without activation and re-minimized. Uses PrintWindow. Omit output_path to use the configured directory. No automatic screen fallback.",
     "inputSchema": {"type": "object", "properties": {
         "hwnd": {"type": "integer", "description": "Window handle from list_windows"},
         "pid": {"type": "integer", "description": "Process ID from list_windows, checked to avoid a stale handle"},
         "output_path": {"type": "string", "description": "Optional absolute PNG path, including requested filename"},
         "overwrite": {"type": "boolean", "default": False},
         "include_image": {"type": "boolean", "default": False, "description": "Also return the PNG as MCP image content"}},
         "required": ["hwnd", "pid"]}},
    {"name": "capture_window_by_title", "description": "Capture one window by all or part of its title. Matching ignores case and refuses ambiguous results. A minimized window is briefly restored without activation and re-minimized.",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "Window title or unique part of it"},
         "match": {"type": "string", "enum": ["exact", "contains"], "default": "contains"},
         "pid": {"type": "integer", "description": "Optional process ID to disambiguate matches"},
         "output_path": {"type": "string", "description": "Optional absolute PNG path"},
         "overwrite": {"type": "boolean", "default": False},
         "include_image": {"type": "boolean", "default": False}},
         "required": ["title"]}},
]


def _mcp_capture(arguments: dict) -> dict:
    hwnd = int(arguments["hwnd"])
    pid = int(arguments["pid"])
    before = _window(hwnd)
    if before["pid"] != pid:
        raise ValueError("Window PID changed; list windows again")
    argv = cli_command("capture", "--hwnd", str(arguments["hwnd"]),
                       "--pid", str(arguments["pid"]), "--output",
                       str(arguments.get("output_path") or default_output_path(int(arguments["hwnd"]))))
    if arguments.get("overwrite"):
        argv.append("--overwrite")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired as exc:
        if before["minimized"] and sys.platform == "win32" and user32.IsWindow(hwnd):
            try:
                if _window(hwnd)["pid"] == pid:
                    user32.ShowWindow(hwnd, 7)
            except (ValueError, OSError):
                pass
        raise RuntimeError("Capture timed out after 10 seconds") from exc
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Capture failed")
    info = json.loads(proc.stdout)
    content = [{"type": "text", "text": json.dumps(info, ensure_ascii=False)}]
    if arguments.get("include_image"):
        content.append({"type": "image", "data": base64.b64encode(Path(info["path"]).read_bytes()).decode("ascii"), "mimeType": "image/png"})
    return {"content": content, "isError": False}


def mcp_server() -> None:
    initialized = False
    for line in sys.stdin:
        try:
            message = json.loads(line)
            method = message.get("method")
            if "id" not in message:
                if method == "notifications/initialized":
                    initialized = True
                continue
            response = {"jsonrpc": "2.0", "id": message["id"]}
            if method == "initialize":
                version = message.get("params", {}).get("protocolVersion", PROTOCOL_VERSION)
                response["result"] = {"protocolVersion": version if version == PROTOCOL_VERSION else PROTOCOL_VERSION,
                                      "capabilities": {"tools": {"listChanged": False}},
                                      "serverInfo": {"name": "ai-screen-grabby", "version": VERSION}}
            elif not initialized:
                response["error"] = {"code": -32000, "message": "Initialize first"}
            elif method == "tools/list":
                response["result"] = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params", {})
                try:
                    if params.get("name") == "list_windows":
                        result = {"content": [{"type": "text", "text": json.dumps(list_windows(), ensure_ascii=False)}], "isError": False}
                    elif params.get("name") == "set_output_directory":
                        result = {"content": [{"type": "text", "text": json.dumps(set_output_directory(params.get("arguments", {})["directory"]), ensure_ascii=False)}], "isError": False}
                    elif params.get("name") == "capture_window":
                        result = _mcp_capture(params.get("arguments", {}))
                    elif params.get("name") == "capture_window_by_title":
                        arguments = dict(params.get("arguments", {}))
                        target = resolve_window_title(arguments["title"], arguments.get("match", "contains"), arguments.get("pid"))
                        arguments.update(hwnd=target["hwnd"], pid=target["pid"])
                        result = _mcp_capture(arguments)
                    else:
                        raise ValueError("Unknown tool")
                except Exception as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                response["result"] = result
            else:
                response["error"] = {"code": -32601, "message": "Method not found"}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a selected Windows window to a local PNG")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="Open the local user interface")
    sub.add_parser("list", help="List visible windows as JSON")
    sub.add_parser("mcp", help="Run local MCP stdio server")
    settings = sub.add_parser("settings", help="Show or change the shared output directory")
    settings.add_argument("--output-directory")
    grab = sub.add_parser("capture", help="Capture a selected window")
    grab.add_argument("--hwnd", type=int, required=True)
    grab.add_argument("--pid", type=int, required=True)
    grab.add_argument("--output")
    grab.add_argument("--overwrite", action="store_true")
    by_title = sub.add_parser("capture-title", help="Capture a unique window by its title")
    by_title.add_argument("--title", required=True)
    by_title.add_argument("--match", choices=("exact", "contains"), default="contains")
    by_title.add_argument("--pid", type=int)
    by_title.add_argument("--output")
    by_title.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.command in (None, "gui"):
        from grabby_gui import GrabbyApp
        GrabbyApp().run()
        return 0
    if args.command == "mcp":
        mcp_server()
        return 0
    try:
        if args.command == "list":
            result = list_windows()
        elif args.command == "settings":
            result = set_output_directory(args.output_directory) if args.output_directory else load_settings()
        elif args.command == "capture-title":
            target = resolve_window_title(args.title, args.match, args.pid)
            result = capture(target["hwnd"], target["pid"], args.output or default_output_path(target["hwnd"]), args.overwrite)
        else:
            result = capture(args.hwnd, args.pid, args.output or default_output_path(args.hwnd), args.overwrite)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Ai_Screen_Grabby: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
