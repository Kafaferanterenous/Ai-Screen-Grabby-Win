"""Smoke-check the GUI pages and capture the synthetic settings layout."""

import json
from pathlib import Path

import grabby
from grabby_gui import GrabbyApp


app = GrabbyApp()
try:
    app.root.update()
    app.search.set("__no_matching_window__")
    app.root.update()
    if app.listbox.size() != 0:
        raise RuntimeError("Window filter did not apply")
    app.show("settings")
    app.root.update()
    targets = [w for w in grabby.list_windows() if w["title"] == "Ai Screen Grabby"]
    if len(targets) != 1:
        raise RuntimeError("Grabby GUI window was not found")
    target = targets[0]
    output = Path(__file__).parent / "captures" / "synthetic-settings-acceptance.png"
    result = grabby.capture(target["hwnd"], target["pid"], str(output), overwrite=True)
    print(json.dumps({"settings_page": "loaded", "filter": "passed", "screenshot": result["path"]}))
finally:
    app.root.destroy()
