import subprocess
import threading
import time
import tkinter as tk
import os
import signal

from tkinter import ttk, scrolledtext
from tkinter import messagebox
from tkinter.messagebox import showinfo
from tkinter import simpledialog
from collections import deque
import queue
from config import _stop
import config
import utils
import main
import logging
from second_window import SecondWindow  # Импортируем класс из отдельного файла
from settings_window import SettingsWindow
from export_dialog import ExportDialog
from choose_channels import ChannelSelectorDialog  # Новое окно выбора каналов
import logging

logger = logging.getLogger(__name__)


class WifiMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
    
        # self.logger = logging.getLogger(__name__)
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
        self.indicator.pack(side='left')
        # Присваиваем обработчик события для индикатора RUNNING
        self.indicator.bind('<Button-1>', self.on_running_indicator_click)
        
        # Новый индикатор для состояния сканирования каналов
        self.channel_indicator = tk.Label(self, text="", background="grey", width=7, height=1)
        self.channel_indicator.pack(side='left')
        
        # Добавляем связывание события Button-1 (щелчок левой кнопкой мыши)
        self.channel_indicator.bind('<Button-1>', self.on_channel_indicator_click)

        # Новый индикатор для отображения текущего канала
        self.channel_label = tk.Label(self, text="Channel:", background="lightblue", width=10, height=1)
        self.channel_label.pack(side='left')
        
        self.update_indicator()
        self.update_channel_indicator()
        self.refresh_status()

        # Словарь состояний сортировки для каждого столбца
        self._column_sort_state = {}
        for col in ["#1", "#2", "#3", "#4", "#5", "#6", "#7"]:
            self._column_sort_state[col] = True  # По умолчанию сортировка прямого порядка
        # Флаг активности сканирования
        self.scanning_active = False
        self.prev_channels = []
        self.prev_delay_time =0
        # Перемещаем сюда объявление буфера
        self.tree_buffer = deque(maxlen=1000)
        self.log_queue = queue.Queue()

        self.flush_lock = threading.Lock()
        self.flush_buffers()

    def flush_buffers(self):
        # Получаем блокировку (если уже занята — ждём)
        with self.flush_lock:
            logger.info("Flushing buffers...")
            
            # Массовое обновление дерева
            while self.tree_buffer:
                mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes = self.tree_buffer.popleft()
                self.update_tree(mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes)

            logger.info("Buffers flushed successfully.")
            
            # Обработка логов
            messages = []
            while not self.log_queue.empty():
                messages.append(self.log_queue.get())
            if messages:


                # Проверяем, существует ли список и не пуст ли он
                if messages and len(messages) > 0:
                    last_element = messages[-1]  # Получаем последний элемент
                    # Проверяем, что последний символ не равен '\n'
                    if not last_element.endswith('\n'):
                        messages[-1] = last_element + '\n'  # Добавляем '\n' к последнему элементу

                self.add_text("\n".join(messages))
            
            # Плановое повторение (самозапланирование через 1 секунду)
            # Важно: self.after() должен быть вне блока with, чтобы не блокировать поток GUI
            self.after(1000, lambda: self.flush_buffers())

        # Централизация окна
    def center_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 800
        window_height = 480
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")



    def tree_view(self, frame):
        # Заголовок дерева
        self.title_label = tk.Label(frame, text=f"Обнаруженные уникальные MAC-адреса", font=("TkDefaultFont", 10))  # Здесь делаем title_label атрибутом класса
        self.title_label.pack(side=tk.TOP, anchor="w", pady=5)
        
        # Прокрутка вертикальная для дерева
        scroll_y = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Структура таблицы TreeView
        # columns = ("#1", "#2", "#3", "#4", "#5", "#6")  # Добавляем новый столбец
        # self.tree = ttk.Treeview(frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)
        columns = ("#1", "#2", "#3", "#4", "#5", "#6", "#7")  # Добавляем ещё один столбец
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)
        
        # Названия столбцов
        self.tree.heading('#1', text='MAC Address', anchor='center', command=lambda: self.sort_column("#1"))
        self.tree.heading('#2', text='Вендор', anchor='center', command=lambda: self.sort_column("#2"))
        self.tree.heading('#3', text='RSSI', anchor='center', command=lambda: self.sort_column("#3"))
        self.tree.heading('#4', text='Время', anchor='n', command=lambda: self.sort_column("#4"))
        self.tree.heading('#5', text='Канал', anchor='center', command=lambda: self.sort_column("#5"))  # Привязываем сортировку
        self.tree.heading('#6', text='Кол-во', anchor='center', command=lambda: self.sort_column("#6"))
        self.tree.heading('#7', text='Траффик', anchor='center', command=lambda: self.sort_column("#7"))  # Название нового столбца
        
        # Размеры столбцов
        self.tree.column('#1', width=150, minwidth=90, stretch=False)
        self.tree.column('#2', width=150, minwidth=90, stretch=False, anchor='center')
        self.tree.column('#3', width=40, minwidth=10, stretch=False, anchor='center')
        self.tree.column('#4', width=100, minwidth=90, stretch=False, anchor='center')
        self.tree.column('#5', width=50, minwidth=10, stretch=False, anchor='center')
        self.tree.column('#6', width=60, minwidth=10, stretch=False, anchor='center')
        self.tree.column('#7', width=80, minwidth=50, stretch=False, anchor='center')  # Ширина нового столбца
        
        
        # Связываем событие двойного клика с обработчиком
        self.tree.bind("<Double-1>", self.on_device_double_click)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Конфигурируем прокрутку
        scroll_y.config(command=self.tree.yview)
        
        # Чекбокс для выбора порядка сортировки по первому столбцу
        check_box = tk.Checkbutton(frame, text="по последнему октету", variable=self.reverse_check_var, command=lambda: self.sort_column("#1"))
        check_box.place(in_=self.title_label, relx=1.0, rely=0.0, anchor="ne", x=200, y=0)  # Рядом с заголовком

    def log_view(self, frame):
        # Текстовая область для журналов и сообщений
        self.text_area = scrolledtext.ScrolledText(frame, wrap=tk.NONE, height=5)  # Ограничиваем высоту в 5 строк
        self.text_area.pack(fill='both', expand=True)  # Растягиваем по ширине и занимаем весь контейнер

    # Полоса статуса
    def status_bar(self):
        self.status_text = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, width=37, font=("TkDefaultFont", 10))  # Высота в одну строку
        self.status_text.pack(side=tk.LEFT, anchor='w')
        # Автообновление индикатора состояния потока
        
    def update_indicator(self):
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            logger.info("TShark thread is alive.DEF update_indicator")
            self.indicator.config(background="red", text='running')
            new_props = {'relief': 'sunken', 'text': 'Стоп'}
            self.set_button_properties('Стоп', new_props)
        else:
            self.indicator.config(background="#ccc", text='stopped')
            new_props = {'relief': 'raised', 'text': 'Пуск'}
            self.set_button_properties('Стоп', new_props)
        
        # Проверка статуса сканирования каналов
        if getattr(self, 'scanning_active', False):
            self.channel_indicator.config(background="yellow", text='scanning')
        else:
            self.channel_indicator.config(background="#ccc", text='no scan')

        self.after(1000, self.update_indicator)  # Обновляем индикатор каждые 1000 мс

    def update_channel_indicator(self):
        # Получаем текущий канал
        current_channel, frequency = utils.get_current_channel()
        if not current_channel:
            current_channel = 1 # Заглушка, если не Monitor mode
        self.channel_label.config(text=f"Ch:{current_channel}", background="lightblue")
        # Повторяем проверку каждые 2 секунды
        # self.after(2000, self.update_channel_indicator)

    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства

    # Открывает второе окно с информацией о устройстве
    def open_second_window(self, *, data=None):
        scanner_was_running = False
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            _stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread = None  # Немедленно удаляем ссылку на поток
        
        if hasattr(self, 'scanner_thread'):
            scanner_was_running = True

        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        mac_address = data[0]  # Первая колонка — MAC-адрес
        manufacturer = data[1]  # Вторая колонка — Производитель
        channel = data[4]

        self.stop_scanning()
        self.change_channel(channel)
        SecondWindow(self, mac_address, manufacturer, channel)
        if scanner_was_running == True:
            print("он был запущен, можно перезапускать заново")

    def sort_column(self, column_id):
        # print(f"[SORT] Начало сортировки для столбца {column_id}")
        
        # Сохраняем состояние
        current_order = self._column_sort_state.get(column_id, True)
        new_order = not current_order
        self._column_sort_state[column_id] = new_order
        # print(f"[SORT] Порядок: {current_order} → {new_order}")
        
        # Получаем данные
        items = list(self.tree.get_children())
        if not items:
            # print("[SORT] Нет элементов для сортировки")
            return
            
        values = [(item, self.tree.set(item, column_id)) for item in items]
        # print(f"[SORT] Исходные данные: {values}")
        
        try:
            if column_id == '#3':  # RSSI (float)
                key_func = lambda x: (
                    float(str(x[1]).strip()) if str(x[1]).strip()
                    else float('-inf')
                )
            elif column_id in ('#5', '#6', '#7'):  # Целочисленные столбцы
                key_func = lambda x: (
                    int(str(x[1]).strip()) if str(x[1]).strip().isdigit()
                    else 0
                )
            elif column_id == '#1':  # MAC-адрес
                if self.reverse_check_var.get():
                    key_func = lambda x: x[1][::-1]
                else:
                    key_func = lambda x: x[1]
            else:  # Остальные столбцы (строки)
                key_func = lambda x: str.lower(str(x[1]) if x[1] is not None else '')

            values.sort(key=key_func, reverse=new_order)
            # print(f"[SORT] Отсортированные данные: {values}")

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Ошибка сортировки: {e}")
            print(f"[SORT] Ошибка сортировки: {e}")
            values.sort(
                key=lambda x: str.lower(str(x[1]) if x[1] is not None else ''),
                reverse=new_order
            )

        
        # Обновляем дерево
        for idx, (item, _) in enumerate(values):
            self.tree.move(item, '', idx)
            # print(f"[SORT] Перемещено: {item} → {idx}")
        
        # Корректируем выравнивание для MAC-адреса
        if column_id == '#1':
            alignment = 'e' if self.reverse_check_var.get() else 'w'
            self.tree.column('#1', anchor=alignment)
            # print(f"[SORT] Выравнивание: {alignment}")
        
        # print("[SORT] Сортировка завершена")




    # Добавляет текст в журнал
    def add_text(self, text):
        # self.text_area.insert(tk.END, text + "\n")
        self.text_area.insert(tk.END, text)
        self.text_area.yview_moveto(1.0) #прокручивает вертикальный скролл виджета до самого низа (1.0 = 100% позиции по вертикали)



    def update_tree(self, mac_address, vendor, rssi, last_seen, channel_number, appearance_count, useful_bytes):
        with config._seen_lock:
            # Обновляем данные
            normalized_mac = ":".join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)])
            item = next((item for item in self.tree.get_children() if self.tree.item(item)['values'][0] == normalized_mac), None)
            if item:
                # Если запись существует, обновляем её поля
                self.tree.set(item, '#2', vendor)
                self.tree.set(item, '#3', rssi)
                self.tree.set(item, '#4', last_seen)
                self.tree.set(item, '#5', channel_number)
                self.tree.set(item, '#6', appearance_count)
                self.tree.set(item, '#7', useful_bytes)
            else:
                # Иначе добавляем новую запись
                self.tree.insert('', tk.END, values=(normalized_mac, vendor, rssi, last_seen, channel_number, appearance_count))
            self.refresh_status()

    def refresh_status(self):
        total_devices = len(config._last_seen)
        devices_in_white_list = sum(1 for mac in config._last_seen if mac in config._whitelist)
        config.mode = utils.get_wlan_mode(config.interface)

        status_message = f"{config.interface}: {config.mode} mode.  | Найдено: {total_devices}"
        self.status_text.replace(1.0, tk.END, status_message)

        if config.mode != 'Monitor':  # Выделяем красный цветом текущий режим
            self.status_text.tag_add("highlight", '1.6', '1.20')
            self.status_text.tag_config("highlight", foreground="red")
            self.add_text('Инерфейс не переведён в режим Monitor, нажмите кнопку Monitor mode\n')
            # self.status_text.config(state=tk.DISABLED)
        else:
            # self.status_text.tag_remove("highlight", "1.0", tk.END)  # удалить тег со всего текста
            new_props = {'relief': 'sunken', 'state': 'disabled'}
            self.set_button_properties('Monitor mode', new_props)
        # Повторяем проверку каждые 2 секунды
        # self.after(10000, self.refresh_status)

    def create_buttons(self, toolbar):
        # Определяем названия кнопок и их команды
        button_names_and_commands = {
            "Стоп": {"command": self.toggle_scanning},
            "Monitor mode": {"command": self.switch_to_monitor_mode},
            "Очистить список": {"command": self.reset_data},
            "Экспорт в TXT": {"command": self.export_csv},
            "Белый список": {"command": self.show_whitelist},
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

    # Универсальный метод для установки любых свойств кнопки
    def set_button_properties(self, button_name, properties):
        """
        Изменяет любые свойства указанной кнопки.
        :param button_name: Имя кнопки
        :param properties: Словарь новых свойств (например, {'relief': 'sunken', 'bg': 'red'})
        """
        if button_name in self.buttons:
            self.buttons[button_name].config(**properties)

            
    def toggle_scanning(self):
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            _stop.set()  # Устанавливаем флаг остановки
            # Не удаляем ссылку на поток, а позволяем ему закончить естественно
            # self.tshark_thread = None  # Эту строку нужно убрать
            self.set_button_properties('Стоп', {'text': 'Пуск'})  # Меняем текст на "Пуск"
        else:
            _stop.clear()  # Снимаем флаг остановки
            self.start_tshark()
            self.set_button_properties('Стоп', {'text': 'Стоп'})  # Меняем текст на "Стоп"
    
    def start_tshark(self):
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            return  # Если поток уже запущен, ничего не делаем
        self.tshark_thread = threading.Thread(target=main.tshark_worker, args=(self, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        self.tshark_thread.start()

    def clean_buffers(self, controlled=False):
        if controlled:
            # Здесь можно добавить управляемую очистку (если нужно)
            pass
        else:
            # Оставляем только очистку лога
              print ('здесь могла бы быть ваша реклама')
              pass
            # self.clear_text()  # Очищаем текстовую область
        
    # Очищает текстовую область
    def clear_text(self):
        self.text_area.delete('1.0', tk.END)
      





    def switch_to_monitor_mode(self):
        """Перевод интерфейса в мониторный режим."""
        password = config.password  # Пароль жёстко закодирован!
        if password is not None and len(password.strip()) > 0:
            success = utils.enable_monitor_mode(config.interface, password)
            if success:
                self.add_text(f'Интерфейс {config.interface} успешно переведен в режим монитора.\n')
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
        try:
            # Прямо вызываем класс ExportDialog для начала экспорта
            ExportDialog(self.master, self.tree)

        except Exception as e:
            print(f"Ошибка при открытии окна экспорта: {e}")
            messagebox.showerror("Ошибка", "Не удалось открыть окно экспорта данных.")

    def _on_export_dialog_close(self, dialog_window):
        """Обработчик закрытия окна экспорта."""
        # Освобождаем модальный захват
        dialog_window.grab_release()
        
        # Закрываем окно
        dialog_window.destroy()
        
        # Дополнительно: можно обновить интерфейс или выполнить другие действия после закрытия

    def show_whitelist(self):
        """Показывает содержание белого списка и открывает его для редактирования в отдельном окне терминала."""
        # Определение пути к файлу white-list
        whitelist_path = config.WHITELIST_PATH  # Или локально определённое значение

        # Команда для открытия xterm с запущенным nano
        terminal_command = [
            'xterm',
            '-T', 'Редактирование белого списка',  # Название окна
            # '-hold',                               # Держать окно открытым после выхода из nano
            '-e',                                  # Выполнить команду
            'nano', whitelist_path                 # Запуск nano с указанным файлом
        ]

        try:
            # Запуск терминала с nano и получение объекта процесса
            process = subprocess.Popen(terminal_command)

            # Ожидание завершения процесса
            process.wait()  # Ждать, пока пользователь закончит редактирование

            # Отправка сигнала SIGHUP основному процессу tshark
            pid = os.getpid()  # PID текущего процесса
            os.kill(pid, signal.SIGHUP)

            # Уведомление пользователя о завершении
            messagebox.showinfo("Готово", "Белый список успешно обновлён!")

        except OSError as err:
            messagebox.showerror("Ошибка", f"Невозможно открыть терминал: {err}")
            logger.error(f"Невозможно открыть терминал: {err}")
            return


    def show_settings(self):
        # Затем открываем окно настроек
        settings_window = SettingsWindow(self.master)
        settings_window.grab_set()  # Фокусируется на окне настроек

    def show_channel_selector(self):
        dialog = ChannelSelectorDialog(self, config.interface, channels=getattr(self, 'prev_channels', None), delay_time=getattr(self, 'prev_delay_time', None))

        if dialog.result:
            selected_channels, delay_time = dialog.result
            self.prev_channels = selected_channels
            self.prev_delay_time = delay_time
            if selected_channels:
                self.scan_selected_channels(selected_channels, delay_time)
            else:
                # Если выбрали пустой список каналов, то остановим сканирование
                self.stop_scanning()

    def scan_selected_channels(self, channels, delay_time=0.25):
        if len(channels) == 1:
            # Единственный канал — фиксируем на нём
            self.stop_scanning()
            self.change_channel(channels[0])
            return
        
        # Циклическое сканирование по нескольким каналам
        def run_scanner():
            while self.scanning_active:
                for channel in channels:
                    if self.scanning_active == False:
                        break
                    # logger.info("Before changing channel")
                    self.change_channel(channel)
                    # logger.info("Before changing channel")
                    time.sleep(delay_time)

        self.scanner_thread = threading.Thread(target=run_scanner, daemon=True)
        self.scanning_active = True  # Включаем сканирование
        self.scanner_thread.start()

    def change_channel(self, channel, password=config.password):
        logger.info("Before changing channel")
        # Формируем команду
        command = ['sudo', 'iw', 'dev', config.interface, 'set', 'channel', str(channel)]
        # Выполнение команды с передачей пароля через stdin
        process = subprocess.run(command, input=f'{password}\n', encoding='utf-8', capture_output=True)

        if process.returncode != 0:
            print(f"Ошибка: {process.stderr}")  # Выводим сообщение об ошибке
            logger.info(f"Ошибка: {process.stderr}")
        else:
            # print(f"Успешно сменил канал на {channel} для интерфейса {config.interface}.")
            logger.info(f"Успешно сменил канал на {channel} для интерфейса {config.interface}.")
            # Обновляем лейбл с номером канала
            # updated_text = f"Обнаруженные уникальные MAC-адреса (Канал: {channel})"
            # self.title_label.config(text=updated_text)
            self.update_channel_indicator()

    def stop_scanning(self):
        # Отключаем флаг активности сканирования
        self.scanning_active = False
        # Ждем завершения потока (если надо, можете добавить таймаут ожидания)
        if hasattr(self, 'scanner_thread'):
            self.scanner_thread.join(timeout=1.0)  # Дожидаемся завершения потока
            # del self.scanner_thread  # Освобождаем память

        self.add_text("Процесс сканирования каналов остановлен." + "\n")
    
    def on_channel_indicator_click(self, event):
        if self.scanning_active:
            self.stop_scanning()
        else:
            # Например, начать сканирование или выбрать каналы вручную
            self.show_channel_selector()
            
    def on_running_indicator_click(self, event):
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            logger.info("TShark thread is alive.")
            # Текущий поток активен, остановка мониторинга
            _stop.set()  # Установим флаг остановки
            self.tshark_thread = None  # Удалим ссылку на поток
            new_props = {'relief': 'raised'}  # Вернем виджет в исходное состояние
            self.set_button_properties('Стоп', new_props)
        else:
            # Поток не активен, запускаем мониторинг
            _stop.clear()  # Снимем флаг остановки
            self.start_tshark()
            new_props = {'relief': 'sunken'}  # Сделаем кнопку утопленной
            self.set_button_properties('Стоп', new_props)


if __name__ == "__main__":
    app = WifiMonitor()
    app.mainloop()