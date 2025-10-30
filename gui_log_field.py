import tkinter as tk
from tkinter.scrolledtext import ScrolledText


class LogField:
    def __init__(self, master):
        self.master = master
        self.text_area = None
        self.setup_log_field()

    def setup_log_field(self):
        # Текстовая область для логов
        self.text_area = ScrolledText(self.master, wrap=tk.NONE, height=6)
        self.text_area.pack(fill=tk.BOTH, expand=True)

    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)