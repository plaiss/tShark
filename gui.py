import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog

import config
import main
import utils


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Инициализация окна
        self.title("WiFi Monitor")
        self.minsize(width=1380, height=768)
        self.center_window()  # Используем общедоступный метод класса

        # Общие настройки окон и панелей
        # container = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        container = tk.PanedWindow(self, orient=tk.VERTICAL)

        # Объявляем основные фреймы верхнего уровня ДО установки позиции разделительной полосы
        upper_frame = tk.Frame(container)
        lower_frame = tk.Frame(container)
        container.add(upper_frame)
        container.add(lower_frame)

        # Упаковка контейнера и установка позиции разделительной полосы
        container.pack(fill=tk.BOTH, expand=True)
        container.sash_place(0, 0, 2)  # Двухуровневое деление окна

        # Заголовок верхней панели
        title_label = tk.Label(upper_frame, text="Обнаруженные уникальные адреса", font=("TkDefaultFont", 10, 'bold'))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Панель с кнопками и лейблами сверху
        top_frame = tk.Frame(upper_frame)
        top_frame.pack(side=tk.RIGHT, fill=tk.X)

        # Создание дерева с устройствами
        tree_frame = tk.Frame(upper_frame)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("#1", "#2", "#3", "#4")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)

        # Центрирование содержимого столбцов
        self.tree.heading('#1', text='MAC Address', anchor='center')
        self.tree.heading('#2', text='Vendor', anchor='center')
        self.tree.heading('#3', text='RSSI', anchor='center')
        self.tree.heading('#4', text='Last Seen', anchor='center')

        # Установка ширины столбцов
        self.tree.column('#1', width=150, minwidth=90, stretch=False)
        self.tree.column('#2', width=150, minwidth=90, stretch=False)
        self.tree.column('#3', width=40, minwidth=10, stretch=False)
        self.tree.column('#4', width=300, minwidth=90, stretch=False)

        self.tree.bind("<Double-1>", self.on_device_double_click)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_y.config(command=self.tree.yview)

        # Текстовая область для вывода журнала и уведомлений
        self.text_area = scrolledtext.ScrolledText(lower_frame, wrap=tk.NONE, height=6)  # Высота в 6 строк
        self.text_area.pack(fill=tk.BOTH)
        # self.text_area.pack(fill=tk.BOTH, expand=True)

        # Методы добавления и очистки текста
        def add_text(self, text):
            self.text_area.insert(tk.END, text + "\n")
            self.text_area.yview_moveto(1.0)

        def clear_text(self):
            self.text_area.delete('1.0', tk.END)

        # Полоса статуса с динамическим сообщением
        self.status_label = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, font=("TkDefaultFont", 10))  # Высота в одну строку
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Обновляем строку статуса
        def update_status(self, total_devices, devices_in_white_list):
            status_message = f"{config.interface}: {config.mode} mode | Found: {total_devices}, Whitelist: total {len(config._whitelist)} | Ignored {devices_in_white_list}"
            self.status_label.delete('1.0', tk.END)
            self.status_label.insert(tk.END, status_message)

            if config.mode != 'Monitor':
                self.status_label.tag_add("red", '1.6', '1.20')  # Выделяем красным название текущего режима
                self.status_label.tag_config("red", foreground="red")
                self.status_label.config(state=tk.DISABLED)

        # Обработчик нажатия кнопок
        def on_button_click(self, button_name):
            if button_name == 'Start Scanning':
                pass
            elif button_name == 'Stop Scanning':
                pass
            elif button_name == 'Monitor':
                password = simpledialog.askstring("Ввод пароля", "Введите пароль sudo:", show="*")
                if password is not None and len(password.strip()) > 0:
                    success = utils.enable_monitor_mode(config.interface, password)
                else:
                    print("Операция отменена.")

                update_status(0, 0)
            elif button_name == 'Export to CSV':
                pass
            elif button_name == 'Open White List':
                pass
            elif button_name == 'Show Details':
                pass
            elif button_name == '2name':
                self.open_second_window()
                print(f"Button '{button_name}' clicked.")

        # Кнопочная панель
        button_panel = tk.Frame(top_frame)
        button_panel.pack()

        buttons = [
            "Start Scanning", "Monitor", "Reset Data",
            "Export to CSV", "Open White List", "Show Details", "2name"
        ]

        for btn_name in buttons:
            btn = tk.Button(button_panel, text=btn_name, command=lambda b=btn_name: on_button_click(b))
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Кнопка для открытия второго окна
        open_second_window_btn = tk.Button(self, text="Открыть второе окно", command=self.open_second_window)
        open_second_window_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Общедоступный метод для добавления текста
    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)

    # Общедоступный метод для очистки текста
    def clear_text(self):
        self.text_area.delete('1.0', tk.END)

    # Общедоступный метод для обновления дерева
    def update_tree(self, mac_address, vendor, rssi, last_seen):
        normalized_mac = ':'.join([mac_address[i:i + 2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac),
                    None)
        if item:
            self.tree.set(item, '#2', vendor)
            self.tree.set(item, '#3', rssi)
            self.tree.set(item, '#4', last_seen)
        else:
            self.tree.insert("", tk.END, values=(normalized_mac, vendor, rssi, last_seen))

    # Общедоступный метод сортировки столбцов
    def sort_column(self, column_id):
        items = list(self.tree.get_children())
        try:
            # Сортируем числа или строки соответственно
            items.sort(key=lambda x: int(float(self.tree.set(x, column_id))) if column_id == '#3' else str.lower(
                self.tree.set(x, column_id)))
        except ValueError:
            # Если значение не число, сортируем как строки
            items.sort(key=lambda x: str.lower(self.tree.set(x, column_id)))

        # Применяем новую сортировку
        for i, item in enumerate(items):
            self.tree.move(item, "", i)

    # Общедоступный метод для открытия нового окна
    def open_second_window(self, data=None):
        SecondWindow(self, data=data)

    # Общедоступный метод обработки двойного щелчка мыши
    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]
        if data:
            self.open_second_window(data=data)

    # Общедоступный метод обновления статуса
    def update_status(self, total_devices, devices_in_white_list):
        status_message = f"{config.interface}: {config.mode} mode | Found: {total_devices}, Whitelist: total {len(config._whitelist)} | Ignored {devices_in_white_list}"
        self.status_label.delete('1.0', tk.END)
        self.status_label.insert(tk.END, status_message)

        if config.mode != 'Monitor':
            self.status_label.tag_add("red", '1.6', '1.20')  # Выделяем красным название текущего режима
            self.status_label.tag_config("red", foreground="red")
            self.status_label.config(state=tk.DISABLED)

    # Центрировка окна вынесена в отдельный общедоступный метод класса
    def center_window(self):
        """Метод центрирует главное окно"""
        window_width = 1380
        window_height = 768
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")


class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.title("Детали устройства")
        self.geometry("640x480")

        if data is not None:
            details = f"MAC: {data[0]} | {utils.lookup_vendor_db(data[0], config.DB_PATH, False)}  Count: {data[1]} Last Seen: {data[2]}"
            label = tk.Label(self, text=details)
            label.pack(pady=20)
        else:
            label = tk.Label(self, text="Нет доступной информации")
            label.pack(pady=20)

        close_btn = tk.Button(self, text="Закрыть", command=self.destroy)
        close_btn.pack(pady=10)