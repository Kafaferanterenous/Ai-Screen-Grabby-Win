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
              "border": "#9ba8b9", "select": "#315e9d", "select_fg": "#ffffff"},
    "Dark": {"bg": "#202329", "fg": "#eceef3", "field": "#2c313b", "button": "#353c47",
             "border": "#697586", "select": "#5988ce", "select_fg": "#ffffff"},
    "Navy": {"bg": "#132137", "fg": "#e9f1fb", "field": "#1d304d", "button": "#294364",
             "border": "#7997b8", "select": "#527db6", "select_fg": "#ffffff"},
    "Darker Pastel": {"bg": "#292633", "fg": "#f1eaf4", "field": "#383345", "button": "#484053",
                      "border": "#b3a0bb", "select": "#806983", "select_fg": "#ffffff"},
}


class GrabbyApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ai Screen Grabby")
        self.root.geometry("760x520")
        self.root.minsize(620, 420)
        self.font = ("Consolas", 10)
        self.root.option_add("*Font", self.font)
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure(".", font=self.font)
        self.apply_theme(grabby.load_settings()["theme"])
        self.windows = []
        self.displayed = []
        self.last_capture = None
        self.status = tk.StringVar(value="Ready")

        nav = ttk.Frame(self.root, padding=10)
        nav.pack(fill="x")
        ttk.Button(nav, text="Capture", command=lambda: self.show("capture")).pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Settings", command=lambda: self.show("settings")).pack(side="left")

        self.content = ttk.Frame(self.root, padding=16)
        self.content.pack(fill="both", expand=True)
        ttk.Label(self.root, textvariable=self.status, padding=10).pack(fill="x")
        self.show("capture")

    def show(self, page):
        for child in self.content.winfo_children():
            child.destroy()
        self.apply_theme(grabby.load_settings()["theme"])
        if page == "settings":
            self.settings_page()
        else:
            self.capture_page()

    def apply_theme(self, name):
        colors = PALETTES[name]
        self.palette = colors
        self.root.configure(background=colors["bg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"], font=self.font)
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
        ttk.Label(self.content, text="Select a window, then save a PNG in the configured folder.").pack(anchor="w", pady=(4, 12))
        ttk.Label(self.content, text="Filter windows by title").pack(anchor="w", pady=(0, 4))
        self.search = tk.StringVar()
        ttk.Entry(self.content, textvariable=self.search).pack(fill="x", pady=(0, 8))
        self.search.trace_add("write", lambda *_: self.filter_windows())
        self.listbox = tk.Listbox(self.content, font=self.font, activestyle="dotbox",
                                  background=self.palette["field"], foreground=self.palette["fg"],
                                  selectbackground=self.palette["select"], selectforeground=self.palette["select_fg"],
                                  highlightbackground=self.palette["border"])
        self.listbox.pack(fill="both", expand=True)
        buttons = ttk.Frame(self.content)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Refresh windows", command=self.refresh).pack(side="left")
        ttk.Button(buttons, text="Capture selected", command=self.capture_selected).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open save folder", command=self.open_directory).pack(side="left")
        self.open_capture_button = ttk.Button(buttons, text="Open last PNG", command=self.open_last_capture)
        self.open_capture_button.pack(side="left", padx=(8, 0))
        if not self.last_capture:
            self.open_capture_button.state(["disabled"])
        ttk.Label(self.content, text="Minimized windows are briefly restored behind other windows, then minimized again. Some apps may return blank images.", wraplength=680).pack(anchor="w", pady=(10, 0))
        self.refresh()

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

    def capture_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Choose a window", "Select a window first.")
            return
        item = self.displayed[selection[0]]
        output = grabby.default_output_path(item["hwnd"])
        self.status.set("Capturing...")

        def worker():
            command = grabby.cli_command("capture", "--hwnd", str(item["hwnd"]),
                                         "--pid", str(item["pid"]), "--output", output)
            try:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
                if proc.returncode:
                    raise RuntimeError(proc.stderr.strip() or "Capture failed")
                result = json.loads(proc.stdout)
                self.root.after(0, lambda: self.capture_done(result["path"]))
            except subprocess.TimeoutExpired:
                if item["minimized"]:
                    try:
                        if grabby._window(item["hwnd"])["pid"] == item["pid"]:
                            grabby.user32.ShowWindow(item["hwnd"], 7)
                    except (ValueError, OSError):
                        pass
                self.root.after(0, lambda: messagebox.showerror("Capture failed", "The window did not respond within 10 seconds."))
                self.root.after(0, lambda: self.status.set("Capture timed out"))
            except Exception as exc:
                detail = str(exc)
                self.root.after(0, lambda: messagebox.showerror("Capture failed", detail))
                self.root.after(0, lambda: self.status.set("Capture failed"))

        threading.Thread(target=worker, daemon=True).start()

    def capture_done(self, path):
        self.last_capture = path
        if self.open_capture_button.winfo_exists():
            self.open_capture_button.state(["!disabled"])
        self.status.set(f"Saved: {path}")

    def open_directory(self):
        directory = Path(grabby.load_settings()["output_directory"])
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)

    def open_last_capture(self):
        if self.last_capture and Path(self.last_capture).is_file():
            os.startfile(self.last_capture)

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

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    GrabbyApp().run()
