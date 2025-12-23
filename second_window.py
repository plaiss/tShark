import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import time
import config
import os
import re
import utils

# Максимальная длина графика
MAX_POINTS_ON_GRAPH = 100

# Поток данных из tshark
def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output

# # Извлечение уровня сигнала (RSSI)
# def extract_rssi(data):
#     parts = data.strip().split("\t")
#     if len(parts) >= 2:
#         return parts[1]  # Уровень сигнала (RSSI)
#     return "-"

# Окно с деталями устройства
class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Детали устройства")
        
        # Фиксированный размер окна 800x480
        self.geometry("800x480")
        self.maxsize(800, 480)
        self.minsize(800, 480)

        # ИНИЦИАЛИЗИРУЕМ paused ЗДЕСЬ!
        self.paused = False  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
        
        # MAC-адрес устройства
        self.mac_address = mac_address or "2C:57:41:83:32:01"

        # Получаем информацию о канале Wi-Fi
        wifi_info = os.popen(f"iw dev wlan1 info").read()
        channel_num, frequency = utils.parse_wifi_info(wifi_info)
        if channel_num != channel:
            print('Текущий канал не совпадает с переданным!')

        # Основная команда для мониторинга сигнала (RSSI)
        TSHARK_CMD1 = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "frame.number",  # Номер кадра
            "-e", "wlan_radio.signal_dbm",  # RSSI
            "-Y", f"wlan.ta=={self.mac_address}",
            "-l"  # Буферизация
        ]

        # Команда для определения типа устройства (AP или STA)
        self.CHECK_TYPE_CMD = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",  # Поле типа фрейма
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "100",  # Число пакетов для анализа
            "-l"  # Буферизация
        ]
        # print(self.CHECK_TYPE_CMD)
        # Атрибуты
        self.ema_value = None  # Экспоненциальная средняя
        self.device_type = ""  # Тип устройства (будет установлен позже)
        self.last_valid_time = time.time()

        # Основной grid для окна
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)  # Левый фрейм (75%)
        self.grid_columnconfigure(1, weight=5)  # Правый фрейм (125%)

        # Левый контейнер с таблицей
        left_frame = tk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(1, weight=1)

        # Шапка таблицы
        headers = ["Характеристика", "Значение"]
        for col, header in enumerate(headers):
            hdr = tk.Label(left_frame, text=header, relief=tk.RAISED, padx=5, pady=3, font=("Arial", 10, "bold"))
            hdr.grid(row=0, column=col, sticky="ew")

        # Тело таблицы
        rows = [
            ("Адрес устройства", mac_address),
            ("Производитель", manufacturer),
            ("Тип устройства", ""),  # Будет установлено позже
            ("Канал", channel),
            ("Частота", frequency),
            ("Последний кадр", "N/A"),  # Номер кадра
            ("Задержка", "N/A"),      # Задержка
            ("RSSI", "N/A")          # Добавляем строку для RSSI
        ]

        for idx, (key, _) in enumerate(rows):
            # Название строки
            key_label = tk.Label(left_frame, text=key, anchor="w", font=("Arial", 10))
            key_label.grid(row=idx + 1, column=0, sticky="w", padx=1, pady=1)

            # Создаём лейбл для отображения значения
            value_label = tk.Label(left_frame, text="", anchor="w", font=("Arial", 10))
            value_label.grid(row=idx + 1, column=1, sticky="ew", padx=1, pady=1)


            # Назначаем лейбл нужной характеристике
            if key == "Тип устройства":
                self.type_device_label = value_label
            elif key == "Последний кадр":
                self.frame_number_label = value_label
            elif key == "Задержка":
                self.delay_label = value_label
            elif key == "RSSI":
                self.rssi_label = value_label
            else:
                setattr(self, f"{key.lower().replace(' ', '_')}_label", value_label)

        # Правый контейнер (график + управление)
        right_frame = tk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        right_frame.grid_rowconfigure(0, weight=7)  # График — 70% высоты
        right_frame.grid_rowconfigure(1, weight=3)  # Панель — 30% высоты
        right_frame.grid_columnconfigure(0, weight=1)

        # График RSSI
        fig = plt.Figure(figsize=(5, 3))
        self.ax = fig.add_subplot(111)
        self.ax.grid(True)
        self.ax.set_ylabel('RSSI (dBm)', fontsize=9)
        self.canvas = FigureCanvasTkAgg(fig, master=right_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        # Настройка сетки графика
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)

        # Данные для графика
        self.rssi_values = []
        self.timestamps = []

        # Параметры сглаживания
        self.alpha = 0.2
        self.use_filter_var = tk.BooleanVar(value=True)

        # Панель управления
        control_frame = tk.Frame(right_frame)
        control_frame.grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        control_frame.grid_columnconfigure(1, weight=2)  # Слайдер занимает больше места

        # Кнопка паузы
        self.pause_start_button = tk.Button(
            control_frame, text="Пауза", command=self.toggle_pause, font=("Arial", 9)
        )
        self.pause_start_button.grid(row=0, column=0, padx=3, pady=3)

        # Регулятор сглаживания
        alpha_slider = tk.Scale(
            control_frame, from_=0.01, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
            label="Сглаживание:", length=150, font=("Arial", 8))
        alpha_slider.set(self.alpha)
        alpha_slider.grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        alpha_slider.bind("<ButtonRelease-1>", lambda e: self.update_alpha())
        

        # Флажок сглаживания
        self.filter_toggle = tk.Checkbutton(
            control_frame, text="Вкл.", variable=self.use_filter_var,
            command=self.toggle_filter, font=("Arial", 9)
        )
        self.filter_toggle.grid(row=0, column=2, padx=3, pady=3)

        # Запуск мониторинга через .after() вместо потока
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.start_monitoring()

        # Определение типа устройства
        self.check_device_type()

    def check_device_type(self):
        """Определение типа устройства (AP или STA)."""
        proc = subprocess.Popen(self.CHECK_TYPE_CMD, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frames = []
        for line in get_data_stream(proc):
            frame_type = line.split()[0]
            frames.append(frame_type)

        # Подсчёт фреймов
        beacon_count = sum(1 for ft in frames if ft.startswith("0x0008"))  # Beacon-фреймы (AP)
        probe_req_count = sum(1 for ft in frames if ft.startswith("0x0004"))  # Probe Request (STA)

        if beacon_count > 0:
            self.device_type = "Access Point (AP)"
        elif probe_req_count > 0:
            self.device_type = "Station (STA)"
        else:
            self.device_type = "Unknown"

        # Обновляем лейбл типа устройства
        self.type_device_label['text'] = self.device_type

        # Завершаем процесс
        proc.wait()

    def stop_updating(self):
        """Остановить мониторинг."""
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()

    def toggle_pause(self):
        """Переключение режима паузы."""
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
        else:
            self.pause_start_button.config(text="Пауза")

    def start_monitoring(self):
        """Запускаем мониторинг через .after()."""
        self._read_next_line()

    def _read_next_line(self):
        """Читаем одну строку и планируем следующий вызов."""
        if self.paused:
            self.after(1000, self._read_next_line)  # Проверяем раз в секунду
            return

        try:
            # Читаем одну строку (не блокируем)
            line = self.proc.stdout.readline()
            if line:
                response = line.decode().strip()
                if response:
                    self._process_response(response)
            else:
                # Конец потока
                self.after(100, self._read_next_line)
                return
        except Exception as e:
            print(f"[ERROR] {e}")

        # Планируем следующий вызов через 100 мс
        self.after(100, self._read_next_line)

    def _process_response(self, response):
        """Обрабатываем одну строку данных."""
        parts = response.strip().split("\t")
        if len(parts) != 2:
            print(f"[DEBUG] Недостаточно полей: {response}")
            return

        frame_number = parts[0]
        rssi_value = parts[1].strip()

        try:
            current_rssi = float(rssi_value)
            if -100 <= current_rssi <= -20:
                self.last_valid_time = time.time()
                self.delay_label["text"] = ""


                # Сглаживание
                if self.use_filter_var.get():
                    if self.ema_value is None:
                        self.ema_value = current_rssi
                    else:
                        self.ema_value = self.alpha * current_rssi + (1 - self.alpha) * self.ema_value
                    display_rssi = self.ema_value
                else:
                    display_rssi = current_rssi

                # Обновляем виджеты (в основном потоке!)
                self.frame_number_label["text"] = frame_number
                self.rssi_label["text"] = f"{display_rssi:.2f} dBm"
                self.rssi_values.append(display_rssi)
                self.timestamps.append(time.time())


                # Ограничиваем длину
                if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                    self.rssi_values.pop(0)
                    self.timestamps.pop(0)

                self.plot_graph()
            else:
                delay_seconds = int(time.time() - self.last_valid_time)
                self.delay_label["text"] = f"{delay_seconds} сек."
        except ValueError:
            print(f"[DEBUG] Некорректное значение RSSI: '{rssi_value}'")

    def plot_graph(self):
        """График RSSI."""
        if len(self.timestamps) < 2 or len(self.rssi_values) < 2:
            return  # Не рисуем, если мало точек

        self.ax.clear()
        self.ax.grid(True)
        self.ax.set_ylabel('RSSI (dBm)', fontsize=9)
        self.ax.plot(self.timestamps, self.rssi_values, color='blue')

        # Настройка сетки
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)


        # Скрываем ось X
        self.ax.xaxis.set_visible(False)
        self.canvas.draw_idle()

    def update_alpha(self):
        """Обновление коэффициента сглаживания."""
        widget = self.winfo_children()[0].winfo_children()[1]  # Находим слайдер
        if isinstance(widget, tk.Scale):
            self.alpha = widget.get()

    def toggle_filter(self):
        """Включение/выключение сглаживания."""
        pass  # Логика уже реализована через self.use_filter_var

    def destroy(self):
        """Завершение программы."""
        self.stop_updating()
        plt.close('all')
        super().destroy()
        if __name__ == "__main__":
            self.parent.destroy()

# Запуск программы
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root)
    root.withdraw()  # Скрываем главное окно
    app.mainloop()
