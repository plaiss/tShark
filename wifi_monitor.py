import subprocess
import threading
import time
import tkinter as tk
import os
import signal
import customtkinter as ctk  # подключаем библиотеку CustomTkinter
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
from whitelist_window import EditorWindow
from threading import Lock
from choose_channels import ChannelSelectorDialog
import traceback
from export_dialog import ExportDialog  # замените 'export_dialog' на реальное имя модуля
from rssi_monitor_async import SecondWindow
from settings_window import SettingsWindow

change_channel_lock = Lock()
logger = logging.getLogger(__name__)    # Логгер настроен в первом файле, тут его повторно настраивать не нужно

ctk.set_appearance_mode("System")  # задаем систему отображения (светлый/дарк-тема)
ctk.set_default_color_theme("green")  # устанавливаем тему зеленого цвета

class WifiMonitor(ctk.CTk):  # наследование от Ctk
    def __init__(self):
        super().__init__()

        # === 1. Инициализация и базовые настройки окна ===
        self.title("WiFi Monitor")
        self.attributes('-fullscreen', True)
        self.minsize(width=800, height=480)
        self.center_window()

        # === 2. Управление состояниями и данными ===
        self.reverse_check_var = tk.BooleanVar(value=False)
        self.buttons = {}  # Словарь для хранения ссылок на кнопки
        
        # Состояния сортировки столбцов
        self._column_sort_state = {}
        for col in ["#1", "#2", "#3", "#4", "#5", "#6", "#7"]:
            self._column_sort_state[col] = True  # По умолчанию — прямой порядок
        
        self.scanning_active = False  # Флаг активности сканирования
        self.prev_channels = []
        self.prev_delay_time = 0
        self.tree_buffer = deque(maxlen=1000)  # Буфер для дерева
        self.log_queue = queue.Queue()  # Очередь логов
        self.flush_lock = threading.Lock()  # Лок для синхронизации очистки

        # === 3. Структура интерфейса (компоновка виджетов) ===
        main_frame = ctk.CTkFrame(self)  # Используем CtkFrame
        main_frame.pack(fill=ctk.BOTH, expand=True)

        central_container = ctk.CTkFrame(main_frame)  # Используем CtkFrame
        central_container.pack(fill=ctk.BOTH, expand=True)

        # Левый контейнер для таблицы (TreeView)
        table_container = ctk.CTkFrame(central_container)  # Используем CtkFrame
        table_container.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)

        # Правый контейнер для панели инструментов
        toolbar_container = ctk.CTkFrame(central_container, fg_color="#f0f0f0")  # фоновый цвет для панели
        toolbar_container.pack(side=ctk.RIGHT, fill=ctk.Y)

        # Контейнер для журнала сообщений
        log_container = ctk.CTkFrame(main_frame)  # Используем CtkFrame
        log_container.pack(side=ctk.TOP, fill=ctk.X)

        # === 4. Создание интерфейсных элементов ===
        self.tree_view(table_container)  # Таблица устройств
        self.create_buttons(toolbar_container)  # Кнопки панели инструментов
        self.log_view(log_container)  # Журнал сообщений
        self.status_bar()  # Строка состояния

        # Кнопка «Закрыть»
        close_button = ctk.CTkButton(self, text="X", font=("Arial", 10, "bold"), command=self.quit)
        close_button.pack(side=ctk.RIGHT, anchor="ne", before=self.status_text)

        # # Индикатор состояния потока

        self.indicator = ctk.CTkLabel(
            self,
            text="",
            fg_color="gray",
            width=70,
            height=20,
            corner_radius=5
        )
        self.indicator.pack(side='left', padx=(10, 5), pady=5)  # Отступ слева 10, справа 5

        # Индикатор состояния сканирования каналов
        # self.channel_indicator = ctk.CTkLabel(self, text="сканинг", fg_color="grey", width=45, height=1)
        # self.channel_indicator.pack(side='left', padx=5, pady=5)  # Равномерные отступы 5px
        self.channel_indicator = ctk.CTkLabel(
            self,
            text="no scan",
            fg_color="gray",           # Как у кнопки «Стоп»
            text_color="black",            # Белый текст (как у кнопки)
            width=70,                     # Приближено к размеру кнопки
            height=20,                  # Высота как у кнопки
            corner_radius=5              # Скругление углов (как у CTkButton)
        )
        self.channel_indicator.pack(side='left', padx=10, pady=5)

        # Индикатор текущего канала
        # self.channel_label = ctk.CTkLabel(self, text="Channel:", fg_color="lightblue", width=10, height=1)
        # self.channel_label.pack(side='left', padx=(5, 10), pady=5)  # Отступ слева 5, справа 10
        self.channel_label = ctk.CTkLabel(
            self,
            text="Ch: ",
            fg_color="lightblue",
            text_color="black",           # Чёрный текст (контраст)
            width=35,                   # Под длину текста
            height=20,
            corner_radius=5
        )
        self.channel_label.pack(side='left', padx=10, pady=5)

        # === 5. Обработка событий ===
        self.indicator.bind('<Button-1>', self.on_running_indicator_click)
        self.channel_indicator.bind('<Button-1>', self.on_channel_indicator_click)

        # === 6. Обновление состояния интерфейса ===
        
        self.update_channel_indicator()
        self.refresh_status()

        # === 7. Очистка и синхронизация данных ===
        self.flush_buffers()

        # Периодически проверяем очередь и обновляем интерфейс
        self.poll_log_queue()

    def poll_log_queue(self):
      while not self.log_queue.empty():
          msg = self.log_queue.get()
          self.add_text(msg)    # Удалили "\n", теперь добавляем только само сообщение

      # Повторно запускаем опрос через 1 секунду
      self.after(1000, lambda: self.poll_log_queue())

    def flush_buffers(self):
        # Получаем блокировку (если уже занята — ждём)
        with self.flush_lock:
            # logger.info("Flushing buffers...")
            
            # Массовое обновление дерева
            while self.tree_buffer:
                mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes = self.tree_buffer.popleft()
                self.update_tree(mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes)

            # logger.info("Buffers flushed successfully.")
            
            # Обработка логов
            messages = []
            while not self.log_queue.empty():
                messages.append(self.log_queue.get())
            if messages:
                self.add_text("\n".join(messages))
            
            # Плановое повторение (самозапланирование через 1 секунду)
            # Важно: self.after() должен быть вне блока with, чтобы не блокировать поток GUI
            self.update_indicator()
            self.after(5000, lambda: self.flush_buffers())

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
        self.title_label = ctk.CTkLabel(frame, text=f"Обнаруженные уникальные MAC-адреса", font=("TkDefaultFont", 10))  # Теперь CtkLabel
        self.title_label.pack(side=ctk.TOP, anchor="w", pady=5)
        
        # Прокрутка вертикальная для дерева
        scroll_y = ctk.CTkScrollbar(frame, orientation=ctk.VERTICAL, width=40)  # Увеличиваем ширину скролла до 20 пикселей
        scroll_y.pack(side=ctk.RIGHT, fill=ctk.Y)
        
        # Структура таблицы TreeView
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
        self.tree.pack(side=ctk.TOP, fill=ctk.BOTH, expand=True)
        
        # Конфигурируем прокрутку
        scroll_y.configure(command=self.tree.yview)
        
        # Чекбокс для выбора порядка сортировки по первому столбцу
        check_box = ctk.CTkCheckBox(
            frame,
            text="по последнему октету",
            variable=self.reverse_check_var,
            command=lambda: self.sort_column("#1")
        )

        check_box.place(in_=self.title_label, relx=1.0, rely=0.0, anchor="ne", x=200, y=0)  # Рядом с заголовком

    def log_view(self, frame):
        # Текстовая область для журналов и сообщений
        self.text_area = tk.Text(frame, wrap=tk.NONE, height=5)  # ограничиваем высоту в 5 строк
        self.text_area.pack(fill='both', expand=True)  # растягиваем по ширине и занимаем весь контейнер
   
    def status_bar(self):
         # Полоса статуса
        self.status_text = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, width=37, font=("TkDefaultFont", 10))  # высота в одну строку
        self.status_text.pack(side=ctk.LEFT, anchor='w')
        # Автообновление индикатора состояния потока

    def update_indicator(self):
        if (hasattr(self, 'tshark_thread') and 
                isinstance(self.tshark_thread, threading.Thread) and
                self.tshark_thread.is_alive()):
            
            # Индикатор статуса (ctk.CTkLabel вместо tk.Label)
            self.indicator.configure(
                fg_color="red",      # цвет фона (аналог background)
                text="running"
            )
            
            # Обновляем кнопку "Стоп" (ctk.CTkButton)
            new_props = {
                'text': 'Стоп',
                'fg_color': 'darkred',     # цвет кнопки при активном состоянии
                'hover_color': 'red',   # цвет при наведении
                'text_color': 'white'    # цвет текста
            }
            self.set_button_properties('Стоп', new_props)
            
        else:
            self.indicator.configure(
                fg_color="gray",     # серый фон (остановлено)
                text="stopped",
                text_color="black" 
            )
            
            # Обновляем кнопку "Стоп" (возвращаем к состоянию "Пуск")
            new_props = {
                'text': 'Пуск',
                'fg_color': 'green',      # цвет кнопки в режиме "Пуск"
                'hover_color': 'darkgreen',
                'text_color': 'white'
            }
            self.set_button_properties('Стоп', new_props)

    def update_channel_indicator(self):
        try:
            current_channel, frequency = utils.get_current_channel()
            if not current_channel:
                current_channel = 1
            self.channel_label.configure(text=f"Ch:{current_channel}")  # Обновляем существующий виджет
        except Exception as e:
            logger.error(f"Ошибка получения текущего канала: {e}")
            self.channel_label.configure(text="Ch:N/A")


    def on_device_double_click(self, event):
        logger.info("Двойной клик")
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            logger.info("Данные имеются")
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства
    
    def open_second_window(self, *, data=None):
        # Открывает второе окно с информацией о устройстве
        scanner_was_running = False
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            _stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread = None  # Немедленно удаляем ссылку на поток
            logger.info("Команды на остановку потока даны")
        
        if hasattr(self, 'scanner_thread'):
            scanner_was_running = True
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        mac_address = data[0]  # Первая колонка — MAC-адрес
        manufacturer = data[1]  # Вторая колонка — Производитель
        channel = data[4]
        self.stop_scanning()
        logger.info("Команды на остановку сканирования каналов даны")
        # self.toggle_scanning()
        self.change_channel(channel)
        logger.info(f"Команды на смену канала на {channel} ")
        SecondWindow(self, mac_address, manufacturer, channel)
        logger.info(f"Команды на смену канала на {channel} ")
        if scanner_was_running == True:
            logger.info("он был запущен, можно перезапускать заново")

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
        
    def add_text(self, text):
            """
            Добавляет текст сверху вниз в self.text_area, удаляя лишние строки,
            пропускает пустые строки и поддерживает ограничение видимости.
            """
            if isinstance(text, str):
                lines = text.splitlines()  # Разбиваем на отдельные строки
            elif isinstance(text, list):
                lines = text
            else:
                raise ValueError("Параметр 'text' должен быть строкой или списком строк.")
                
            for line in reversed(lines):
                if not line.strip():  # Пропускаем пустые строки
                    continue
                    
                # Удаляем самые старые строки, если их больше 1000
                all_lines = self.text_area.get('1.0', tk.END).split('\n')
                while len(all_lines) > 1000:
                    del all_lines[0]
                
                # Формируем обновленный список строк
                new_lines = [''] + all_lines[:-1] + [line]  # добавляем новую строку сверху
                
                # Обновляем содержимое text_area
                self.text_area.delete('1.0', tk.END)
                self.text_area.insert(tk.END, '\n'.join(new_lines))
                
                # Прокручиваем виджет вверх, чтобы новая строка была внизу
                self.text_area.see(tk.END)

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

        # Создаем кнопки и размещаем их на панели
        for button_name, props in button_names_and_commands.items():
            btn = ctk.CTkButton(toolbar, text=button_name, **props)  # Передаем только нужные параметры
            btn.pack(side=ctk.TOP, fill=ctk.X, expand=True, padx=5, pady=5)  # Расположение кнопок
            self.buttons[button_name] = btn  # Сохраняем ссылку на кнопку       

    def set_button_properties(self, button_name, properties):
        if button_name in self.buttons:
            # Фильтруем только поддерживаемые параметры для ctk.CTkButton
            valid_props = {
                k: v for k, v in properties.items()
                if k in ['text', 'fg_color', 'hover_color', 'text_color', 'state', 'width']
            }
            self.buttons[button_name].configure(**valid_props)

    def toggle_scanning(self):
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            _stop.set()  # Устанавливаем флаг остановки
            # Не удаляем ссылку на поток, а позволяем ему закончить естественно
            self.tshark_thread.join(timeout=1.0)  # Ждём завершения потока
            self.tshark_thread = None
            self.set_button_properties('Стоп', {'text': 'Пуск'})  # Меняем текст на "Пуск"
        else:
            _stop.clear()  # Снимаем флаг остановки
            self.start_tshark()
            self.set_button_properties('Стоп', {'text': 'Стоп'})  # Меняем текст на "Стоп"
    
    
    def start_tshark(self):
        logger.info("Начинается попытка запуска tshark")
        if hasattr(self, 'tshark_thread') and isinstance(self.tshark_thread, threading.Thread) and self.tshark_thread.is_alive():
            logger.info("Игнорируем запуск, поскольку поток уже активен")
            return  # Если поток уже запущен, ничего не делаем
        self.tshark_thread = threading.Thread(target=main.tshark_worker, args=(self, config.TSHARK_CMD), daemon=True)
        self.tshark_thread.start()
        logger.info("Создание нового потока tshark завершено")

    def clean_buffers(self, controlled=False):
        if controlled:
            # Здесь можно добавить управляемую очистку (если нужно)
            pass
        else:
            # Оставляем только очистку лога
              print ('здесь могла бы быть ваша реклама')
              pass

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
        # self.clear_text()
        self.text_area.delete('1.0', tk.END)

    def export_csv(self):
        """Экспорт данных в CSV-файл."""
        try:
            # Прямо вызываем класс ExportDialog для начала экспорта
            ExportDialog(self, self.tree)

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
        """Метод для открытия окна редактора"""
        editor = EditorWindow()
        editor.mainloop()

    def show_settings(self):
        # Затем открываем окно настроек
        settings_window = SettingsWindow(self.master)
        # settings_window.grab_set() # Фокусируется на окне настроек

    def show_channel_selector(self):
        """Открывает диалог выбора каналов для сканирования"""
        self.stop_scanning()  # Останавливаем текущее сканирование перед выбором новых каналов

        dialog = ChannelSelectorDialog(
            self,
            config.interface,
            channels=getattr(self, 'prev_channels', None),
            delay_time=getattr(self, 'prev_delay_time', None)
        )

        if dialog.result:
            selected_channels, delay_time = dialog.result
            self.prev_channels = selected_channels
            self.prev_delay_time = delay_time

            if selected_channels:
                self.scan_selected_channels(selected_channels, delay_time)
            else:
                self.add_text("Сканирование не запущено: не выбраны каналы.\n")
   
    def on_channel_indicator_click(self, event=None):
        if not self.scanning_active:
            # Получаем доступные каналы из другого модуля
            available_channels = utils.get_available_channels(config.interface)
            if available_channels:
                self.prev_channels = available_channels
                # Начинаем сканирование по всем доступным каналам с минимальным временем задержки
                self.scan_selected_channels(list(available_channels), delay_time=0.25)
        else:
            self.prev_channels = []
            self.stop_scanning()





    
    def scan_selected_channels(self, channels, delay_time=0.25):
        """Запускает сканирование по выбранным каналам"""
        if not channels:
            self.add_text("Нет каналов для сканирования.\n")
            return

        if len(channels) == 1:
            # Фиксированный канал — просто переключаемся на него
            self.change_channel(channels[0])
            self.scanning_active = True
            self.add_text(f"Фиксированный канал: {channels[0]}\n")
        else:
            # Циклическое сканирование по нескольким каналам
            def run_scanner():
                while self.scanning_active:
                    for channel in channels:
                        start_time = time.time()
                        if not self.scanning_active:
                            break
                        self.change_channel(channel)
                        time.sleep(delay_time)
                        total_time = time.time() - start_time
                        logger.debug(f"Смена канала {channel} заняла {total_time:.2f} сек")

            # Останавливаем предыдущее сканирование, если оно было
            self.stop_scanning()

            self.scanner_thread = threading.Thread(target=run_scanner, daemon=True)
            self.scanning_active = True
            self.scanner_thread.start()
            self.add_text(f"Запуск циклического сканирования по каналам: {channels}\n")
            logger.info(f"Запуск циклического сканирования по каналам: {channels}")

        self.update_scanning_indicator()
    
    def change_channel(self, channel):
        
        try:
            with change_channel_lock:  # Используем контекстный менеджер
                command = ["sudo", "iw", "dev", config.interface, "set", "channel", str(channel)]
                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,  # Вместо encoding="utf-8"
                    timeout=60
                )
                if process.returncode == 0:
                    self.update_channel_indicator()
                else:
                    logger.error(
                        f"Ошибка смены канала {channel}: "
                        f"stdout={process.stdout}, stderr={process.stderr}"
                    )
        except subprocess.TimeoutExpired:
            logger.critical(f"Таймаут при смене канала {channel}")
        except Exception as e:
            logger.critical(f"Неожиданная ошибка: {e}\n{traceback.format_exc()}")
        finally:
            logger.debug(f"change_channel закончен")

    def stop_scanning(self):
        """Останавливает сканирование каналов"""
        self.scanning_active = False

        # Ждём завершения потока сканирования
        if hasattr(self, 'scanner_thread') and self.scanner_thread.is_alive():
            self.scanner_thread.join(timeout=1.0)

        # Обновляем интерфейс
        self.add_text("Процесс сканирования каналов остановлен.\n")
        self.update_scanning_indicator()

            
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

    def update_scanning_indicator(self):
        """Обновляет индикатор сканирования: цвет и текст в зависимости от состояния"""
        if self.scanning_active:
            self.channel_indicator.configure(
                text="scanning",
                fg_color="yellow",
                text_color="black"
            )
        else:
            self.channel_indicator.configure(
                text="no scan",
                fg_color="gray",
                text_color="black"
            )


if __name__ == "__main__":
    app = WifiMonitor()
    app.mainloop()