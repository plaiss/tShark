import tkinter as tk
from tkinter import ttk, scrolledtext

import config
import main


class App(tk.Tk):
    def __init__(self):  # Исправлено на __init__
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

        # Панель сверху с таблицей и полосой прокрутки
        tree_frame = tk.Frame(self)
        tree_frame.pack(side=tk.TOP, fill=tk.X)

        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("#1", "#2", "#3")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set, height=20)

        self.tree.heading('#1', text='Уникальный MAC', command=lambda: self.sort_column('#1'))
        self.tree.heading('#2', text='Count', command=lambda: self.sort_column('#2'))
        self.tree.heading('#3', text='Last Seen', command=lambda: self.sort_column('#3'))

        self.tree.column('#1', width=150)
        self.tree.column('#2', width=50)
        self.tree.column('#3', width=250)

        self.tree.pack(side=tk.LEFT, fill=tk.X)

        scroll_y.config(command=self.tree.yview)

        # Область для вывода подробностей
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.NONE, height=20)
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
        item = next((item for item in self.tree.get_children() if
                     self.tree.item(item)['values'][0] == normalized_mac), None)
        if item:
            # Если элемент найден - обновляем его значения
            self.tree.set(item, '#2', count)
            self.tree.set(item, '#3', last_seen)
        else:
            # Если элемент не найден - добавляем новый элемент в TreeView
            self.tree.insert("", tk.END,
                             values=(normalized_mac,
                                     count,
                                     last_seen))

    def add_text(self, text):
        """Добавляет текст в поле вывода"""
        # Вставляем текст в конец ScrolledText поля и прокручиваем вниз.
        self.text_area.insert(tk.END, text + "\n")
        # Прокручиваем вниз.
        self.text_area.yview_moveto(1.0)

    def clear_text(self):
        """Очищает содержимое поля вывода"""
        # Удаляем весь текст из ScrolledText поля.
        self.text_area.delete('1.0', tk.END)

    def update_status(self, total_devices, devices_in_white_list):
        """Обновляет статусную строку"""
        # Обновляем текст статусной строки с информацией о количестве устройств и белом списке.
        status_message = f"{config.interface} : {config.mode} mode| Found: {total_devices}, Whitelist: total {len(config._whitelist)} | ignored {devices_in_white_list}"
        self.status_label.config(text=status_message)