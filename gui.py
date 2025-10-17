

# gui.py
import tkinter as tk
from tkinter import ttk, scrolledtext


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("WiFi Monitor")
        self.geometry("800x700")

        # Панель сверху с таблицей и полосой прокрутки
        tree_frame = tk.Frame(self)
        tree_frame.pack(side=tk.TOP, fill=tk.X)

        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("#1", "#2", "#3")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)
        self.tree.heading('#1', text='MAC Address', command=lambda: self.sort_column('#1'))
        self.tree.heading('#2', text='Count', command=lambda: self.sort_column('#2'))
        self.tree.heading('#3', text='Last Seen', command=lambda: self.sort_column('#3'))
        self.tree.column('#1', width=150)
        self.tree.column('#2', width=50)
        self.tree.column('#3', width=250)
        self.tree.pack(side=tk.LEFT, fill=tk.X)
        scroll_y.config(command=self.tree.yview)

        # Область для вывода подробностей
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # Статусная панель снизу
        self.status_label = tk.Label(self, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def sort_column(self, col):
        items = [(self.tree.set(child, col), child) for child in self.tree.get_children()]
        items.sort(reverse=False)
        for index, (_, child_id) in enumerate(items):
            self.tree.move(child_id, "", index)

    def update_tree(self, mac_address, count, last_seen):
        """Обновляет дерево TreeView новыми данными."""
        normalized_mac = ':'.join([mac_address[i:i + 2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac),
                    None)
        if item:
            self.tree.set(item, '#2', count)
            self.tree.set(item, '#3', last_seen)
        else:
            self.tree.insert("", tk.END, values=(normalized_mac, count, last_seen))

    def add_text(self, text):
        """Добавляет текст в поле вывода"""
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)  # Прокручиваем вниз

    def clear_text(self):
        """Очищает содержимое поля вывода"""
        self.text_area.delete('1.0', tk.END)

    def update_status(self, total_devices, devices_in_white_list):
        """Обновляет статусную строку"""
        self.status_label.config(text=f"Found: {total_devices}, White List: {devices_in_white_list}")