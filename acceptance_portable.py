"""Check portable GUI and MCP capture with synthetic local content only."""

import base64
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time

import grabby


here = Path(__file__).resolve().parent
package = here / "portable_app"
cli = package / "Grabby.exe"
gui_exe = package / "GrabbyGUI.exe"
assert cli.is_file() and gui_exe.is_file()
known_gui_handles = {w["hwnd"] for w in grabby.list_windows() if w["title"] == "Ai Screen Grabby"}
demo = subprocess.Popen([sys.executable, str(here / "demo_window.py")])
gui = None
gui_handle = None
try:
    for _ in range(50):
        matches = [w for w in grabby.list_windows() if w["pid"] == demo.pid and w["title"] == "Ai Screen Grabby synthetic test"]
        if matches:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Synthetic target did not appear")
    target = matches[0]

    gui = subprocess.Popen([str(gui_exe)])
    for _ in range(75):
        matches = [w for w in grabby.list_windows() if w["title"] == "Ai Screen Grabby" and w["hwnd"] not in known_gui_handles]
        if matches:
            gui_handle = matches[0]["hwnd"]
            break
        time.sleep(0.2)
    if gui_handle is None:
        raise RuntimeError("Portable GUI did not open")

    ctypes.windll.user32.ShowWindow(target["hwnd"], 6)
    time.sleep(0.2)
    if not grabby._window(target["hwnd"])["minimized"]:
        raise RuntimeError("Synthetic target did not minimize")

    output = here / "captures" / "synthetic-portable-mcp.png"
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": grabby.PROTOCOL_VERSION}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "capture_window_by_title", "arguments": {"title": "Ai Screen Grabby synthetic test",
                                                            "match": "exact", "pid": target["pid"],
                                                            "output_path": str(output), "overwrite": True,
                                                            "include_image": True}}},
    ]
    proc = subprocess.run([str(cli), "mcp"], input="\n".join(json.dumps(r) for r in requests) + "\n",
                          text=True, capture_output=True, timeout=40)
    if proc.returncode:
        raise RuntimeError(proc.stderr or f"MCP exit {proc.returncode}")
    responses = [json.loads(line) for line in proc.stdout.splitlines()]
    names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    if names != {"list_windows", "set_output_directory", "capture_window", "capture_window_by_title"}:
        raise RuntimeError(f"MCP tools mismatch: {names}")
    result = responses[2]["result"]
    if result["isError"]:
        raise RuntimeError(result["content"][0]["text"])
    info = json.loads(result["content"][0]["text"])
    if not info["temporarily_restored"] or not grabby._window(target["hwnd"])["minimized"]:
        raise RuntimeError("Portable minimized capture did not restore target state")
    png = output.read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n" or base64.b64decode(result["content"][1]["data"]) != png:
        raise RuntimeError("MCP image differs from saved PNG")
    cli_output = here / "captures" / "synthetic-portable-title-cli.png"
    cli_result = subprocess.run([str(cli), "capture-title", "--title", "Ai Screen Grabby synthetic test",
                                 "--match", "exact", "--pid", str(target["pid"]),
                                 "--output", str(cli_output), "--overwrite"],
                                capture_output=True, text=True, timeout=30)
    if cli_result.returncode:
        raise RuntimeError(cli_result.stderr or "Portable title CLI failed")
    if not cli_output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Portable title CLI did not save a PNG")
    print(json.dumps({"portable_gui": "opened", "portable_mcp": "passed", "portable_title_cli": "passed", "png_bytes": len(png),
                      "width": info["width"], "height": info["height"]}))
finally:
    if gui_handle is not None:
        ctypes.windll.user32.PostMessageW(gui_handle, 0x0010, 0, 0)  # WM_CLOSE
    if gui is not None:
        try:
            gui.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gui.terminate()
            gui.wait(timeout=5)
    demo.terminate()
    demo.wait(timeout=5)
