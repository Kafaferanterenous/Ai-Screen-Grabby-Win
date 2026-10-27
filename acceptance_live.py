"""Run an MCP round trip against the synthetic demo window on this desktop."""

import base64
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
server = subprocess.Popen([sys.executable, str(HERE / "grabby.py"), "mcp"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, bufsize=1)


def request(message):
    server.stdin.write(json.dumps(message) + "\n")
    server.stdin.flush()
    if "id" in message:
        return json.loads(server.stdout.readline())


try:
    init = request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "grabby-acceptance", "version": "1"}}})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listed = request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "list_windows", "arguments": {}}})
    windows = json.loads(listed["result"]["content"][0]["text"])
    matches = [w for w in windows if w["title"] == "Ai Screen Grabby synthetic test"]
    assert len(matches) == 1, f"Expected one synthetic window, found {len(matches)}"
    target = matches[0]
    output = HERE / "captures" / "synthetic-mcp.png"
    captured = request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "capture_window", "arguments": {"hwnd": target["hwnd"], "pid": target["pid"],
        "output_path": str(output), "overwrite": True, "include_image": True}}})
    result = captured["result"]
    assert not result["isError"], result
    info = json.loads(result["content"][0]["text"])
    image = result["content"][1]
    assert image["mimeType"] == "image/png"
    assert base64.b64decode(image["data"]) == output.read_bytes()
    print(json.dumps({"mcp": "passed", "path": info["path"],
                      "width": info["width"], "height": info["height"], "sha256": info["sha256"]}))
finally:
    server.stdin.close()
    server.wait(timeout=15)
