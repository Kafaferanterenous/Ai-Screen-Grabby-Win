"""Capture sanitized app screenshots for the local README and public repository."""

import json
from pathlib import Path
import time

import grabby
from grabby_gui import GrabbyApp


here = Path(__file__).resolve().parent
assets = here / "assets"
assets.mkdir(exist_ok=True)
app = GrabbyApp()
try:
    app.root.update()
    app.windows = [{"hwnd": 1001, "pid": 1234, "title": "Synthetic demo window", "minimized": False}]
    app.filter_windows()
    app.status.set("Synthetic demo window ready")
    app.apply_theme("Navy")
    app.root.update()
    target = next(w for w in grabby.list_windows() if w["title"] == "Ai Screen Grabby")

    output = assets / "grabby-capture-navy.png"
    grabby.capture(target["hwnd"], target["pid"], str(output), overwrite=True)

    app.show("settings")
    app.directory.set(r"C:\Screenshots")
    app.startup.set(False)
    outputs = [str(output)]
    for theme, filename in (("Dark", "grabby-settings-dark.png"),
                            ("Navy", "grabby-settings-navy.png"),
                            ("Darker Pastel", "grabby-settings-darker-pastel.png")):
        app.theme_choice.set(theme)
        app.apply_theme(theme)
        app.root.update()
        time.sleep(0.1)
        output = assets / filename
        grabby.capture(target["hwnd"], target["pid"], str(output), overwrite=True)
        outputs.append(str(output))
    print(json.dumps({"screenshots": outputs}))
finally:
    app.root.destroy()
