import logging
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
import threading
import numpy as np
import select

frameBeacon = '0x0008'

# Максимальная длина графика
MAX_POINTS_ON_GRAPH = 1000

# Поток данных из tshark
def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output

# Окно с деталями устройства
class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Мониторинг RSSI")
        
        # Полноценное развертывание окна
        self.attributes('-fullscreen', True)
        self.overrideredirect(True)

        self.paused = False
        self.device_type = ""
        self.last_valid_time = time.time()
        
        # Валидация MAC-адреса
        if not mac_address or not re.match(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$", mac_address):
            self.mac_address = "0A:2C:47:0B:CD:D3"
        else:
            self.mac_address = mac_address
        current_channel_num, frequency = utils.get_current_channel()
        
        # Определение типа устройства
        self.check_device_type()
        
        # Основная команда для мониторинга сигнала (RSSI)
        TSHARK_CMD1 = [
            "tshark", "-i", config.interface,
            "-s", "0",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "wlan_radio.signal_dbm",
            "-Y", f"wlan.ta=={self.mac_address}",
            "-l"
        ]

        # Основной grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)  # Левый блок (таблица + управление)
        self.grid_columnconfigure(1, weight=5)  # Правый блок (график)

        # Левый контейнер (таблица + управление)
        left_frame = tk.Frame(self, padx=5, pady=5)
        left_frame.grid(row=0, column=0, sticky="nsew")

        # Шапка таблицы
        headers = ["Характеристика", "Значение"]
        for col, header in enumerate(headers):
            hdr = tk.Label(
                left_frame, text=header, relief=tk.RAISED,
                padx=8, pady=4, font=("Arial", 11, "bold"),
                bg="#f0f0f0",
                width=15
            )
            hdr.grid(row=0, column=col, sticky="ew")


        rows = [
            ("Адрес устройства", ""),  # Первая строка специально оставляется пустой для текста
            ("Производитель", manufacturer or "N/A"),
            ("Тип устройства", self.device_type),
            ("SSID", self.ssid),          
            ("Канал", str(channel) if current_channel_num else "N/A"),
            ("Частота", f"{frequency}" if frequency else "N/A"),
            ("Текущий кадр", "N/A"),
            ("RSSI", "N/A")
        ]

        self.labels = {}

        # Специально обрабатываем первую ячейку с MAC адресом
        row_idx = 0
        for idx, (key, _) in enumerate(rows):
            # Название строки
            key_label = tk.Label(
                left_frame, text=key, anchor="w", width=15,
                font=("Arial", 10), padx=5
            )
            key_label.grid(row=row_idx+1, column=0, sticky="w", pady=2)

            # Если первая строка - используем виджет Text
            if idx == 0:
                value_widget = tk.Text(left_frame, height=1, width=18, state="normal", font=("Arial", 10), borderwidth=0, highlightthickness=0, background="#EFEFEF")
                value_widget.insert("1.0", self.mac_address)
                value_widget.tag_add("centered", "1.0", "end")
                value_widget.tag_configure("centered", justify="center")
                value_widget.config(state="disabled")
                value_widget.grid(row=row_idx+1, column=1, sticky="w", pady=2)
                # Контекстное меню для копирования
                self.create_context_menu(value_widget)
            else:
                # Остальные строки остаются обычными лейблами
                value_label = tk.Label(
                    left_frame, text=_ or "", anchor="w",
                    font=("Arial", 10), padx=5,
                    width=18
                )
                value_label.grid(row=row_idx+1, column=1, sticky="w", pady=2)
            
            self.labels[key] = value_widget if idx == 0 else value_label
            row_idx += 1

        # Панель управления (под таблицей)
        control_frame = tk.Frame(left_frame, pady=10)
        control_frame.grid(row=len(rows)+1, column=0, columnspan=2, sticky="ew")
        control_frame.columnconfigure(1, weight=2)

        # Кнопка паузы
        self.pause_start_button = tk.Button(
            control_frame, text="Пауза", command=self.toggle_pause,
            font=("Arial", 10), width=10
        )
        self.pause_start_button.grid(row=0, column=0, padx=3, pady=5)

        # Добавляем кнопку закрытия в нижний левый угол
        close_button = tk.Button(self, text="Закрыть", command=self.destroy, font=("Arial", 10))
        close_button.place(relx=0, rely=1, x=10, y=-35, anchor="sw")  # Нижний левый угол

        # Правый контейнер (график)
        right_frame = tk.Frame(self, padx=5, pady=5)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)  # График занимает всю высоту
        right_frame.grid_columnconfigure(0, weight=1)

        # График RSSI
        fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        # self.ax.set_ylabel('RSSI (dBm)', fontsize=10)
        self.canvas = FigureCanvasTkAgg(fig, master=right_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew")

        # Настройка графика
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)
        self.ax.margins(x=0.02)

        self.rssi_values = []
        self.timestamps = []

        # Запуск мониторинга
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.flush_lock = threading.Lock()

        self.start_monitoring()
        self.schedule_plot_update()  # Запускаем периодическую перерисовку
        self.rssi_buffer = []        # Буфер для сглаживания
        self.ema_value = None         # Начальное значение EMA
        self.last_valid_time = time.time()
        self.use_filter_var = tk.BooleanVar(value=True)  # Включено сглаживание
        self.alpha = 0.2            # Коэффициент EMA

    def check_device_type(self):
        """
        Определение типа устройства (AP или STA) и SSID с обработкой различных форматов SSID.
        """
        beacon_cmd = [
            "tshark", "-i", config.interface,
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",
            "-e", "wlan.ssid",
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "100"
        ]
        
        try:
            result = subprocess.run(beacon_cmd, capture_output=True, text=True, timeout=10)
            
            lines = result.stdout.strip().splitlines()
            frames = []
            ssids = set()
            
            for line in lines:
                parts = line.split("\t")
                
                frame_type = parts[0].strip() if len(parts) > 0 else ""
                raw_ssid = parts[1].strip() if len(parts) > 1 else ""
                
                frames.append(frame_type)
                
                if frame_type == "0x0008" and raw_ssid and raw_ssid != "(missing)" and raw_ssid != "":
                    decoded_ssid = None
                    
                    if re.fullmatch(r'[0-9a-fA-F]+', raw_ssid):
                        try:
                            decoded_bytes = bytes.fromhex(raw_ssid)
                            decoded_ssid = decoded_bytes.decode('utf-8', errors='replace')
                        except (ValueError, UnicodeDecodeError) as e:
                            logging.warning(f"Ошибка декодирования hex SSID '{raw_ssid}': {e}")
                            decoded_ssid = None
                    else:
                        decoded_ssid = raw_ssid
                    
                    if decoded_ssid:
                        cleaned_ssid = ''.join(ch for ch in decoded_ssid if ord(ch) >= 32 and ord(ch) <= 126)
                        if cleaned_ssid:
                            ssids.add(cleaned_ssid)
                            
            beacon_count = sum(1 for ft in frames if ft == "0x0008")
            probe_req_count = sum(1 for ft in frames if ft == "0x0004")
            
            if beacon_count > 0:
                self.device_type = "Access Point (AP)"
                self.ssid = next(iter(ssids)) if ssids else "N/A"
            elif probe_req_count > 0:
                self.device_type = "Station (STA)"
                self.ssid = "N/A"
            else:
                self.device_type = "Unknown"
                self.ssid = "N/A"
        
        except subprocess.TimeoutExpired:
            logging.warning("tshark превысил таймаут (5 сек)")
        except Exception as e:
            logging.error(f"Произошла ошибка при обработке данных: {e}")

    def create_context_menu(self, widget):
        # Создание контекстного меню
        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Копировать", command=lambda: self.copy_mac_address(widget))
        widget.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))

    def copy_mac_address(self, widget):
        # Копирует выбранный текст в буфер обмена
        selection = widget.selection_get()
        self.clipboard_clear()
        self.clipboard_append(selection)

    def stop_updating(self):
        """Остановить мониторинг."""
        if self.proc and self.proc.poll() is None:
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
        """Читаем данные пакетно, планируем следующий вызов через 50 мс."""
        if self.paused:
            self.after(50, self._read_next_line)
            return

        try:
            # Собираем до 10 строк за один вызов
            batch = []
            for _ in range(10):
                if select.select([self.proc.stdout], [], [], 0.01)[0]:
                    line = self.proc.stdout.readline()
                    if line:
                        batch.append(line.decode().strip())
                else:
                    break

            # Обрабатываем пакет
            for response in batch:
                if response:
                    self._process_response(response)

            # Планируем следующий вызов через 50 мс
            self.after(50, self._read_next_line)
        except Exception as e:
            print(f"[ERROR] {e}")
            self.after(50, self._read_next_line)

    def _process_response(self, response):
        """
        Новый процесс обработки данных с использованием адаптивного EMA и ограничений шага.
        """
        parts = response.strip().split("\t")
        if len(parts) != 2:
            return  # Пропускаем некорректные строки

        frame_number, rssi_value = parts
        try:
            current_rssi = int(rssi_value)
            if -100 <= current_rssi <= -20:  # Валидный диапазон RSSI
                self.last_valid_time = time.time()

                # Адаптивное EMA
                if self.ema_value is None:
                    self.ema_value = current_rssi
                else:
                    alpha = 0.2  # Базовый коэффициент сглаживания
                    ema_candidate = alpha * current_rssi + (1-alpha)*self.ema_value
                    
                    # Ограничение изменения EMA (защита от больших шагов)
                    step_limit = 5  # Разрешенный максимальный шаг
                    change = ema_candidate - self.ema_value
                    if abs(change) > step_limit:
                        direction = 1 if change > 0 else -1
                        ema_candidate = self.ema_value + direction*step_limit
                        
                    self.ema_value = ema_candidate

                # Диагностика

                # print(f"Raw: {current_rssi}, EMA: {self.ema_value:.2f}, Alpha: {self.alpha:.2f}, Step Limit: {step_limit}")

                # Обновление интерфейса
                self.labels["Текущий кадр"]["text"] = frame_number
                self.labels["RSSI"]["text"] = f"{self.ema_value:.2f} dBm"

                self.rssi_values.append(self.ema_value)
                self.timestamps.append(time.time())

                # Ограничиваем длину буферов
                if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                    self.rssi_values.pop(0)
                    self.timestamps.pop(0)

        except ValueError:
            pass  # Пропускаем неверные данные
        except Exception as e:
            print(f"[ERROR in _process_response] {e}")

    def plot_graph(self):
        """Перерисовка графика."""
        if len(self.timestamps) < 4 or len(self.rssi_values) < 4:  # Минимум 4 точки
            return

        self.ax.clear()
        self.ax.grid(True, linestyle='--', alpha=0.7)

        # Наносим данные на график
        self.ax.plot(self.timestamps, self.rssi_values, color='blue', linewidth=1.5, zorder=10)

        # Настройки оси Y
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)
        self.ax.margins(x=0.02)

        self.canvas.draw_idle()

    def schedule_plot_update(self):
        """Планируем периодическую перерисовку графика каждые 100 мс."""
        self.plot_graph()
        self.after(100, self.schedule_plot_update)

    def on_closing(self):
        """Обработчик закрытия окна."""
        self.stop_updating()
        self.destroy()

# Пример использования (если нужно)
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Скрываем главное окно
    window = SecondWindow(root, mac_address="86:DB:E5:38:96:3C")
    window.protocol("WM_DELETE_WINDOW", window.on_closing)
    root.mainloop()