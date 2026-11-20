"""Small local GUI for Ai Screen Grabby."""

import json
import os
from pathlib import Path
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import grabby


PALETTES = {
    "Light": {"bg": "#f1f3f6", "fg": "#202632", "field": "#ffffff", "button": "#e2e7ee",
              "border": "#9ba8b9", "select": "#315e9d", "select_fg": "#ffffff", "accent": "#b4560b"},
    "Dark": {"bg": "#202329", "fg": "#eceef3", "field": "#2c313b", "button": "#353c47",
             "border": "#697586", "select": "#5988ce", "select_fg": "#ffffff", "accent": "#f0a85a"},
    "Navy": {"bg": "#132137", "fg": "#e9f1fb", "field": "#1d304d", "button": "#294364",
             "border": "#7997b8", "select": "#527db6", "select_fg": "#ffffff", "accent": "#ffc46b"},
    "Darker Pastel": {"bg": "#292633", "fg": "#f1eaf4", "field": "#383345", "button": "#484053",
                      "border": "#b3a0bb", "select": "#806983", "select_fg": "#ffffff", "accent": "#f2c48d"},
}

DELAYS = ("No delay", "3 seconds", "5 seconds", "10 seconds", "15 seconds", "30 seconds", "60 seconds")

# (keys, what it does) shown on the Help page; the bindings below must match.
SHORTCUTS = [
    ("F1", "Show this help"),
    ("Ctrl+1 / Ctrl+2 / Ctrl+3", "Capture page / Settings / Help"),
    ("Ctrl+F", "Jump to the window filter"),
    ("Up / Down", "Choose a window in the list"),
    ("Enter", "Capture the selected window (uses the delay setting)"),
    ("Ctrl+D", "Change the delay (none, 3, 5, 10, 15, 30, 60 s)"),
    ("Ctrl+T", "Toggle: window content only (no title bar)"),
    ("Esc", "Cancel a running countdown"),
    ("F5 or Ctrl+R", "Refresh the window list"),
    ("Ctrl+O", "Open the last screenshot"),
    ("Ctrl+E", "Open the save folder"),
    ("Ctrl+Q", "Exit Grabby"),
]


class GrabbyApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ai Screen Grabby")
        self.root.geometry("860x720")
        self.root.minsize(680, 520)
        self.font = ("Consolas", 10)
        self.root.option_add("*Font", self.font)
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure(".", font=self.font)
        self.apply_theme(grabby.load_settings()["theme"])
        self.windows = []
        self.displayed = []
        self.last_capture = None
        self.page = "capture"
        self.countdown_job = None
        self.status = tk.StringVar(value="Ready. Press F1 for help and shortcut keys.")
        self.delay_choice = tk.StringVar(value=DELAYS[0])
        self.client_only = tk.BooleanVar(value=False)

        nav = ttk.Frame(self.root, padding=10)
        nav.pack(fill="x")
        ttk.Button(nav, text="Capture", command=lambda: self.show("capture")).pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Settings", command=lambda: self.show("settings")).pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Help (F1)", command=lambda: self.show("help")).pack(side="left")
        ttk.Button(nav, text="Exit", command=self.exit_app).pack(side="right")

        self.content = ttk.Frame(self.root, padding=16)
        self.content.pack(fill="both", expand=True)
        ttk.Label(self.root, textvariable=self.status, padding=10).pack(fill="x")
        self.bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.show("capture")

    # ---------- keyboard ----------
    def bind_keys(self):
        r = self.root
        r.bind("<F1>", lambda e: self.show("help"))
        r.bind("<Control-Key-1>", lambda e: self.show("capture"))
        r.bind("<Control-Key-2>", lambda e: self.show("settings"))
        r.bind("<Control-Key-3>", lambda e: self.show("help"))
        r.bind("<Control-f>", lambda e: self.on_capture_page(self.focus_filter))
        r.bind("<Return>", lambda e: self.on_capture_page(self.capture_selected))
        r.bind("<Control-d>", lambda e: self.cycle_delay())
        r.bind("<Control-t>", lambda e: self.client_only.set(not self.client_only.get()))
        r.bind("<Escape>", lambda e: self.cancel_countdown())
        r.bind("<F5>", lambda e: self.on_capture_page(self.refresh))
        r.bind("<Control-r>", lambda e: self.on_capture_page(self.refresh))
        r.bind("<Control-o>", lambda e: self.open_last_capture())
        r.bind("<Control-e>", lambda e: self.open_directory())
        r.bind("<Control-q>", lambda e: self.exit_app())

    def on_capture_page(self, action):
        if self.page != "capture":
            self.show("capture")
        action()
        return "break"

    def focus_filter(self):
        if hasattr(self, "filter_entry") and self.filter_entry.winfo_exists():
            self.filter_entry.focus_set()

    def cycle_delay(self):
        i = DELAYS.index(self.delay_choice.get())
        self.delay_choice.set(DELAYS[(i + 1) % len(DELAYS)])
        self.status.set(f"Delay: {self.delay_choice.get()}")

    def delay_seconds(self):
        value = self.delay_choice.get().split()[0]
        return 0 if not value.isdigit() else int(value)

    # ---------- pages ----------
    def show(self, page):
        self.page = page
        for child in self.content.winfo_children():
            child.destroy()
        self.apply_theme(grabby.load_settings()["theme"])
        if page == "settings":
            self.settings_page()
        elif page == "help":
            self.help_page()
        else:
            self.capture_page()

    def apply_theme(self, name):
        colors = PALETTES[name]
        self.palette = colors
        self.root.configure(background=colors["bg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"], font=self.font)
        self.style.configure("Accent.TLabel", background=colors["bg"], foreground=colors["accent"],
                             font=("Consolas", 12, "bold"))
        self.style.configure("TButton", background=colors["button"], foreground=colors["fg"],
                             bordercolor=colors["border"], padding=6, font=self.font)
        self.style.map("TButton", background=[("active", colors["select"])],
                       foreground=[("active", colors["select_fg"])])
        self.style.configure("TEntry", fieldbackground=colors["field"], foreground=colors["fg"],
                             insertcolor=colors["fg"], bordercolor=colors["border"], font=self.font)
        self.style.configure("TCombobox", fieldbackground=colors["field"], background=colors["button"],
                             foreground=colors["fg"], arrowcolor=colors["fg"], font=self.font)
        self.style.map("TCombobox", fieldbackground=[("readonly", colors["field"])],
                       foreground=[("readonly", colors["fg"])])
        self.style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"], font=self.font)
        self.style.map("TCheckbutton", background=[("active", colors["bg"])],
                       foreground=[("active", colors["fg"])])
        if hasattr(self, "listbox") and self.listbox.winfo_exists():
            self.listbox.configure(background=colors["field"], foreground=colors["fg"],
                                   selectbackground=colors["select"], selectforeground=colors["select_fg"],
                                   highlightbackground=colors["border"])

    def capture_page(self):
        ttk.Label(self.content, text="Capture a window", font=("Consolas", 15, "bold")).pack(anchor="w")
        ttk.Label(self.content, text="Select a window, then press Enter or Capture selected. "
                                     "The PNG is saved in the configured folder.").pack(anchor="w", pady=(4, 12))
        ttk.Label(self.content, text="Filter windows by title (Ctrl+F)").pack(anchor="w", pady=(0, 4))
        self.search = tk.StringVar()
        self.filter_entry = ttk.Entry(self.content, textvariable=self.search)
        self.filter_entry.pack(fill="x", pady=(0, 8))
        self.search.trace_add("write", lambda *_: self.filter_windows())
        self.listbox = tk.Listbox(self.content, font=self.font, activestyle="dotbox", exportselection=False,
                                  background=self.palette["field"], foreground=self.palette["fg"],
                                  selectbackground=self.palette["select"], selectforeground=self.palette["select_fg"],
                                  highlightbackground=self.palette["border"])
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self.capture_selected())

        options = ttk.Frame(self.content)
        options.pack(fill="x", pady=(10, 0))
        ttk.Label(options, text="Delay (Ctrl+D):").pack(side="left")
        ttk.Combobox(options, textvariable=self.delay_choice, values=DELAYS, state="readonly",
                     width=12).pack(side="left", padx=(6, 18))
        ttk.Checkbutton(options, text="Window content only, no title bar (Ctrl+T)",
                        variable=self.client_only).pack(side="left")

        buttons = ttk.Frame(self.content)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Refresh windows (F5)", command=self.refresh).pack(side="left")
        self.capture_button = ttk.Button(buttons, text="Capture selected (Enter)", command=self.capture_selected)
        self.capture_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Open save folder", command=self.open_directory).pack(side="left")
        self.open_capture_button = ttk.Button(buttons, text="Open last PNG", command=self.open_last_capture)
        self.open_capture_button.pack(side="left", padx=(8, 0))
        if not self.last_capture:
            self.open_capture_button.state(["disabled"])
        self.countdown_label = ttk.Label(self.content, text="", style="Accent.TLabel")
        self.countdown_label.pack(anchor="w", pady=(10, 0))
        ttk.Label(self.content, text="Use a delay to capture a menu, a hover state or a later screen: "
                                     "start the timer, then set the window up. Esc cancels.",
                  wraplength=740).pack(anchor="w", pady=(4, 0))
        self.refresh()
        self.listbox.focus_set()

    def help_page(self):
        ttk.Label(self.content, text="Help", font=("Consolas", 15, "bold")).pack(anchor="w")
        ttk.Label(self.content, wraplength=760, text=(
            "Grabby saves a picture of ONE window you choose, even if it is covered by other windows. "
            "It never captures the whole screen and never uploads anything.")).pack(anchor="w", pady=(6, 10))
        ttk.Label(self.content, text="Shortcut keys", font=("Consolas", 12, "bold")).pack(anchor="w")
        table = ttk.Frame(self.content)
        table.pack(anchor="w", pady=(2, 8))
        for row, (keys, what) in enumerate(SHORTCUTS):
            ttk.Label(table, text=keys, style="Accent.TLabel", font=("Consolas", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 18), pady=1)
            ttk.Label(table, text=what).grid(row=row, column=1, sticky="w", pady=1)
        ttk.Label(self.content, text="Tips", font=("Consolas", 12, "bold")).pack(anchor="w")
        ttk.Label(self.content, wraplength=760, text=(
            "- Delay: choose a delay, press Enter, then open the menu or page you want; Grabby captures "
            "when the countdown ends.\n"
            "- If a picture comes out as one plain colour, the app is protected (e.g. video with DRM) or "
            "still loading: try again with a delay.\n"
            "- Minimised windows are restored behind other windows for a moment, then minimised again.")).pack(
            anchor="w", pady=(2, 12))
        ttk.Label(self.content, text="For AI tools", font=("Consolas", 12, "bold")).pack(anchor="w")
        ttk.Label(self.content, wraplength=760, text=(
            "Grabby.exe list | capture-title --title \"...\" [--delay 5] [--client] | mcp\n"
            "MCP tools: list_windows, capture_window, capture_window_by_title (delay_seconds, client_area, "
            "include_image), set_output_directory. Run Grabby.exe --help for examples.")).pack(anchor="w")

    # ---------- capture ----------
    def refresh(self):
        try:
            self.windows = grabby.list_windows()
            self.filter_windows()
            self.status.set(f"{len(self.windows)} windows found")
        except Exception as exc:
            self.windows = []
            self.status.set(str(exc))

    def filter_windows(self):
        query = self.search.get().casefold()
        self.displayed = [item for item in self.windows if query in item["title"].casefold()]
        self.listbox.delete(0, "end")
        for item in self.displayed:
            state = " [minimized]" if item["minimized"] else ""
            self.listbox.insert("end", f'{item["title"]}  (PID {item["pid"]}, HWND {item["hwnd"]}){state}')
        if self.displayed:
            self.listbox.selection_set(0)
            self.listbox.activate(0)

    def capture_selected(self):
        if self.countdown_job:
            return
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Choose a window", "Select a window first.")
            return
        item = self.displayed[selection[0]]
        self.countdown(item, self.delay_seconds())

    def countdown(self, item, remaining):
        if remaining <= 0:
            self.countdown_job = None
            self.set_countdown_text("")
            self.run_capture(item)
            return
        self.set_countdown_text(f"Capturing \"{item['title'][:50]}\" in {remaining} s   (Esc to cancel)")
        self.status.set(f"Countdown: {remaining} s")
        self.countdown_job = self.root.after(1000, lambda: self.countdown(item, remaining - 1))

    def set_countdown_text(self, text):
        if hasattr(self, "countdown_label") and self.countdown_label.winfo_exists():
            self.countdown_label.configure(text=text)

    def cancel_countdown(self):
        if self.countdown_job:
            self.root.after_cancel(self.countdown_job)
            self.countdown_job = None
            self.set_countdown_text("")
            self.status.set("Countdown cancelled")

    def run_capture(self, item):
        output = grabby.default_output_path(item["hwnd"])
        self.status.set("Capturing...")
        client = self.client_only.get()

        def worker():
            command = grabby.cli_command("capture", "--hwnd", str(item["hwnd"]),
                                         "--pid", str(item["pid"]), "--output", output)
            if client:
                command.append("--client")
            try:
                proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=15, check=False,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if proc.returncode:
                    raise RuntimeError(proc.stderr.strip() or "Capture failed")
                result = json.loads(proc.stdout)
                self.root.after(0, lambda: self.capture_done(result))
            except subprocess.TimeoutExpired:
                if item["minimized"]:
                    try:
                        if grabby._window(item["hwnd"])["pid"] == item["pid"]:
                            grabby.user32.ShowWindow(item["hwnd"], 7)
                    except (ValueError, OSError):
                        pass
                self.root.after(0, lambda: messagebox.showerror("Capture failed", "The window did not respond within 15 seconds."))
                self.root.after(0, lambda: self.status.set("Capture timed out"))
            except Exception as exc:
                detail = str(exc)
                self.root.after(0, lambda: messagebox.showerror("Capture failed", detail))
                self.root.after(0, lambda: self.status.set("Capture failed"))

        threading.Thread(target=worker, daemon=True).start()

    def capture_done(self, result):
        path = result["path"]
        self.last_capture = path
        if hasattr(self, "open_capture_button") and self.open_capture_button.winfo_exists():
            self.open_capture_button.state(["!disabled"])
        if result.get("blank"):
            self.status.set(f"Saved, but the picture is one plain colour (window could not be rendered): {path}")
        else:
            self.status.set(f"Saved {result['width']}x{result['height']}: {path}")

    def open_directory(self):
        directory = Path(grabby.load_settings()["output_directory"])
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)

    def open_last_capture(self):
        if self.last_capture and Path(self.last_capture).is_file():
            os.startfile(self.last_capture)

    # ---------- settings ----------
    def settings_page(self):
        ttk.Label(self.content, text="Settings", font=("Consolas", 15, "bold")).pack(anchor="w")
        ttk.Label(self.content, text="Save screenshots to").pack(anchor="w", pady=(20, 4))
        self.directory = tk.StringVar(value=grabby.load_settings()["output_directory"])
        row = ttk.Frame(self.content)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.directory).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left", padx=(8, 0))
        self.startup = tk.BooleanVar(value=grabby.startup_enabled())
        ttk.Checkbutton(self.content, text="Start with Windows", variable=self.startup).pack(anchor="w", pady=(22, 0))
        ttk.Label(self.content, text="Starts this window when you sign in to Windows.").pack(anchor="w", pady=(4, 18))
        ttk.Label(self.content, text="Appearance").pack(anchor="w", pady=(0, 4))
        self.theme_choice = tk.StringVar(value=grabby.load_settings()["theme"])
        chooser = ttk.Combobox(self.content, textvariable=self.theme_choice, values=grabby.THEMES,
                               state="readonly", width=19)
        chooser.pack(anchor="w", pady=(0, 6))
        chooser.bind("<<ComboboxSelected>>", lambda _: self.apply_theme(self.theme_choice.get()))
        ttk.Label(self.content, text="Choose Light, Dark, Navy, or Darker Pastel.").pack(anchor="w", pady=(0, 20))
        ttk.Button(self.content, text="Save settings", command=self.save_settings).pack(anchor="w")
        ttk.Label(self.content, text="AI access: register the local MCP command shown in README.md with your AI client.", wraplength=680).pack(anchor="w", pady=(30, 0))

    def browse(self):
        directory = filedialog.askdirectory(initialdir=self.directory.get() or str(Path.home()))
        if directory:
            self.directory.set(directory)

    def save_settings(self):
        try:
            grabby.save_settings(directory=self.directory.get(), theme=self.theme_choice.get())
            grabby.set_startup(self.startup.get())
            self.status.set("Settings saved")
        except Exception as exc:
            messagebox.showerror("Settings could not be saved", str(exc))

    def exit_app(self):
        self.cancel_countdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    grabby.enable_dpi_awareness()
    GrabbyApp().run()
