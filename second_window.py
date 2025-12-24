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
import select

frameBeacon = '0x0008'


# Максимальная длина графика
MAX_POINTS_ON_GRAPH = 100

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
        self.title("Детали устройства")
        
        # Фиксированный размер окна 800x480
        self.geometry("800x480")
        self.maxsize(800, 480)
        self.minsize(800, 480)

        self.paused = False
        self.ema_value = None
        self.device_type = ""
        self.last_valid_time = time.time()

        # Валидация MAC-адреса
        if not mac_address or not re.match(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$", mac_address):
            self.mac_address = "2C:57:41:83:32:01"
        else:
            self.mac_address = mac_address

        # Получаем информацию о канале Wi-Fi
        # wifi_info = os.popen(f"iw dev wlan1 info").read()
        # current_channel_num, frequency = utils.parse_wifi_info(wifi_info)
        # if current_channel_num != channel:
        #     print('Текущий канал не совпадает с переданным!')

        current_channel_num, frequency = utils.get_current_channel()

        # Основная команда для мониторинга сигнала (RSSI)
        TSHARK_CMD1 = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "wlan_radio.signal_dbm",
            "-Y", f"wlan.ta=={self.mac_address}",
            "-l"
        ]

        # Команда для определения типа устройства (AP или STA)
        self.CHECK_TYPE_CMD = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "100",
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
                bg="#f0f0f0"
            )
            hdr.grid(row=0, column=col, sticky="ew")

        # Тело таблицы (компактное)
        rows = [
            ("Адрес устройства", self.mac_address),
            ("Производитель", manufacturer or "N/A"),
            ("Тип устройства", ""),
            ("SSID", "N/A"),          # ← Новая строка
            ("Канал", str(channel) if current_channel_num else "N/A"),
            ("Частота", f"{frequency}" if frequency else "N/A"),
            ("Текущий кадр", "N/A"),
            ("RSSI", "N/A")
        ]

        self.labels = {}  # Храним ссылки на лейблы значений

        for idx, (key, value) in enumerate(rows):
            # Название строки
            key_label = tk.Label(
                left_frame, text=key, anchor="w",
                font=("Arial", 10), padx=5
            )
            key_label.grid(row=idx+1, column=0, sticky="w", pady=2)

            # Значение
            value_label = tk.Label(
                left_frame, text=value, anchor="w",
                font=("Arial", 10), padx=5
            )
            value_label.grid(row=idx+1, column=1, sticky="w", pady=2)
            
            self.labels[key] = value_label

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

        # Параметры сглаживания
        self.alpha = 0.2
        self.use_filter_var = tk.BooleanVar(value=True)

        # Регулятор сглаживания
        self.alpha_slider = tk.Scale(
            control_frame, from_=0.01, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, label="Сглаживание:", length=150,
            font=("Arial", 9)
        )
        self.alpha_slider.set(self.alpha)
        self.alpha_slider.grid(row=0, column=1, sticky="ew", padx=3, pady=5)
        self.alpha_slider.bind("<ButtonRelease-1>", self.update_alpha)

        # Флажок сглаживания
        self.filter_toggle = tk.Checkbutton(
            control_frame, text="Вкл.", variable=self.use_filter_var,
            command=self.toggle_filter, font=("Arial", 10)
        )
        self.filter_toggle.grid(row=0, column=2, padx=3, pady=5)

        # Правый контейнер (график)
        right_frame = tk.Frame(self, padx=5, pady=5)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)  # График занимает всю высоту
        right_frame.grid_columnconfigure(0, weight=1)

        # График RSSI
        fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_ylabel('RSSI (dBm)', fontsize=10)
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
        self.start_monitoring()

        # Определение типа устройства
        self.check_device_type()
    

    def check_device_type(self):
        """
        Определение типа устройства (AP или STA) и SSID с обработкой различных форматов SSID.
        """
        beacon_cmd = [
            "tshark", "-i", "wlan1",
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",
            "-e", "wlan.ssid",
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "100"
        ]
        
        try:
            result = subprocess.run(beacon_cmd, capture_output=True, text=True, timeout=5)
            
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
            probe_req_count = sum(1 for ft in frames if ft == "0x04")
            
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
        """Читаем одну строку и планируем следующий вызов."""
        if self.paused:
            self.after(1000, self._read_next_line)
            return

        try:
            # Проверяем наличие данных (неблокирующий вызов)
            if select.select([self.proc.stdout], [], [], 0.1)[0]:
                line = self.proc.stdout.readline()
                if line:
                    response = line.decode().strip()
                    if response:
                        self._process_response(response)
            else:
                # Нет данных — ждём 100 мс
                self.after(100, self._read_next_line)
                return
        except Exception as e:
            print(f"[ERROR] {e}")

        self.after(100, self._read_next_line)

    def _process_response(self, response):
        """Обрабатываем одну строку данных."""
        parts = response.strip().split("\t")
        if len(parts) != 2:
            return  # Пропускаем некорректные строки

        frame_number, rssi_value = parts

        try:
            current_rssi = float(rssi_value)
            if -100 <= current_rssi <= -20:
                self.last_valid_time = time.time()

                # Сглаживание
                if self.use_filter_var.get():
                    if self.ema_value is None:
                        self.ema_value = current_rssi
                    else:
                        self.ema_value = (self.alpha * current_rssi +
                                         (1 - self.alpha) * self.ema_value)
                    display_rssi = self.ema_value
                else:
                    display_rssi = current_rssi

                # Обновляем виджеты
                self.labels["Текущий кадр"]["text"] = frame_number
                self.labels["RSSI"]["text"] = f"{display_rssi:.2f} dBm"
                self.rssi_values.append(display_rssi)
                self.timestamps.append(time.time())


                # Ограничиваем длину буфера
                if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                    self.rssi_values.pop(0)
                    self.timestamps.pop(0)

                self.plot_graph()
        except ValueError:
            pass  # Пропускаем некорректные значения RSSI


    def plot_graph(self):
        """Обновляем график RSSI."""
        if len(self.timestamps) < 2 or len(self.rssi_values) < 2:
            return

        self.ax.clear()
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_ylabel('RSSI (dBm)', fontsize=10)
        self.ax.plot(self.timestamps, self.rssi_values, color='blue', linewidth=1)


        # Настройка осей
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)
        self.ax.margins(x=0.02)

        self.canvas.draw_idle()

    def update_alpha(self, event=None):
        """Обновление коэффициента сглаживания."""
        self.alpha = self.alpha_slider.get()

    def toggle_filter(self):
        """Включение/выключение сглаживания."""
        pass  # Логика уже в _process_response

    def destroy(self):
        """Завершение программы."""
        self.stop_updating()
        time.sleep(0.5)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            time.sleep(0.3)
            if self.proc.poll() is None:
                self.proc.kill()
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