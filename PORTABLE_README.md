# Ai Screen Grabby portable

This is experimental Windows software developed so both a human user and an AI assistant can capture a chosen window. **Use at your own risk.** Screenshots may contain private information. Review files before sharing them.

## For people

1. Extract the ZIP, keeping both EXE files in the same folder.
2. Double-click `GrabbyGUI.exe`.
3. In **Settings**, choose a save directory and Light, Dark, Navy, or Darker Pastel. Tick **Start with Windows** only if wanted, then choose **Save settings**.
4. In **Capture**, select a window, optionally filtering the list by title, then choose **Capture selected**.
5. Choose **Open last PNG** to inspect it or **Open save folder** to locate it.

The app uses a monospace font. `Screenshots\Grabby-Navy.png` shows the interface with synthetic window data.

The two EXE files must stay in the same folder. This is a local portable app for Windows 10/11; it needs an interactive desktop session and does not need Python installed. Settings are stored in `%APPDATA%\Ai_Screen_Grabby\settings.json`. If you move the folder after enabling Windows startup, open Settings and save it again so the startup command uses the new location.

## For AI tools

`Grabby.exe` provides local commands:

```powershell
.\Grabby.exe list
.\Grabby.exe settings --output-directory "C:\absolute\folder"
.\Grabby.exe capture --hwnd HANDLE --pid PID
.\Grabby.exe capture-title --title "part of window title"
.\Grabby.exe mcp
```

An AI client with local shell access can run the commands directly. To use MCP, register `Grabby.exe` as a local stdio server with `mcp` as its argument. No cloud connector or network listener is required by Grabby. MCP tools are `list_windows`, `set_output_directory`, `capture_window`, and `capture_window_by_title`. Title matching ignores case; if several windows match, Grabby refuses to guess and asks for an exact title, PID, or HWND. `output_path` is optional, and `include_image=true` also returns the PNG to the client. The client may transmit returned images according to its own policy.

For Codex CLI or its IDE extension, the registration command is:

```powershell
codex mcp add ai_screen_grabby -- "FULL_PATH_TO\Grabby.exe" mcp
codex mcp get ai_screen_grabby
```

Replace `FULL_PATH_TO` with the extracted folder. Restart the Codex client after registration. This changes Codex's local MCP configuration; the portable app itself does not change that configuration.

Grabby captures covered windows using Windows `PrintWindow`. A minimized window is briefly restored without taking focus, captured, then minimized again. Some GPU-rendered or protected apps can still return blank or incomplete images. Inspect the saved PNG before treating it as evidence.

Only a synthetic interface screenshot is included in this package. No user window captures are included. Grabby does not upload captures.

Source code and license terms are in the public Grabby repository. This package includes Grabby's license and third-party runtime notices.
