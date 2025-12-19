import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import time
import threading
import config
import os
import re
import utils

# Максимальная длина графика
MAX_POINTS_ON_GRAPH = 100

# Генерация потока данных из tshark
def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output

# Извлечение уровня сигнала (RSSI)
def extract_rssi(data):
    parts = data.strip().split("\t")
    if len(parts) >= 2:
        return parts[1]  # Второе поле — уровень сигнала (RSSI)
    return "-"

# Основной класс окна с деталями устройства
class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")
        
        # Адрес устройства
        self.mac_address = mac_address or "5E:CE:BA:35:67:AD"

        # Информация о канале Wi-Fi
        wifi_info = os.popen(f"iw dev wlan1 info").read()
        channel_num, frequency = utils.parse_wifi_info(wifi_info)
        if channel_num != channel_num:
            print('Текущий канал не соответствует указанному!')

        # Основная команда для отслеживания сигнала (RSSI)
        TSHARK_CMD1 = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "frame.number",  # Номер кадра
            "-e", "wlan_radio.signal_dbm",  # Уровень сигнала (RSSI)
            "-Y", f"wlan.ta=={self.mac_address}",
            "-l"  # Буферизация
        ]

        # Быстрая проверка типа устройства (AP или STA)
        self.CHECK_TYPE_CMD = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "wlan.fc.type_subtype",  # Поле типа фрейма
            "-Y", f"wlan.addr=={self.mac_address}",
            "-c", "100",  # Число пакетов для анализа
            "-l"  # Буферизация
        ]

        # Скользящая средняя (EMA)
        self.ema_value = None  # Начальное значение скользящей средней

        # Пользовательские лейблы
        self.frame_number_label = tk.Label(self, text="Номер кадра: N/A", font=("Arial", 12))
        self.frame_number_label.pack()

        self.delay_label = tk.Label(self, text="Последнее обновление: N/A", font=("Arial", 12))
        self.delay_label.pack()

        self.channel_label = tk.Label(self, text=f"Канал: {channel}, Частота: {frequency}", font=("Arial", 12))
        self.channel_label.pack()

        self.mac_label = tk.Label(self, text=f"MAC: {self.mac_address}", font=("Arial", 12))
        self.mac_label.pack()

        self.manufacturer_label = tk.Label(self, text=f"Производитель: {manufacturer}", font=("Arial", 12))
        self.manufacturer_label.pack()

        self.rssi_label = tk.Label(self, text="RSSI: N/A", font=("Arial", 12))
        self.rssi_label.pack()

        # Создание графики для отображения уровней сигнала
        fig = plt.Figure(figsize=(6, 4))
        self.ax = fig.add_subplot(111)
        self.ax.grid(True)
        self.ax.set_ylabel('RSSI (dBm)')
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()

        # Масштабирование сетки графика
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)

        # Данные для графика
        self.rssi_values = []  # Список для хранения значений RSSI
        self.timestamps = []  # Временные метки

        # Управление параметрами фильтрации
        self.alpha = 0.2  # Коэффициент сглаживания
        self.use_filter_var = tk.BooleanVar(value=True)  # Использование сглаживания

        # Кнопка паузы
        self.pause_start_button = tk.Button(self, text="Пауза", command=self.toggle_pause)
        self.pause_start_button.pack()

        # Старт мониторинга
        self.thread_running = True
        self.paused = False
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

        # Определение типа устройства
        self.check_device_type()

    def check_device_type(self):
        """Определение типа устройства (AP или STA)."""
        proc = subprocess.Popen(self.CHECK_TYPE_CMD, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frames = []
        for line in get_data_stream(proc):
            frame_type = line.split()[0]
            frames.append(frame_type)

        # Подсчёт фреймов разных типов
        beacon_count = sum(1 for ft in frames if ft.startswith("0x08"))
        probe_req_count = sum(1 for ft in frames if ft.startswith("0x04"))

        if beacon_count > 0:
            device_type = "Access Point (AP)"
        elif probe_req_count > 0:
            device_type = "Station (STA)"
        else:
            device_type = "Unknown"

        # Отображение типа устройства
        type_label = tk.Label(self, text=f"Тип устройства: {device_type}", font=("Arial", 12))
        type_label.pack()

        # Завершение процесса
        proc.wait()

    def stop_updating(self):
        """Остановка сбора данных."""
        self.thread_running = False
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

    def update_data_from_stream(self):
        """Обработка данных из потока tshark."""
        decimation_counter = 0  # Счётчик пропускаемых пакетов

        generator = get_data_stream(self.proc)
        while self.thread_running:
            if self.paused:
                time.sleep(1)
                continue

            # Получение очередного пакета
            response = next(generator, '')
            if not response:
                continue

            # Выборка каждого второго пакета
            decimation_counter += 1
            if decimation_counter % 2 != 0:
                continue

            # Разбиение полученной строки
            parts = response.strip().split("\t")
            if len(parts) != 2:
                print(f"[DEBUG] Недостаточно полей в выводе: {response}")
                continue

            frame_number = parts[0]  # Номер кадра
            rssi_value = parts[1].strip()  # Уровень сигнала (RSSI)

            # Преобразование значения RSSI
            try:
                current_rssi = float(rssi_value)

                # Проверка диапазона значений RSSI
                if current_rssi < -20 and current_rssi >= -100:
                    # Обновляем интерфейс
                    self.frame_number_label["text"] = f"Номер кадра: {frame_number}"

                    # Обновляем последнюю временную отметку
                    now = time.time()
                    self.last_valid_time = now

                    # Удаляем надпись о задержке
                    self.delay_label["text"] = ""

                    # Вычисляем скользящую среднюю (EMA)
                    if self.use_filter_var.get():
                        if self.ema_value is None:
                            self.ema_value = current_rssi
                        else:
                            self.ema_value = self.alpha * current_rssi + (1 - self.alpha) * self.ema_value

                        # Используется сглаженное значение
                        self.rssi_label["text"] = f"RSSI: {self.ema_value:.2f} dBm"
                        self.rssi_values.append(self.ema_value)
                    else:
                        # Без сглаживания используем исходное значение
                        self.rssi_label["text"] = f"RSSI: {current_rssi:.2f} dBm"
                        self.rssi_values.append(current_rssi)

                    # Временная метка текущего момента
                    timestamp = time.time()
                    self.timestamps.append(timestamp)

                    # Ограничиваем длину графика
                    if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                        self.rssi_values.pop(0)
                        self.timestamps.pop(0)

                    # Обновляем график
                    self.plot_graph()
                else:
                    # Неправильные данные вызывают задержку
                    if self.last_valid_time is not None:
                        delay_seconds = int(time.time() - self.last_valid_time)
                        self.delay_label["text"] = f"Последнее обновление: {delay_seconds} сек."
            except ValueError:
                print(f"[DEBUG] Некорректное значение RSSI: '{rssi_value}'")
                continue

    def plot_graph(self):
        """Отрисовка графика значений RSSI."""
        self.ax.clear()  # Очистка графика
        self.ax.grid(True)
        self.ax.set_ylabel('RSSI (dBm)')
        self.ax.plot(self.timestamps, self.rssi_values, color='blue')

        # Настройки оси Y
        yticks = list(range(-100, -20, 10))
        self.ax.set_yticks(yticks)
        self.ax.set_ylim(-100, -20)

        # Осью X управляет библиотека, мы её скрываем
        self.ax.xaxis.set_visible(False)
        self.canvas.draw_idle()  # Обновляем график

    def destroy(self):
        """Завершение работы программы."""
        self.stop_updating()
        self.data_update_thread.join()
        time.sleep(0.5)
        plt.close('all')
        super().destroy()
        if __name__ == "__main__":
            root.destroy()

# Запуск тестового окна
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root)
    root.withdraw()  # Скрываем главное окно
    app.mainloop()