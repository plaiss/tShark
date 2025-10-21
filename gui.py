import tkinter as tk
from pickle import FALSE
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog

import config
import main
import utils


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

        # Главная контейнерная сетка
        container = tk.PanedWindow(self, orient=tk.VERTICAL)
        container.pack(fill=tk.BOTH, expand=True)

        # Верхняя секция с деревом
        upper_frame = tk.Frame(container)
        container.add(upper_frame)

        # Верхняя панель с статусом и правой стороной
        top_frame = tk.Frame(upper_frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # Status line
        self.status_label = tk.Text(self, bd=0, relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Title для TreeView
        title_label = tk.Label(top_frame, text="Devices Detected:", font=("Arial", 14, 'bold'))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Правый блок с лейблом и кнопками
        right_top_frame = tk.Frame(top_frame)
        right_top_frame.pack(side=tk.RIGHT, anchor="ne")

        # Label состояния справа вверху
        self.state_label = tk.Label(right_top_frame, text="State: Ready", font=("Arial", 12))
        self.state_label.pack(pady=5)

        # Кнопка для открытия второго окна
        open_second_window_btn = tk.Button(self, text="Открыть второе окно", command=self.open_second_window)
        open_second_window_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Кнопочная панель внизу лейбла
        button_panel = tk.Frame(right_top_frame)
        button_panel.pack()

        buttons = ["Start Scanning", "Monitor", "Reset Data",
                  "Export to CSV", "Open White List", "Show Details", "2name"]

        for btn_name in buttons:
            btn = tk.Button(button_panel, text=btn_name, command=lambda b=btn_name: self.on_button_click(b))
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Дерево с устройством (TreeView)
        tree_frame = tk.Frame(upper_frame)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("#1", "#2", "#3", "#4", "#5")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)

        self.tree.heading('#1', text='MAC Address')
        self.tree.heading('#2', text='Vendor')
        self.tree.heading('#3', text='RSSI')
        self.tree.heading('#4', text='Last Seen')
        self.tree.heading('#5', text='Last Seen')

        self.tree.column('#1', width=150)
        self.tree.column('#2', width=50)
        self.tree.column('#3', width=250)
        self.tree.column('#4', width=50)
        self.tree.column('#5', width=50)

        self.tree.bind("<Double-1>", self.on_double_click)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_y.config(command=self.tree.yview)

        # Нижняя секция с текстом
        lower_frame = tk.Frame(container)
        container.add(lower_frame)

        # Текстовая область
        self.text_area = scrolledtext.ScrolledText(lower_frame, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)

    def open_second_window(self, data=None):
        SecondWindow(self, data=data)

    def on_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]
        if data:
            self.open_second_window(data=data)

    def sort_column(self, col):
        sorted_items = sorted(self.tree.get_children(), key=lambda x: float(self.tree.set(x, col)) if col == '#2' else self.tree.set(x, col))
        for idx, item in enumerate(sorted_items):
            self.tree.move(item, '', idx)

    def update_tree(self, mac_address, vendor, rssi, last_seen):
        normalized_mac = ':'.join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac), None)
        if item:
            self.tree.set(item, '#2', vendor)
            self.tree.set(item, '#2', rssi)
            self.tree.set(item, '#3', last_seen)
        else:
            self.tree.insert("", tk.END, values=(normalized_mac, vendor, rssi, last_seen))

    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)

    def clear_text(self):
        self.text_area.delete('1.0', tk.END)

    def update_status(self, total_devices, devices_in_white_list):
        status_message = f"{config.interface}: {config.mode} mode | Found: {total_devices}, Whitelist: total {len(config._whitelist)} | Ignored {devices_in_white_list}"
        self.status_label.delete('1.0', tk.END)
        self.status_label.insert(tk.END, status_message)

        if config.mode != ('Monitor'):
            # Создаем тег для выделения
            self.status_label.tag_add("red", '1.6', '1.20')
            # Настраиваем цвет тега
            self.status_label.tag_config("red", foreground="red")
            self.status_label.config(state=tk.DISABLED)  # Делаем текст недоступным для редактирования

    def on_button_click(self, button_name):
        if button_name == 'Start Scanning':
            print(f"Button '{button_name}' clicked.")
        elif button_name == 'Stop Scanning':
            print(f"Button '{button_name}' clicked.")
        elif button_name == 'Monitor':
            # Запускаем окно для ввода пароля
            root = tk.Tk()
            root.withdraw()  # Скрываем основное окно Tkinter

            # Диалоговое окно для ввода пароля
            password = simpledialog.askstring("Ввод пароля", "Введите пароль sudo:", show="*")

            if password is not None and len(password.strip()) > 0:
                success = utils.enable_monitor_mode(config.interface, password)
            else:
                print("Операция отменена.")

            # utils.enable_monitor_mode(config.interface)
            self.update_status(0, 0)
        elif button_name == 'Export to CSV':
            print(f"Button '{button_name}' clicked.")
        elif button_name == 'Open White List':
            print(f"Button '{button_name}' clicked.")
        elif button_name == 'Show Details':
            print(f"Button '{button_name}' clicked.")
        elif button_name == '2name':
            self.open_second_window()
            print(f"Button '{button_name}' clicked.")


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