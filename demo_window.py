"""Synthetic window for capture testing; contains no user data."""

import tkinter as tk


root = tk.Tk()
root.title("Ai Screen Grabby synthetic test")
root.geometry("480x260+200+150")
root.configure(bg="#17324d")
canvas = tk.Canvas(root, width=480, height=260, highlightthickness=0, bg="#17324d")
canvas.pack(fill="both", expand=True)
canvas.create_rectangle(30, 35, 450, 225, fill="#e6f4ff", outline="#ffc857", width=6)
canvas.create_text(240, 102, text="AI SCREEN GRABBY", fill="#17324d", font=("Arial", 22, "bold"))
canvas.create_text(240, 160, text="SYNTHETIC CAPTURE TEST", fill="#146f59", font=("Arial", 14))
root.mainloop()
