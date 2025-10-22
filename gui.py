import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog

import config
import main
import utils

_is_running = False  # Глобальная переменная для отслеживания состояния процесса

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Настройка главного окна приложения
        self.title("WiFi Monitor")
        self.minsize(width=1380, height=768)
        self.center_window()  # Центрируем окно

        # Главный фрейм для всего интерфейса
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Панель для разделяемых областей верхнего и нижнего уровня
        container = tk.PanedWindow(main_frame, orient=tk.VERTICAL)
        container.pack(fill=tk.BOTH, expand=True)

        # Верхняя секция: дерево устройств слева
        upper_frame = tk.Frame(container)
        container.add(upper_frame)

        # Нижняя секция: текстовая область для сообщений справа
        lower_frame = tk.Frame(container)
        container.add(lower_frame)

        # Фрейм для отображения деревьев устройств
        tree_frame = tk.Frame(upper_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Надпись над деревом устройств
        title_label = tk.Label(tree_frame, text="Обнаруженные уникальные MAC-адреса",
                               font=("TkDefaultFont", 10, 'bold'))
        title_label.pack(side=tk.TOP, anchor="w", pady=5)

        # Прокрутка вертикальная для дерева
        scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Структура таблицы TreeView
        columns = ("#1", "#2", "#3", "#4")  # Макет столбцов (#1-MAC адрес, #2-Производитель, #3-RSSI, #4-Время последнего обнаружения)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scroll_y.set)

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

        # Коннект прокрутки с деревом
        scroll_y.config(command=self.tree.yview)

        # Боковая панель с кнопками управления
        button_frame = tk.Frame(upper_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Создаем панель с кнопками
        button_panel = tk.Frame(button_frame)
        button_panel.pack(fill=tk.Y)

        # Список кнопок
        buttons = [
            "Запустить сканирование",
            "Мониторинг",
            "Сброс данных",
            "Экспорт в CSV",
            "Открыть белый список",
            "Показать детали",
            "2 Имя"
        ]

        # Размещаем кнопки на панели
        for btn_name in buttons:
            btn = tk.Button(button_panel, text=btn_name, command=lambda b=btn_name: self.on_button_click(b))
            btn.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Текстовая область внизу для журналов и сообщений
        self.text_area = scrolledtext.ScrolledText(lower_frame, wrap=tk.NONE, height=6)  # Высота в 6 строк
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # Полоса статуса снизу окна
        self.status_label = tk.Text(self, bd=0, relief=tk.SUNKEN, height=1, font=("TkDefaultFont", 10))  # Высота в одну строку
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # Централизация окна
    def center_window(self):
        w_width = 1380
        w_height = 768
        s_width = self.winfo_screenwidth()
        s_height = self.winfo_screenheight()
        x = (s_width - w_width) // 2
        y = (s_height - w_height) // 2
        self.geometry(f"{w_width}x{w_height}+{x}+{y}")

    # Обработка события двойного клика мыши по устройству
    def on_device_double_click(self, event):
        selected_item = self.tree.focus()
        data = self.tree.item(selected_item)["values"]  # Получаем выбранные значения
        if data:
            self.open_second_window(data=data)  # Открываем новое окно с деталями устройства

    # Реакция на нажатие кнопок
    def on_button_click(self, button_name):
        global _is_running  # Работаем с глобальной переменной состояния
        if button_name == 'Запустить сканирование':
            if _is_running:
                # Процесс уже запущен, останавливаем его
                config._stop.set()  # Устанавливаем сигнал остановки
                _is_running = False
                self.change_button_state('Запустить сканирование')  # Меняем название кнопки обратно
            else:
                # Начинаем сканирование
                tshark_thread = main.threading.Thread(target=main.tshark_worker, args=(self, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
                tshark_thread.start()
                _is_running = True
                self.change_button_state('Остановить сканирование')  # Меняем название кнопки
        elif button_name == 'Мониторинг':
            # Ваш старый код остался прежним...
            pass
        elif button_name == 'Сброс данных':
            # Ваш старый код остался прежним...
            pass
        elif button_name == 'Экспорт в CSV':
            # Ваш старый код остался прежним...
            pass
        elif button_name == 'Открыть белый список':
            # Ваш старый код остался прежним...
            pass
        elif button_name == 'Показать детали':
            # Ваш старый код остался прежним...
            pass
        elif button_name == '2 Имя':
            # Ваш старый код остался прежним...
            pass

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

    # Метод для изменения названия кнопки
    def change_button_state(self, new_text):
        # Поиск нужной кнопки среди виджетов
        for widget in self.children.values():
            if isinstance(widget, tk.Frame):
                for child_widget in widget.children.values():
                    if isinstance(child_widget, tk.Button) and child_widget["text"] == 'Запустить сканирование':
                        child_widget.config(text=new_text)
                        break

    # Открывает второе окно с информацией о устройстве
    def open_second_window(self, data=None):
        SecondWindow(self, data=data)

    # Обновляет полосу статуса
    def update_status(self, total_devices, ignored_devices):
        status_message = f"{config.interface}: {config.mode} режим | Найдено: {total_devices}, Белый список: Всего {len(config._whitelist)}, Игнорировано: {ignored_devices}"
        self.status_label.delete('1.0', tk.END)
        self.status_label.insert(tk.END, status_message)

        if config.mode != 'Monitor':  # Выделяем красный цветом текущий режим
            self.status_label.tag_add("red", '1.6', '1.20')
            self.status_label.tag_config("red", foreground="red")
            self.status_label.config(state=tk.DISABLED)


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