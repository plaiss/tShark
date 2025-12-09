import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter import messagebox
from tkinter.messagebox import showinfo
from tkinter import simpledialog
from config import _stop
import config
import utils
import main
from second_window import SecondWindow  # Импортируем класс из отдельного файла
from settings_window import SettingsWindow
from export_dialog import ExportDialog
from choose_channels import ChannelSelectorDialog  # Новое окно выбора каналов

class WifiMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Настройка главного окна приложения
        self.title("WiFi Monitor")
        self.minsize(width=800, height=480)
        self.center_window()  # Центрируем окно
        
        # Переменная состояния чекбокса (инициализируем до использования)
        self.reverse_check_var = tk.BooleanVar(value=False)
        
        # Хранилище ссылок на созданные кнопки
        self.buttons = {}  # Словарь для хранения ссылок на кнопки
        
        # Главный фрейм для всего интерфейса
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Центральный контейнер для разделения на левую и правую стороны
        central_container = tk.Frame(main_frame)
        central_container.pack(fill=tk.BOTH, expand=True)
        
        # Левый контейнер для таблицы (TreeView)
        table_container = tk.Frame(central_container)
        table_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # Таблица занимает всю левую сторону
        
        # Таблица с устройствами
        self.tree_view(table_container)
        
        # Правый контейнер для панели инструментов
        toolbar_container = tk.Frame(central_container, bg="#f0f0f0")
        toolbar_container.pack(side=tk.RIGHT, fill=tk.Y)  # Кнопки располагаются справа, растягиваются по высоте
        
        # Создаем сами кнопки
        self.create_buttons(toolbar_container)
        
        # Новый контейнер для журнала сообщений
        log_container = tk.Frame(main_frame)
        log_container.pack(side=tk.TOP, fill=tk.X)  # Ставим контейнер под центральным контейнером, растянув по ширине
        
        # Создаем сам журнал сообщений
        self.log_view(log_container)
        
        # Полоса статуса снизу окна
        self.status_bar()
        
        # Индикатор состояния потока
        self.indicator = tk.Label(self, text="", background="black", width=7, height=1)
        self.indicator.pack()
        self.update_indicator()
        
        # Словарь состояний сортировки для каждого столбца
        self._column_sort_state = {}
        for col in ["#1", "#2", "#3", "#4", "#5"]:
            self._column_sort_state[col] = True  # По умолчанию сортировка прямого порядка

    # Централизация окна
    def center_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 800
        window_height = 480
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Автообновление индикатора состояния потока
    def update_indicator(self):
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            self.indicator.config(background="red", text='running')
            new_props = {'relief': 'sunken'}
            self.set_button_properties('Стоп', new_props)
        else:
            self.indicator.config(background="#ccc", text='stopped')
            new_props = {'relief': 'raised'}
            self.set_button_properties('Стоп', new_props)
        self.after(1000, self.update_indicator)  # Обновляем индикатор каждые 1000 мс

    def tree_view(self, frame):
        # Заголовок дерева
        title_label = tk.Label(frame, text="Обнаруженные уникальные MAC-адреса", font=("TkDefaultFont", 10))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)
        
        # Прокрутка вертикальная для дерева
        scroll_y = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Структура таблицы TreeView
        columns = ("#1", "#2", "#3", "#4", "#5")  # Добавили новый столбец №5 для номера канала
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)
        
        # Названия столбцов
        self.tree.heading('#1', text='MAC Address', anchor='center', command=lambda: self.sort_column("#1"))
        self.tree.heading('#2', text='Производитель', anchor='center', command=lambda: self.sort_column("#2"))
        self.tree.heading('#3', text='RSSI', anchor='center', command=lambda: self.sort_column("#3"))
        self.tree.heading('#4', text='Последнее обнаружение', anchor='n', command=lambda: self.sort_column("#4"))
        self.tree.heading('#5', text='Канал', anchor='center')  # Название нового столбца
        
        # Размеры столбцов
        self.tree.column('#1', width=150, minwidth=90, stretch=False)
        self.tree.column('#2', width=150, minwidth=90, stretch=False, anchor='center')
        self.tree.column('#3', width=40, minwidth=10, stretch=False, anchor='center')
        self.tree.column('#4', width=200, minwidth=90, stretch=False, anchor='center')
        self.tree.column('#5', width=50, minwidth=10, stretch=False, anchor='center')  
        
        # Связываем событие двойного клика с обработчиком
        self.tree.bind("<Double-1>", self.on_device_double_click)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Конфигурируем прокрутку
        scroll_y.config(command=self.tree.yview)
        
        # Чекбокс для выбора порядка сортировки по первому столбцу
        check_box = tk.Checkbutton(frame, text="по последнему октету", variable=self.reverse_check_var, command=lambda: self.sort_column("#1"))
        check_box.place(in_=title_label, relx=1.0, rely=0.0, anchor="ne", x=250, y=0)  # Рядом с заголовком

    def log_view(self, frame):
        # Текстовая область для журналов и сообщений
        self.text_area = scrolledtext.ScrolledText(frame, wrap=tk.NONE, height=6)  # Ограничиваем высоту в 6 строк
        self.text_area.pack(fill=tk.BOTH, expand=True)  # Растягиваем по ширине и занимаем весь контейнер

    # Полоса статуса
    def status_bar(self):
        self.status_text = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, font=("TkDefaultFont", 10))  # Высота в одну строку
        self.status_text.pack(side=tk.BOTTOM, fill=tk.X)

    # Обработчик двойного клика мыши по устройству
    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            # Остановка сканирования
            _stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства

    def sort_column(self, column_id):
        # Сохраняем текущее состояние сортировки для столбца
        current_order = self._column_sort_state.get(column_id, True)
        new_order = not current_order  # Новый порядок сортировки
        self._column_sort_state[column_id] = new_order  # Запоминаем новый порядок

        items = list(self.tree.get_children())
        values = [(item, self.tree.set(item, column_id)) for item in items]

        try:
            # Применяем сортировку
            if column_id == '#3':  # Числовой столбец (RSSI)
                values.sort(key=lambda x: float(x[1]), reverse=new_order)
            elif column_id == '#1':
                # Специальная логика для первого столбца
                if self.reverse_check_var.get():
                    values.sort(key=lambda x: x[1][::-1], reverse=new_order)
                else:
                    values.sort(key=lambda x: x[1], reverse=new_order)
            else:
                values.sort(key=lambda x: str.lower(x[1]), reverse=new_order)
        except ValueError:
            values.sort(key=lambda x: str.lower(x[1]), reverse=new_order)

        # Обновляем представление
        for idx, (item, _) in enumerate(values):
            self.tree.move(item, '', idx)

        # Меняем выравнивание для первого столбца отдельно
        if column_id == '#1':
            alignment = 'e' if self.reverse_check_var.get() else 'w'
            self.tree.column('#1', anchor=alignment)

    # Открывает второе окно с информацией о устройстве
    def open_second_window(self, *, data=None):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        mac_address = data[0]  # Первая колонка — MAC-адрес
        manufacturer = data[1]  # Вторая колонка — Производитель
        SecondWindow(self, mac_address, manufacturer)

    # Добавляет текст в журнал
    def add_text(self, text):
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.yview_moveto(1.0)

    # Очищает текстовую область
    def clear_text(self):
        self.text_area.delete('1.0', tk.END)

    def update_tree(self, mac_address, vendor, rssi, last_seen, channel_number):
        normalized_mac = ":".join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)])
        item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac), None)
        if item:
            # Если запись существует, обновляем её поля
            self.tree.set(item, '#2', vendor)
            self.tree.set(item, '#3', rssi)
            self.tree.set(item, '#4', last_seen)
            self.tree.set(item, '#5', channel_number)  # Учитываем номер канала
        else:
            # Иначе добавляем новую запись
            self.tree.insert('', tk.END, values=(normalized_mac, vendor, rssi, last_seen, channel_number))
        self.refresh_status()

    def refresh_status(self):
        total_devices = len(config._last_seen)
        devices_in_white_list = sum(1 for mac in config._last_seen if mac in config._whitelist)
        config.mode = utils.get_wlan_mode(config.interface)

        status_message = f"{config.interface}: {config.mode} mode.  | Найдено: {total_devices}"
        self.status_text.replace(1.0, tk.END, status_message)

        if config.mode != 'Monitor':  # Выделяем красный цветом текущий режим
            self.status_text.tag_add("red", '1.6', '1.20')
            self.status_text.tag_config("red", foreground="red")
            self.status_text.config(state=tk.DISABLED)
        else:
            new_props = {'relief': 'sunken', 'state': 'disabled'}
            self.set_button_properties('turn ON monitor mode', new_props)

    def create_buttons(self, toolbar):
        # Определяем названия кнопок и их команды
        button_names_and_commands = {
            "Стоп": {"command": self.toggle_scanning},
            "turn ON monitor mode": {"command": self.switch_to_monitor_mode},
            "Сброс данных": {"command": self.reset_data},
            "Экспорт в CSV": {"command": self.export_csv},
            "Открыть белый список": {"command": self.show_whitelist},
            "Выбор каналов": {"command": self.show_channel_selector},  # Новая кнопка
            "Настройки": {"command": self.show_settings}
        }

        # Стандартные параметры оформления кнопок
        default_style = dict(relief=tk.RAISED, borderwidth=2, activebackground='#ccc')

        # Создание кнопок и их размещение на панели
        for button_name, props in button_names_and_commands.items():
            btn_props = default_style.copy()  # Копируем стандартный стиль
            btn_props.update(props)  # Объединяем с индивидуальными параметрами (включая команду)

            btn = tk.Button(toolbar, text=button_name, **btn_props)
            btn.pack(side=tk.TOP, fill=tk.X, expand=True, padx=5, pady=5)  # Располагаем кнопки вертикально
            self.buttons[button_name] = btn  # Сохраняем ссылку на кнопку
                # Прямо здесь устанавливаем начальный текст кнопки
        # self.set_button_properties('Стоп', {'text': 'Пуск'})

    # Универсальный метод для установки любых свойств кнопки
    def set_button_properties(self, button_name, properties):
        """
        Изменяет любые свойства указанной кнопки.
        :param button_name: Имя кнопки
        :param properties: Словарь новых свойств (например, {'relief': 'sunken', 'bg': 'red'})
        """
        if button_name in self.buttons:
            self.buttons[button_name].config(**properties)

    # Функционал для каждой кнопки
    def toggle_scanning(self):
        """Начало/остановка сканирования."""
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            # Остановка сканирования
            _stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток
            self.set_button_properties('Стоп', {'text': 'Пуск'})  # Меняем текст на "Пуск"
        else:
            # Начало сканирования
            _stop.clear()  # Снимаем флаг остановки
            self.start_tshark()
            self.set_button_properties('Стоп', {'text': 'Стоп'})  # Меняем текст на "Стоп"

    def start_tshark(self):
        """Запуск потока сканирования."""
        self.tshark_thread = threading.Thread(target=main.tshark_worker, args=(self, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        self.tshark_thread.start()

    def switch_to_monitor_mode(self):
        """Перевод интерфейса в мониторный режим."""
        password = config.password  # Пароль жёстко закодирован!
        if password is not None and len(password.strip()) > 0:
            success = utils.enable_monitor_mode(config.interface, password)
            if success:
                self.refresh_status()
        else:
            print("Операция отменена.")

    def reset_data(self):
        """Сброс всех собранных данных."""
        config._last_seen.clear()
        config._seen_count.clear()
        self.tree.delete(*self.tree.get_children())
        self.clear_text()

    def export_csv(self):
        """Экспорт данных в CSV-файл."""
        self.toggle_scanning()  # Сначала останавливаем сканирование
        # Затем открываем окно настроек
        export_window = ExportDialog(self.master,self.tree)
        export_window.grab_set()  # Фокусируется на окне настроек

    def show_whitelist(self):
        """Отображает содержимое белого списка."""
        whitelist_str = '\n'.join(config._whitelist.keys())
        messagebox.showinfo("Белый список", whitelist_str)

    def show_details(self):
        """Покажет дополнительную информацию о выделенном устройстве."""
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]
        if data:
            details = f"MAC: {data[0]} | Производитель: {utils.lookup_vendor_db(data[0], config.DB_PATH, False)}\nКол-во сигналов: {data[1]}\nПоследний раз обнаружен: {data[2]}"
            messagebox.showinfo("Детали устройства", details)

    def show_settings(self):
        #    """Открывает окно настроек и останавливает процесс сканирования перед открытием"""
        self.toggle_scanning()  # Сначала останавливаем сканирование
    
        # Затем открываем окно настроек
        settings_window = SettingsWindow(self.master)
        settings_window.grab_set()  # Фокусируется на окне настроек

    def show_channel_selector(self):
        # Вызов окна выбора каналов
        dialog = ChannelSelectorDialog(self, config.interface)
        if dialog.result:
            selected_channels = dialog.selected_channels
            delay_time = dialog.delay_time
            self.scan_selected_channels(selected_channels, delay_time)

    def scan_selected_channels(self, channels, delay_time):
        # def change_channel(channel):
        #     subprocess.run(["iw", "dev", config.interface, "set", "channel", str(channel)], capture_output=True)
        
        def change_channel(channel, password=config.password):
            # Формируем команду
            command = ['sudo', 'iw', 'dev', config.interface, 'set', 'channel', str(channel)]

            # Выполнение команды с передачей пароля через stdin
            process = subprocess.run(command, input=f'{password}\n', encoding='utf-8', capture_output=True)

            if process.returncode != 0:
                print(f"Ошибка: {process.stderr.decode()}")  # Выводим сообщение об ошибке
            else:
                print(f"Успешно сменил канал на {channel} для интерфейса {config.interface}.")
                # Планируем обновление лейбла в главном потоке Tkinter
                self.after(0, lambda: self.update_title_with_channel(channel))
        


        def run_scanner():
            while True:
                for channel in channels:
                    change_channel(channel)
                    time.sleep(delay_time)

        scanner_thread = threading.Thread(target=run_scanner, daemon=True)
        scanner_thread.start()


    def update_title_with_channel(self, channel):
        # Безопасное обновление лейбла в главном потоке
        updated_text = f"Обнаруженные уникальные MAC-адреса (Канала: {channel})"
        self.title_label.config(text=updated_text)



if __name__ == "__main__":
    app = WifiMonitor()
    app.mainloop()