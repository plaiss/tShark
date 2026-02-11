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
import threading
import numpy as np
import select
from collections import deque
import shutil
import signal

# Конфигурируемые параметры
MAX_POINTS_ON_GRAPH = 1000
EMA_ALPHA = 0.2
TSHARK_TIMEOUT_SEC = 60
UPDATE_INTERVAL_MS = 50  # Чтение данных
PLOT_UPDATE_INTERVAL_MS = 100  # Перерисовка графика

frameBeacon = '0x0008'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("rssi_monitor.log"),
        logging.StreamHandler()
    ]
)

def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output

class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None):
        super().__init__(parent)
        self.geometry("800x480")
        self.parent = parent
        self.title("Мониторинг RSSI")

        self.paused = False
        self.device_type = ""
        self.last_valid_time = time.time()
        self.ssid = "N/A"

        # Валидация MAC-адреса
        if not mac_address or not re.match(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$", mac_address):
            self.mac_address = "0A:2C:47:0B:CD:D3"
            logging.warning(f"Некорректный MAC-адрес. Используем дефолтный: {self.mac_address}")
        else:
            self.mac_address = mac_address

        # Проверка наличия tshark
        if not shutil.which("tshark"):
            logging.error("tshark не установлен! Завершаем работу.")
            self.destroy()
            return

        # Проверка интерфейса
        if not os.path.exists(f"/sys/class/net/{config.interface}"):
            logging.error(f"Интерфейс {config.interface} не найден!")
            self.destroy()
            return

        # Основной поток мониторинга RSSI
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
            ("Адрес устройства", ""),
            ("Производитель", manufacturer or "N/A"),
            ("Тип устройства", "N/A"),
            ("SSID", "N/A"),
            ("Канал", str(channel) if channel else "N/A"),
            ("Текущий кадр", "N/A"),
            ("RSSI", "N/A")
        ]

        self.labels = {}

        # Обработка первой строки (MAC-адрес)
        row_idx = 0
        for idx, (key, _) in enumerate(rows):
            key_label = tk.Label(
                left_frame, text=key, anchor="w", width=15,
                font=("Arial", 10), padx=5
            )
            key_label.grid(row=row_idx+1, column=0, sticky="w", pady=2)

            if idx == 0:
                value_widget = tk.Text(left_frame, height=1, width=18, state="normal", font=("Arial", 10), borderwidth=0, highlightthickness=0, background="#EFEFEF")
                value_widget.insert("1.0", self.mac_address)
                value_widget.tag_add("centered", "1.0", "end")
                value_widget.tag_configure("centered", justify="center")
                value_widget.config(state="disabled")
                value_widget.grid(row=row_idx+1, column=1, sticky="w", pady=2)
                self.create_context_menu(value_widget)
            else:
                value_label = tk.Label(
                    left_frame, text=_ or "", anchor="w",
                    font=("Arial", 10), padx=5,
                    width=18
                )
                value_label.grid(row=row_idx+1, column=1, sticky="w", pady=2)
            
            self.labels[key] = value_widget if idx == 0 else value_label
            row_idx += 1

        # Панель управления
        control_frame = tk.Frame(left_frame, pady=10)
        control_frame.grid(row=len(rows)+1, column=0, columnspan=2, sticky="ew")
        control_frame.columnconfigure(1, weight=2)

        self.pause_start_button = tk.Button(
            control_frame, text="Пауза", command=self.toggle_pause,
            font=("Arial", 10), width=10
        )
        self.pause_start_button.grid(row=0, column=0, padx=3, pady=5)

        # Кнопка закрытия
        close_button = tk.Button(self, text="Закрыть", command=self.on_closing, font=("Arial", 10))
        close_button.place(relx=0, rely=1, x=10, y=-35, anchor="sw")

        # Правый контейнер (график)
        right_frame = tk.Frame(self, padx=5, pady=5)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.canvas = FigureCanvasTkAgg(fig, master=right_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew")

        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)



        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)
        self.ax.margins(x=0.02)


        self.rssi_values = deque(maxlen=MAX_POINTS_ON_GRAPH)
        self.timestamps = deque(maxlen=MAX_POINTS_ON_GRAPH)


        # Статусная метка
        self.status_label = tk.Label(
            left_frame, text="Определение типа устройства...",
            fg="orange", font=("Arial", 9), anchor="w"
        )
        self.status_label.grid(row=len(rows)+2, column=0, columnspan=2, sticky="w", pady=2)

        # Запуск мониторинга
        try:
            self.proc = subprocess.Popen(
                TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=1, text=True
            )
        except Exception as e:
            logging.error(f"Не удалось запустить tshark: {e}")
            self.destroy()
            return

        self.flush_lock = threading.Lock()
        self.rssi_buffer = []
        self.ema_value = None
        self.use_filter_var = tk.BooleanVar(value=True)
        self.alpha = EMA_ALPHA


        threading.Thread(target=self.delayed_device_check, daemon=True).start()
        self.start_monitoring()
        self.schedule_plot_update()


    def delayed_device_check(self):
        """Определяет тип устройства и SSID в фоновом потоке."""
        self.check_device_type()
        self.after(0, self.update_ui_after_check)

    def update_ui_after_check(self):
        """Обновляет интерфейс после определения типа устройства."""
        self.labels["Тип устройства"]["text"] = self.device_type
        self.labels["SSID"]["text"] = self.ssid
        self.status_label.config(text="Готово", fg="green")

    def check_device_type(self):
        """Определяет тип устройства (AP/STA) и SSID."""
        beacon_cmd = [
            "tshark", "-i", config.interface,
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",
            "-e", "wlan.ssid",
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "50"
        ]
        try:
            result = subprocess.run(beacon_cmd, capture_output=True, text=True, timeout=TSHARK_TIMEOUT_SEC)
            lines = result.stdout.strip().splitlines()
            frames = []
            ssids = set()

            for line in lines:
                parts = line.split("\t")
                frame_type = parts[0].strip() if len(parts) > 0 else ""
                raw_ssid = parts[1].strip() if len(parts) > 1 else ""

                frames.append(frame_type)

                if frame_type == "0x0008" and raw_ssid and raw_ssid not in ("(missing)", ""):
                    decoded_ssid = None
                    if re.fullmatch(r'[0-9a-fA-F]+', raw_ssid):
                        try:
                            decoded_bytes = bytes.fromhex(raw_ssid)
                            decoded_ssid = decoded_bytes.decode('utf-8', errors='replace')
                        except (ValueError, UnicodeDecodeError) as e:
                            logging.warning(f"Ошибка декодирования hex SSID '{raw_ssid}': {e}")
                    else:
                        decoded_ssid = raw_ssid

                    if decoded_ssid:
                        cleaned_ssid = ''.join(ch for ch in decoded_ssid if ch.isprintable() and ord(ch) < 127)
                        if cleaned_ssid.strip():
                            ssids.add(cleaned_ssid.strip())

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
            logging.warning("tshark превысил таймаут")
            self.device_type = "Unknown (timeout)"
            self.ssid = "N/A"
        except Exception as e:
            logging.error(f"Ошибка при определении типа устройства: {e}")
            self.device_type = "Error"
            self.ssid = "N/A"

    def create_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Копировать", command=lambda: self.copy_mac_address(widget))
        widget.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))


    def copy_mac_address(self, widget):
        try:
            selection = widget.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(selection)
        except:
            pass

    def stop_updating(self):
        """Останавливает мониторинг и очищает ресурсы."""
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logging.warning("Процесс tshark не завершился за 5 сек, принудительно закрываем")
        if self.proc.stdout:
            self.proc.stdout.close()
        logging.info("Мониторинг остановлен")


    def toggle_pause(self):
        """Переключение режима паузы."""
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
        else:
            self.pause_start_button.config(text="Пауза")


    def start_monitoring(self):
        """Запускает мониторинг."""
        self._read_next_line()


    def _read_next_line(self):
        """Читает данные из tshark."""
        if self.paused:
            self.after(UPDATE_INTERVAL_MS, self._read_next_line)
            return

        if self.proc.poll() is not None:
            logging.info("Процесс tshark завершён")
            return

        try:
            batch = []
            while len(batch) < 10 and select.select([self.proc.stdout], [], [], 0.01)[0]:
                line = self.proc.stdout.readline()
                if line:
                    batch.append(line.strip())


            for response in batch:
                if response:
                    self._process_response(response)


            self.after(UPDATE_INTERVAL_MS, self._read_next_line)
        except Exception as e:
            logging.error(f"Ошибка чтения данных: {e}")
            self.after(UPDATE_INTERVAL_MS, self._read_next_line)


    def _process_response(self, response):
        """Обрабатывает строку данных."""
        parts = response.strip().split("\t")
        if len(parts) != 2:
            return

        frame_number, rssi_value = parts
        try:
            current_rssi = int(rssi_value)
            if -100 <= current_rssi <= -20:
                self.last_valid_time = time.time()

                # EMA с ограничением шага
                if self.ema_value is None:
                    self.ema_value = current_rssi
                else:
                    # Ограничение шага изменения EMA
                    delta = current_rssi - self.ema_value
                    if abs(delta) > 10:  # Макс. шаг ±10 dBm
                        current_rssi = self.ema_value + (10 if delta > 0 else -10)


                    self.ema_value = self.alpha * current_rssi + (1 - self.alpha) * self.ema_value


            # Добавляем в буфер для сглаживания
            self.rssi_buffer.append(self.ema_value)
            if len(self.rssi_buffer) > 5:
                smoothed_rssi = np.mean(self.rssi_buffer[-5:])
                self.rssi_buffer = self.rssi_buffer[-5:]  # Сохраняем последние 5
            else:
                smoothed_rssi = self.ema_value


            # Обновляем метки
            self.labels["Текущий кадр"]["text"] = frame_number
            self.labels["RSSI"]["text"] = f"{int(smoothed_rssi)} dBm"


            # Сохраняем точку для графика
            self.timestamps.append(time.time())
            self.rssi_values.append(smoothed_rssi)


        except ValueError:
            logging.debug(f"Не удалось преобразовать RSSI: {rssi_value}")


    def schedule_plot_update(self):
        """Планирует обновление графика."""
        self._update_plot()
        self.after(PLOT_UPDATE_INTERVAL_MS, self.schedule_plot_update)



    def _update_plot(self):
        """Перерисовывает график с прокруткой вправо, заливкой сверху и имитацией точек при простое."""
        if not self.rssi_values:
            return

        self.ax.clear()
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_ylim(-100, -20)
        self.ax.xaxis.set_visible(False)
        self.ax.margins(x=0.02)

        last_time = self.timestamps[-1]
        x_data = [last_time - t for t in self.timestamps]

        # Линия графика
        line = self.ax.plot(x_data, self.rssi_values, color='blue', linewidth=1.5, zorder=2)

        # Заливка от линии до -20 dBm (сверху)
        # self.ax.fill_between(
        #     x_data, self.rssi_values, -20,
        #     color='skyblue', alpha=0.4, zorder=1
        # )

        self.ax.fill_between(
        x_data, self.rssi_values, -100,
        color='skyblue', alpha=0.4, zorder=1
        )


        # Имитация точек при отсутствии данных (более 5 секунд без обновлений)
        current_time = time.time()
        if current_time - self.last_valid_time > 5:  # Нет новых данных > 5 сек
            # Добавляем фиктивную точку с последним известным RSSI
            self.timestamps.append(current_time)
            self.rssi_values.append(self.rssi_values[-1])
            
            # Обновляем x_data для новой точки
            x_data.append(0)  # Новая точка всегда справа (x=0)

        # Окно просмотра: последние 60 секунд
        window_sec = 60
        x_min = max(0, x_data[-1] - window_sec)  # Не уходим левее 0
        x_max = x_data[0]  # Самая новая точка справа

        self.ax.set_xlim(x_max, x_min)  # Правая граница > левой → ось справа налево

        self.canvas.draw()


    def on_closing(self):
        """Обрабатывает закрытие окна."""
        logging.info("Закрытие окна мониторинга")
        self.stop_updating()
        self.destroy()

    def __del__(self):
        """Финальная очистка."""
        self.stop_updating()



# Обработчик сигналов для корректного завершения
def signal_handler(signum, frame):
    logging.info(f"Получен сигнал {signum}, завершение работы...")
    root.quit()
    root.destroy()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)



if __name__ == "__main__":
    # Пример запуска (замените параметры на реальные)
    root = tk.Tk()
    root.withdraw()  # Скрываем главное окно

    window = SecondWindow(
        parent=root,
        mac_address="E0:CC:F8:BB:75:45",
        manufacturer="Оценщик",
        channel=6
    )

    try:
        window.protocol("WM_DELETE_WINDOW", window.on_closing)
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("Прервано пользователем")
    finally:
        logging.info("Приложение завершено")
