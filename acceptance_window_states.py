"""Check synthetic visible and minimized capture on an interactive desktop."""

import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time
import zlib

import grabby


def distinct_colors(path):
    data = path.read_bytes()
    offset = 8
    compressed = bytearray()
    while offset < len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        if kind == b"IDAT":
            compressed.extend(data[offset + 8:offset + 8 + size])
        offset += size + 12
    pixels = zlib.decompress(compressed)
    return len(set(pixels))


here = Path(__file__).resolve().parent
demo = subprocess.Popen([sys.executable, str(here / "demo_window.py")])
cover = None
try:
    for _ in range(30):
        matches = [w for w in grabby.list_windows() if w["pid"] == demo.pid and w["title"] == "Ai Screen Grabby synthetic test"]
        if matches:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Synthetic window did not appear")
    target = matches[0]
    visible = here / "captures" / "synthetic-visible-acceptance.png"
    covered = here / "captures" / "synthetic-covered-acceptance.png"
    minimized = here / "captures" / "synthetic-minimized-acceptance.png"
    first = grabby.capture(target["hwnd"], demo.pid, str(visible), overwrite=True)
    cover = subprocess.Popen([sys.executable, "-c", "import tkinter as tk; r=tk.Tk(); r.title('Synthetic cover'); r.geometry('520x340+180+130'); r.attributes('-topmost', True); r.mainloop()"])
    for _ in range(30):
        covers = [w for w in grabby.list_windows() if w["pid"] == cover.pid and w["title"] == "Synthetic cover"]
        if covers:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Cover window did not appear")
    foreground = ctypes.windll.user32.GetForegroundWindow()
    hidden = grabby.capture(target["hwnd"], demo.pid, str(covered), overwrite=True)
    if ctypes.windll.user32.GetForegroundWindow() != foreground:
        raise RuntimeError("Foreground changed during covered capture")
    ctypes.windll.user32.ShowWindow(target["hwnd"], 6)
    time.sleep(0.4)
    state = grabby._window(target["hwnd"])
    if not state["minimized"]:
        raise RuntimeError("Window did not minimize")
    foreground_before = ctypes.windll.user32.GetForegroundWindow()
    try:
        grabby.capture(target["hwnd"], demo.pid, str(here / "missing-output-directory" / "test.png"))
    except ValueError:
        pass
    else:
        raise RuntimeError("Invalid output path was accepted")
    if not grabby._window(target["hwnd"])["minimized"]:
        raise RuntimeError("Invalid output path restored the window")
    second = grabby.capture(target["hwnd"], demo.pid, str(minimized), overwrite=True)
    foreground_after = ctypes.windll.user32.GetForegroundWindow()
    if foreground_before != foreground_after:
        raise RuntimeError("Foreground window changed during minimized capture")
    if not grabby._window(target["hwnd"])["minimized"]:
        raise RuntimeError("Window was not returned to minimized state")
    print(json.dumps({"visible": {"size": first["bytes"], "distinct_byte_values": distinct_colors(visible)},
                      "covered": {"size": hidden["bytes"], "distinct_byte_values": distinct_colors(covered), "foreground_unchanged": True},
                      "minimized": {"size": second["bytes"], "distinct_byte_values": distinct_colors(minimized),
                                    "temporarily_restored": second["temporarily_restored"], "foreground_unchanged": True}}))
finally:
    if cover is not None:
        cover.terminate()
        cover.wait(timeout=5)
    demo.terminate()
    demo.wait(timeout=5)
