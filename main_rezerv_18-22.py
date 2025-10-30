import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog
import threading
import time
import signal
import subprocess

import config
# import gui
import utils
from second_window import SecondWindow



from gui_status_bar import StatusBar
from gui_buttons import ButtonPanel
# from gui_treeview import TreeViewManager
from gui_events import EventHandler

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
        ButtonPanel.create_buttons(self, toolbar_container)

        # Новый контейнер для журнала сообщений
        log_container = tk.Frame(main_frame)
        log_container.pack(side=tk.TOP, fill=tk.X)  # Ставим контейнер под центральным контейнером, растянув по ширине

        # Создаем сам журнал сообщений
        self.log_view(log_container)

        # Полоса статуса снизу окна
        StatusBar.status_bar(self)

        # Индикатор состояния потока
        self.indicator = tk.Label(self, text="", background="black", width=7, height=1)
        self.indicator.pack()
        self.update_indicator()

        # Словарь состояний сортировки для каждого столбца
        self._column_sort_state = {}
        for col in ["#1", "#2", "#3", "#4"]:
            self._column_sort_state[col] = True  # По умолчанию сортировка прямого порядка

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
            self.indicator.config(background="#ccc", text='stopped')
        self.after(1000, self.update_indicator)  # Обновляем индикатор каждые 1000 мс
    def tree_view(self, frame):
        # Заголовок дерева
        title_label = tk.Label(frame, text="Обнаруженные уникальные MAC-адреса", font=("TkDefaultFont", 10, 'bold'))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Прокрутка вертикальная для дерева
        scroll_y = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Структура таблицы TreeView
        columns = ("#1", "#2", "#3",
                   "#4")  # Столбцы (#1-MAC адрес, #2-Производитель, #3-RSSI, #4-Время последнего обнаружения)
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

        # Чекбокс для выбора порядка сортировки по первому столбцу
        self.reverse_check_var = tk.BooleanVar(value=False)
        check_box = tk.Checkbutton(frame, text="Сортировка по последнему октету", variable=self.reverse_check_var)
        check_box.place(in_=title_label, relx=1.0, rely=0.0, anchor="ne", x=300, y=0)  # Рядом с заголовком



    def log_view(self, frame):
        # Текстовая область для журналов и сообщений
        self.text_area = scrolledtext.ScrolledText(frame, wrap=tk.NONE, height=6)  # Ограничиваем высоту в 6 строк
        self.text_area.pack(fill=tk.BOTH, expand=True)  # Растергиваем по ширине и занимаем весь контейнер

    # Обработчик двойного клика мыши по устройству
    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            # Остановка сканирования
            config._stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:

            # Остановка сканирования
            config._stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток


            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства


    def refresh_status(self):     # Функция для обновления полосы статуса

        total_devices = len(config._last_seen)
        devices_in_white_list = sum(1 for mac in config._last_seen if mac in config._whitelist)
        config.mode = utils.get_wlan_mode(config.interface)

        if len(self.status_text.get(1.0, tk.END)) == 00:
            self.status_text.delete('0.0', tk.END)
            self.status_text.insert(tk.END, status_message)
            print('было пусто')


        status_message = f"{config.interface}: {config.mode} mode.  | Найдено: {total_devices}"
        self.status_text.replace(1.0, tk.END,status_message)


        if config.mode != 'Monitor':  # Выделяем красным текущий режим
            self.status_text.tag_add("red", '1.6', '1.20')
            self.status_text.tag_config("red", foreground="red")
            self.status_text.config(state=tk.DISABLED)
        else:
            new_props = {'relief': 'sunken', 'state': 'disabled'}
            ButtonPanel.set_button_properties(self, 'turn ON monitor mode', new_props)
            # self.status_text.delete('0.0', tk.END)
            # self.status_text.insert(tk.END, status_message)
        # after_id = self.after(2000, self.refresh_status)



    # Функционал для каждой кнопки
    def toggle_scanning(self):
        """Начало/остановка сканирования"""

        if hasattr(self, 'tshark_thread') and self.tshark_thread.is_alive():
            # Остановка сканирования
            config._stop.set()  # Устанавливаем флаг остановки
            self.tshark_thread.join()  # Ждём завершения потока
            del self.tshark_thread  # Удаляем ссылку на поток
        else:
            # Начало сканирования
            config._stop.clear()  # Снимаем флаг остановки
            self.start_tshark()

    def start_tshark(self):
        """Запуск потока сканирования"""
        self.tshark_thread = threading.Thread(target=tshark_worker, args=(self, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        self.tshark_thread.start()

    def switch_to_monitor_mode(self):
        """Перевод интерфейса в мониторный режим"""
        # password = simpledialog.askstring("Пароль sudo", "Введите пароль sudo:", show="*")
        password = 'kali'
        if password is not None and len(password.strip()) > 0:
            success = utils.enable_monitor_mode(config.interface, password)
            if success:
                self.refresh_status()
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


    def sort_column(self, column_id):
        # Текущий порядок сортировки для данного столбца
        ascending_order = self._column_sort_state.get(column_id, True)

        # Инвертируем порядок сортировки
        self._column_sort_state[column_id] = not ascending_order

        items = list(self.tree.get_children())
        try:
            # Применяем сортировку
            if column_id == '#3':  # Числовой столбец (RSSI)
                items.sort(key=lambda x: float(self.tree.set(x, column_id)), reverse=not ascending_order)
            elif column_id == '#1':  # Первый столбец (MAC-адреса)
                items.sort(key=lambda x: self.tree.set(x, column_id), reverse=not ascending_order)
            else:
                items.sort(key=lambda x: str.lower(self.tree.set(x, column_id)), reverse=not ascending_order)
        except ValueError:
            items.sort(key=lambda x: str.lower(self.tree.set(x, column_id)), reverse=not ascending_order)

        # Обновляем представление
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
        self.refresh_status()


    def reverse_sort_by_first_column(self):
        items = list(self.tree.get_children())
        try:
            # Сортируем по MAC-адресу в обратном порядке
            items.sort(key=lambda x: self.tree.set(x, '#1'), reverse=True)
        except ValueError:
            # Если невозможно выполнить числовую сортировку, сортируем строковым методом
            items.sort(key=lambda x: str.lower(self.tree.set(x, '#1')), reverse=True)

        # Переставляем элементы в дереве
        for idx, item in enumerate(items):
            self.tree.move(item, '', idx)

    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства

def tshark_worker(root, cmd, ttl):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    except Exception as e:
        root.add_text(f"Ошибка при старте tshark: {e}")
        config.config._stop.set()
        return

    def stderr_reader():
        for line in proc.stderr:
            root.add_text(f"{line.rstrip()}")

    threading.Thread(target=stderr_reader, daemon=True).start()

    try:
        for raw in proc.stdout:
            if config._stop.is_set():
                break
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parts = raw.split("\t")
            if len(parts) < 2:
                continue
            raw_time = parts[0]
            mac = parts[1] if len(parts) > 1 else ""
            rssi = parts[2] if len(parts) > 2 else ""
            subtype = parts[3] if len(parts) > 3 else ""

            mac_n = utils.normalize_mac(mac)
            if not mac_n:
                continue

            if config._whitelist:
                allowed = mac_n not in config._whitelist
            else:
                allowed = True

            now = time.time()
            with config._seen_lock:
                last = config._last_seen.get(mac_n)
                if last is not None:
                    if ttl is None:
                        continue
                    if now - last <= ttl:
                        continue
                config._last_seen[mac_n] = now
                config._seen_count[mac_n] = config._seen_count.get(mac_n, 0) + 1

            pretty_time = utils.parse_time_epoch(raw_time)
            mac = utils.lookup_vendor_db(mac)
            if len(mac) <= 50:
                dop = 50 - len(mac)
                mac = mac + ' ' * dop
            else:
                mac = mac[:50]

            root.update_tree(mac_n, utils.lookup_vendor_db(mac_n, config.DB_PATH, False), rssi, pretty_time)
            root.add_text(f"{mac} | {rssi} dBi | {utils.decode_wlan_type_subtype(subtype)} | {pretty_time}")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass

def main():
    global WHITELIST_PATH, SEEN_TTL_SECONDS
    root = App()

    # cmd = config.TSHARK_CMD
    WHITELIST_PATH = config.WHITELIST_PATH
    SEEN_TTL_SECONDS = config.SEEN_TTL_SECONDS

    if WHITELIST_PATH:
        with config._whitelist_lock:
            config._whitelist.clear()
            config._whitelist.update(utils.load_whitelist(WHITELIST_PATH))

    try:
        signal.signal(signal.SIGHUP, utils.handle_sighup)
    except Exception:
        pass

    if SEEN_TTL_SECONDS is not None:
        t = threading.Thread(target=utils.seen_cleaner, args=(SEEN_TTL_SECONDS,), daemon=True)
        t.start()

    if utils.get_wlan_mode(config.interface) == 'Monitor':
        # Запускаем поток и передаем ссылку на него в класс App
        tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD, SEEN_TTL_SECONDS), daemon=True)
        tshark_thread.start()
        root.tshark_thread = tshark_thread  # Присваиваем ссылку на поток в экземпляр App

    root.mainloop()

if __name__ == "__main__":
    main()