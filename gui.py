import threading
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

        # Настройка главного окна приложения
        self.title("WiFi Monitor")
        self.minsize(width=1380, height=768)
        self.center_window()  # Центрируем окно

        # Хранилище ссылок на созданные кнопки
        self.buttons = {}  # Словарь для хранения ссылок на кнопки

        # Главный фрейм для всего интерфейса
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Панель инструментов с кнопками сверху
        toolbar = tk.Frame(main_frame, bg="#f0f0f0")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Создание кнопок и хранение ссылок на них
        self.create_buttons(toolbar)

        # Левый контейнер для таблицы (TreeView)
        left_container = tk.Frame(main_frame)
        left_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Таблица с устройствами
        self.tree_view(left_container)

        # Правый контейнер для журнала сообщений
        right_container = tk.Frame(main_frame)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Журнал сообщений
        self.log_view(right_container)

        # Полоса статуса снизу окна
        self.status_bar()

        # Индикатор состояния потока
        self.indicator = tk.Label(self, text="", background="black", width=7, height=1)
        self.indicator.pack()
        self.update_indicator()


    # Центральизация окна
    def center_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 1380
        window_height = 768
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Автообновление индикатора состояния потока
    def update_indicator(self):
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            self.indicator.config(background="red", text='running')
        else:
            self.indicator.config(background="#ccc", text='stoped')
        self.after(1000, self.update_indicator)  # Обновляем индикатор каждые 1000 мс

    # Таблица с устройствами
    def tree_view(self, frame):
        # Заголовок дерева
        title_label = tk.Label(frame, text="Обнаруженные уникальные MAC-адреса", font=("TkDefaultFont", 10, 'bold'))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Прокрутка вертикальная для дерева
        scroll_y = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Структура таблицы TreeView
        columns = ("#1", "#2", "#3", "#4")  # Столбцы (#1-MAC адрес, #2-Производитель, #3-RSSI, #4-Время последнего обнаружения)
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)

        # Подписи заголовков столбцов
        self.tree.heading('#1', text='MAC Address', anchor='center', command=lambda: self.sort_column("#1"))
        self.tree.heading('#2', text='Производитель', anchor='center', command=lambda: self.sort_column("#2"))
        self.tree.heading('#3', text='RSSI', anchor='center', command=lambda: self.sort_column("#3"))
        self.tree.heading('#4', text='Последнее обнаружение', anchor='center', command=lambda: self.sort_column("#4"))

        # Ширина столбцов
        self.tree.column('#1', width=150, minwidth=90, stretch=False)
        self.tree.column('#2', width=150, minwidth=90, stretch=False)
        self.tree.column('#3', width=40, minwidth=10, stretch=False)
        self.tree.column('#4', width=300, minwidth=90, stretch=False)

        # Связываем событие двойного клика с обработчиком
        self.tree.bind("<Double-1>", self.on_device_double_click)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Конфигурируем прокрутку
        scroll_y.config(command=self.tree.yview)

    # Журнал сообщений
    def log_view(self, frame):
        # Текстовая область для журналов и сообщений
        self.text_area = scrolledtext.ScrolledText(frame, wrap=tk.NONE, height=6)  # Высота в 6 строк
        self.text_area.pack(fill=tk.BOTH, expand=True)

    # Полоса статуса
    def status_bar(self):
        self.status_label = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, font=("TkDefaultFont", 10))  # Высота в одну строку
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # Обработчик двойного клика мыши по устройству
    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства

    # Функция для обновления полосы статуса
    def update_status(self, total_devices, ignored_devices):
        config.mode = utils.get_wlan_mode(config.interface)
        status_message = f"{config.interface}: {config.mode} mode.  | Найдено: {total_devices}, Белый список: Всего {len(config._whitelist)}, Игнорировано: {ignored_devices}"
        self.status_label.delete('1.0', tk.END)
        self.status_label.insert(tk.END, status_message)

        if config.mode != 'Monitor':  # Выделяем красным текущий режим
            self.status_label.tag_add("red", '1.6', '1.20')
            self.status_label.tag_config("red", foreground="red")
            self.status_label.config(state=tk.DISABLED)

    # Создание кнопок и сохранение ссылок на них
    def create_buttons(self, toolbar):
        # Определяем названия кнопок и их команды
        button_names_and_commands = {
            "Стоп": {"command": self.toggle_scanning},
            "Мониторинг": {"command": self.switch_to_monitor_mode},
            "Сброс данных": {"command": self.reset_data},
            "Экспорт в CSV": {"command": self.export_csv},
            "Открыть белый список": {"command": self.show_whitelist},
            "Показать детали": {"command": self.show_details},
            "Настройки": {"command": self.show_settings}
        }

        # Стандартные параметры оформления кнопок
        default_style = dict(relief=tk.RAISED, borderwidth=2, activebackground='#ccc')

        # Создание кнопок и их размещение на панели
        for button_name, props in button_names_and_commands.items():
            btn_props = default_style.copy()  # Копируем стандартный стиль
            btn_props.update(props)  # Объединяем с индивидуальными параметрами (включая команду)

            btn = tk.Button(toolbar, text=button_name, **btn_props)
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
            self.buttons[button_name] = btn  # Сохраняем ссылку на кнопку

    # Универсальный метод для установки любых свойств кнопки
    def set_button_properties(self, button_name, properties):
        """
        Изменяет любое количество свойств указанной кнопки.
        :param button_name: Имя кнопки
        :param properties: Словарь новых свойств (например, {'relief': 'sunken', 'bg': 'red'})
        """
        if button_name in self.buttons:
            self.buttons[button_name].config(**properties)

    # Функционал для каждой кнопки
    def toggle_scanning(self):
        """Начало/остановка сканирования"""
        from config import _stop
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            # Остановка сканирования
            _stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток
        else:
            # Начало сканирования
            _stop.clear()  # Снимаем флаг остановки
            self.start_tshark()

    def start_tshark(self):
        """Запуск потока сканирования"""
        self.tshark_thread = threading.Thread(target=main.tshark_worker, args=(self, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        self.tshark_thread.start()
        #
        # tshark_thread = threading.Thread(target=tshark_worker, args=(root, cmd, SEEN_TTL_SECONDS), daemon=True)
        # tshark_thread.start()
        # root.tshark_thread = tshark_thread  # Присваиваем ссылку на поток в экземпляр App

    def switch_to_monitor_mode(self):
        """Перевод интерфейса в мониторный режим"""
        password = simpledialog.askstring("Пароль sudo", "Введите пароль sudo:", show="*")
        if password is not None and len(password.strip()) > 0:
            success = utils.enable_monitor_mode(config.interface, password)
        else:
            print("Операция отменена.")

    def reset_data(self):
        """Сброс всех собранных данных"""
        config._last_seen.clear()
        config._seen_count.clear()
        self.tree.delete(*self.tree.get_children())
        self.clear_text()

    def export_csv(self):
        """Экспорт данных в CSV-файл"""
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All Files", "*.*")])
        if filename:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["MAC Адрес", "Производитель", "RSSI", "Время последнего обнаружения"])
                for item in self.tree.get_children():
                    row = self.tree.item(item)["values"]
                    writer.writerow(row)

    def show_whitelist(self):
        """Отображает содержимое белого списка"""
        whitelist_str = '\n'.join(config._whitelist.keys())
        messagebox.showinfo("Белый список", whitelist_str)

    def show_details(self):
        """Покажет дополнительную информацию о выделенном устройстве"""
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]
        if data:
            details = f"MAC: {data[0]} | Производитель: {utils.lookup_vendor_db(data[0], config.DB_PATH, False)}\nКол-во сигналов: {data[1]}\nПоследний раз обнаружен: {data[2]}"
            messagebox.showinfo("Детали устройства", details)

    def show_settings(self):
        """Окно настроек"""
        settings_dialog = SettingsDialog(self)
        settings_dialog.grab_set()

    # Сортировка значений в таблице
    def sort_column(self, column_id):
        items = list(self.tree.get_children())
        try:
            # Попытка числовой сортировки для RSSI
            items.sort(key=lambda x: float(self.tree.set(x, column_id)) if column_id == '#3' else str.lower(self.tree.set(x, column_id)))
        except ValueError:
            # В противном случае используем алфавитную сортировку
            items.sort(key=lambda x: str.lower(self.tree.set(x, column_id)))

        # Перестановка элементов согласно сортировке
        for idx, item in enumerate(items):
            self.tree.move(item, '', idx)

    # Открывает второе окно с информацией о устройстве
    def open_second_window(self, data=None):
        SecondWindow(self, data=data)

    # Добавляет текст в журнал
    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)

    # Очищает текстовую область
    def clear_text(self):
        self.text_area.delete('1.0', tk.END)

    # Обновляет таблицу
    def update_tree(self, mac_address, vendor, rssi, last_seen):
        normalized_mac = ":".join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac), None)
        if item:
            self.tree.set(item, '#2', vendor)
            self.tree.set(item, '#3', rssi)
            self.tree.set(item, '#4', last_seen)
        else:
            self.tree.insert('', tk.END, values=(normalized_mac, vendor, rssi, last_seen))

class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.title("Подробности устройства")
        self.geometry("640x480")

        if data is not None:
            details = f"MAC: {data[0]} | Производитель: {utils.lookup_vendor_db(data[0], config.DB_PATH, False)}\nКол-во сигналов: {data[1]}\nПоследний раз обнаружен: {data[2]}"
            label = tk.Label(self, text=details)
            label.pack(pady=20)
        else:
            label = tk.Label(self, text="Нет доступной информации")
            label.pack(pady=20)

        close_btn = tk.Button(self, text="Закрыть", command=self.destroy)
        close_btn.pack(pady=10)

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Настройки")
        self.geometry("400x300")

        # Интерфейс настройки пока пустой, можно расширить позже
        save_btn = tk.Button(self, text="Сохранить", command=self.save_settings)
        save_btn.pack(pady=10)

    def save_settings(self):
        # Здесь реализуйте сохранение настроек
        pass