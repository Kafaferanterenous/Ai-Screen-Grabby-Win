# Ai Screen Grabby v0.5.0

**Use at your own risk. This is experimental software.** A capture may contain private information. Inspect every image before sharing it.

Ai Screen Grabby was developed for both human users and AI assistants. It saves a chosen Windows window as a local PNG. The portable ZIP contains the user interface (`GrabbyGUI.exe`) and the CLI/MCP tool (`Grabby.exe`). It requires Windows 10/11 and an interactive desktop session; Python is not required for the portable build.

## How to use it

1. Download and extract `Ai-Screen-Grabby-v0.5.0-portable.zip`.
2. Double-click `GrabbyGUI.exe`.
3. In **Settings**, choose a save folder and one of Light, Dark, Navy, or Darker Pastel. Save the settings. **Start with Windows** is optional.
4. In **Capture**, select a window and choose **Capture selected**. Open the last PNG to inspect it.

An AI assistant with local shell access can use `Grabby.exe list`, `Grabby.exe capture-title --title "part of title"`, or the other commands in the included README. An MCP client can register `Grabby.exe mcp` as a local stdio server. The AI can set the shared save directory and request a specific window by handle/PID or unique title. Grabby does not open a network listener or upload captures. Clients that request `include_image=true` may transmit the returned image under their own policies.

## Screenshots

The repository README shows real Grabby interface captures using synthetic window data. One sanitized Navy screenshot is also included in the ZIP.

![Navy Grabby Capture page](https://raw.githubusercontent.com/Kafaferanterenous/Ai-Screen-Grabby-Win/main/assets/grabby-capture-navy.png)

## Known limits and validation

Grabby uses Windows `PrintWindow`. It can capture a covered window. It briefly restores a minimized window without activating it, captures it, then minimizes it again. Some GPU-rendered and protected windows can still produce blank or incomplete images.

Five automated checks passed. The GUI, settings themes, title-based targeting, and portable MCP/CLI capture were checked locally with synthetic windows. Live behavior with every third-party app is unverified.

Grabby source is available under the MIT License. The portable ZIP includes the app license and third-party runtime notices.
