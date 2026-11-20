import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import grabby


class PngTests(unittest.TestCase):
    def test_png_header_and_dimensions(self):
        png = grabby._png(2, 1, bytes([0, 0, 255, 0, 0, 255, 0, 0]))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack("!II", png[16:24]), (2, 1))
        self.assertIn(b"IEND", png)


class SettingsTests(unittest.TestCase):
    def test_output_directory_is_shared_and_absolute(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            settings = Path(temporary) / "settings.json"
            target = Path(temporary) / "captures"
            with mock.patch.object(grabby, "SETTINGS_PATH", settings):
                self.assertEqual(grabby.set_output_directory(str(target))["output_directory"], str(target))
                self.assertTrue(target.is_dir())
                self.assertEqual(Path(grabby.default_output_path(123)).parent, target)
                self.assertEqual(grabby.load_settings()["theme"], "Light")
                grabby.save_settings(theme="Navy")
                self.assertEqual(grabby.load_settings()["theme"], "Navy")
                grabby.set_output_directory(str(target))
                self.assertEqual(grabby.load_settings()["theme"], "Navy")
                with self.assertRaises(ValueError):
                    grabby.save_settings(theme="Neon")
                with self.assertRaises(ValueError):
                    grabby.set_output_directory("relative-folder")


class WindowTitleTests(unittest.TestCase):
    def test_unique_match_and_ambiguity_guard(self):
        windows = [
            {"hwnd": 10, "pid": 100, "title": "Untitled - Notes"},
            {"hwnd": 20, "pid": 200, "title": "Work Notes"},
        ]
        with mock.patch.object(grabby, "list_windows", return_value=windows):
            self.assertEqual(grabby.resolve_window_title("untitled", "contains")["hwnd"], 10)
            self.assertEqual(grabby.resolve_window_title("WORK NOTES", "exact")["hwnd"], 20)
            self.assertEqual(grabby.resolve_window_title("notes", pid=200)["hwnd"], 20)
            with self.assertRaisesRegex(ValueError, "Several windows match"):
                grabby.resolve_window_title("notes")
            with self.assertRaisesRegex(ValueError, "No window matches"):
                grabby.resolve_window_title("spreadsheet")
            with self.assertRaises(ValueError):
                grabby.resolve_window_title(" ")


class McpTests(unittest.TestCase):
    def test_initialize_list_and_reject_invalid_capture(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": grabby.PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "capture_window", "arguments": {"hwnd": 0, "pid": 0,
                "output_path": str(Path(__file__).parent / "captures" / "invalid.png")}}},
        ]
        proc = subprocess.run([sys.executable, str(Path(grabby.__file__)), "mcp"],
                              input="\n".join(json.dumps(r) for r in requests) + "\n",
                              text=True, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        results = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["result"]["protocolVersion"], grabby.PROTOCOL_VERSION)
        self.assertEqual({t["name"] for t in results[1]["result"]["tools"]},
                         {"list_windows", "capture_window", "capture_window_by_title", "set_output_directory"})
        self.assertTrue(results[2]["result"]["isError"])

    def test_ai_can_set_shared_output_directory(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            env = os.environ.copy()
            env["APPDATA"] = temporary
            target = Path(temporary) / "ai-captures"
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": grabby.PROTOCOL_VERSION}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                    "name": "set_output_directory", "arguments": {"directory": str(target)}}},
            ]
            proc = subprocess.run([sys.executable, str(Path(grabby.__file__)), "mcp"],
                                  input="\n".join(json.dumps(r) for r in requests) + "\n",
                                  text=True, capture_output=True, timeout=15, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout.splitlines()[-1])["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(json.loads(result["content"][0]["text"])["output_directory"], str(target))
            self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()


class V060Tests(unittest.TestCase):
    """Tests for the 0.6.0 additions (full-content capture helpers, delay, MCP schema)."""

    def test_png_matches_reference_encoder(self):
        # 3x2 BGRA image; compare the fast encoder against a straightforward one.
        bgra = bytes(range(24))
        rows = bytearray()
        for y in range(2):
            rows.append(0)
            for x in range(3):
                b, g, r = bgra[(y * 3 + x) * 4:(y * 3 + x) * 4 + 3]
                rows.extend((r, g, b))
        import zlib
        png = grabby._png(3, 2, bgra)
        idat_len = struct.unpack("!I", png[33:37])[0]
        self.assertEqual(zlib.decompress(png[41:41 + idat_len]), bytes(rows))

    def test_crop(self):
        px = lambda v: bytes((v, v, v, 255))
        img = b"".join(px(y * 10 + x) for y in range(3) for x in range(4))  # 4x3
        out = grabby._crop(img, 4, 3, 1, 1, 3, 3)
        self.assertEqual(out, px(11) + px(12) + px(21) + px(22))
        self.assertEqual(grabby._crop(img, 4, 3, 0, 0, 4, 3), img)
        with self.assertRaises(ValueError):
            grabby._crop(img, 4, 3, 0, 0, 5, 3)

    def test_blank_detection(self):
        white = bytes((255, 255, 255, 0)) * 100
        self.assertTrue(grabby._is_blank(white, 10, 10))
        dot = bytearray(white)
        dot[40:43] = b"\x00\x00\x00"
        self.assertFalse(grabby._is_blank(bytes(dot), 10, 10))

    def test_delay_bounds(self):
        grabby.wait_with_countdown(0)
        with self.assertRaises(ValueError):
            grabby.wait_with_countdown(-1)
        with self.assertRaises(ValueError):
            grabby.wait_with_countdown(grabby.MAX_DELAY_SECONDS + 1)

    def test_mcp_tools_offer_delay_and_client_area(self):
        for name in ("capture_window", "capture_window_by_title"):
            tool = next(t for t in grabby.TOOLS if t["name"] == name)
            props = tool["inputSchema"]["properties"]
            self.assertIn("delay_seconds", props)
            self.assertIn("client_area", props)

    def test_gui_help_lists_every_bound_shortcut(self):
        import grabby_gui
        keys = " ".join(k for k, _ in grabby_gui.SHORTCUTS)
        for needed in ("F1", "Ctrl+D", "Ctrl+T", "Esc", "Ctrl+Q", "Enter"):
            self.assertIn(needed, keys)


class UnicodeOutputTests(unittest.TestCase):
    def test_emoji_titles_survive_a_legacy_code_page_pipe(self):
        import io
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252")
        grabby.utf8_stdio(stream)
        print(json.dumps([{"title": "Family \U0001f3e1 photos"}], ensure_ascii=False), file=stream)
        stream.flush()
        self.assertIn("\U0001f3e1", json.loads(raw.getvalue().decode("utf-8"))[0]["title"])

    def test_cli_list_output_is_utf8_json(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        proc = subprocess.run([sys.executable, str(Path(grabby.__file__)), "list"], capture_output=True,
                              env=env, timeout=30, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIsInstance(json.loads(proc.stdout.decode("utf-8")), list)
