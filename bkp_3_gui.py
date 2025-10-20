import tkinter as tk
from tkinter import ttk, scrolledtext

import config
import main


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("WiFi Monitor")
        self.minsize(width=1380, height=768)

        # Центрируем окно
        window_width = 1380
        window_height = 768

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Левая сторона окна
        left_frame = tk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Верхняя панель с правом верхним блоком
        top_frame = tk.Frame(left_frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # Status line поверх всей ширины окна
        self.status_label = tk.Label(top_frame, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Добавление правого блока с лейблом и кнопочной панелью
        right_top_frame = tk.Frame(top_frame)
        right_top_frame.pack(side=tk.RIGHT, anchor="ne")

        # Label состояния справа вверху
        self.state_label = tk.Label(right_top_frame, text="State: Ready", font=("Arial", 12))
        self.state_label.pack(pady=5)

        # Кнопочная панель внизу лейбла
        button_panel = tk.Frame(right_top_frame)
        button_panel.pack()

        buttons = ["Start Scanning", "Stop Scanning", "Reset Data",
                   "Export to CSV", "Open White List", "Show Details", "Help"]

        for btn_name in buttons:
            btn = tk.Button(button_panel, text=btn_name, command=lambda b=btn_name: self.on_button_click(b))
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Дерево (TreeView) с возможностью изменения размера
        tree_frame = tk.Frame(left_frame)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("#1", "#2", "#3")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)

        self.tree.heading('#1', text='Уникальный MAC', command=lambda: self.sort_column('#1'))
        self.tree.heading('#2', text='Count', command=lambda: self.sort_column('#2'))
        self.tree.heading('#3', text='Last Seen', command=lambda: self.sort_column('#3'))

        self.tree.column('#1', width=150)
        self.tree.column('#2', width=50)
        self.tree.column('#3', width=250)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_y.config(command=self.tree.yview)

        # Область для вывода подробностей
        bottom_frame = tk.Frame(left_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.text_area = scrolledtext.ScrolledText(bottom_frame, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)

    def on_button_click(self, button_name):
        print(f"Button '{button_name}' clicked.")
        # Реализуйте нужную логику здесь

    def sort_column(self, col):
        items = [(self.tree.set(child, col), child) for child in self.tree.get_children()]
        items.sort(reverse=False)
        for index, (_, child_id) in enumerate(items):
            self.tree.move(child_id, "", index)

    def update_tree(self, mac_address, count, last_seen):
        normalized_mac = ':'.join([mac_address[i:i + 2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if
                     self.tree.item(item)['values'][0] == normalized_mac), None)
        if item:
            self.tree.set(item, '#2', count)
            self.tree.set(item, '#3', last_seen)
        else:
            self.tree.insert("", tk.END, values=(normalized_mac, count, last_seen))

    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)

    def clear_text(self):
        self.text_area.delete('1.0', tk.END)

    def update_status(self, total_devices, devices_in_white_list):
        status_message = f"{config.interface}: {config.mode} mode | Found: {total_devices}, Whitelist: total {len(config._whitelist)} | Ignored {devices_in_white_list}"
        self.status_label.config(text=status_message)

