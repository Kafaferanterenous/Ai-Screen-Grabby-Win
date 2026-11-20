# Ai Screen Grabby v0.6.0

## Fixed
- **Browser-based and GPU-rendered apps were captured as a blank image** (WebView2, Tauri, Electron, Chrome, Edge, VS Code, ...). Grabby now asks `PrintWindow` for full content (`PW_RENDERFULLCONTENT`) and falls back to the old method only if Windows refuses. The result JSON reports `"method": "full-content"` or `"legacy"`.

- **Crash when any window title contains an emoji** (or other characters outside the Windows code page): `Grabby.exe list`, the MCP server and the GUI capture printed JSON through the legacy code page ("charmap codec can't encode"). Output is now always UTF-8.

## New
- **Delay timer:** `--delay SECONDS` (CLI), `delay_seconds` (MCP), and a delay chooser with a visible countdown in the window (Esc cancels). Useful for menus, hover states, pages that are still loading, or screens that change on their own.
- **Content only:** `--client` (CLI), `client_area` (MCP), and a checkbox in the window, to capture without the title bar and borders.
- **Blank check:** `"blank": true` plus a plain-language warning when the picture is a single colour, so AI tools don't treat an empty picture as evidence.
- **Help page (F1)** listing all shortcut keys, tips, and the AI commands; **Exit** button.
- **Shortcut keys:** F1 help, Ctrl+1/2/3 pages, Ctrl+F filter, Enter capture, Ctrl+D delay, Ctrl+T content only, Esc cancel, F5/Ctrl+R refresh, Ctrl+O last PNG, Ctrl+E save folder, Ctrl+Q exit. Double-click a window to capture it.
- `Grabby.exe --help` shows examples for people and AI tools.

## Improved
- **DPI awareness** (per-monitor v2): sharp, uncropped captures on displays scaled to 125%/150%.
- **No invisible borders:** captures are trimmed to the visible window frame (DWM extended frame bounds), so there are no dark or transparent edges.
- **About 20× faster PNG encoding** on large windows (no per-pixel Python loop).
- Build script uses an explicit Python (`GRABBY_PYTHON`) and takes the version from the code.

## Unchanged by design
- Grabby still never captures the desktop or pixels from other windows, and never uploads anything.

## Notes
**Use at your own risk. This is experimental software.** A capture may contain private information. Inspect every image before sharing it.

13 automated checks passed. Live behaviour with every third-party app is unverified. Source is available under the MIT License; the portable ZIP includes the app license and third-party runtime notices.

Portable ZIP SHA-256: `83f3fa80a0da724e716b055555b705c697cb0406c638e389d814eef72ba8988b`
