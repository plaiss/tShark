import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import time
import threading

import config


# Команда для отслеживания сигнала конкретного устройства
TSHARK_CMD1 = [
    "tshark", "-i", "wlan1",
    # "-Y", "wlan.addr==48:8B:0A:A1:05:70",
    "-T", "fields",
    "-E", "separator=\t",
    "-e", "radiotap.dbm_antsignal"
]

TSHARK_CMD1 = [
    "tshark", "-i", "wlan1", "-l", "-T",
    # "-Y", "wlan.addr==48:8B:0A:A1:05:70",
    "fields",
    # "-e", "wlan.sa",
    "-e", "wlan_radio.signal_dbm"
]


# Максимальное количество точек на графике
MAX_POINTS_ON_GRAPH = 100


def get_data_stream(proc):
    while True:
        output = proc.stdout.readline().decode().strip()
        yield output


def extract_rssi(data):
    # Возвращаем последнее измеренное значение RSSI
    lines = data.splitlines()
    if lines:
        value = lines[-1].split('\t')[0]
        if value.startswith('-'):
            return value  # RSSI в dBm
        return '-'  # Недоступные данные
    return '-'


class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")

        # Передаем MAC-адрес устройства
        self.mac_address = mac_address or "Unknown"

        # Добавляем текстовые метки для MAC-адреса и канала
        self.mac_label = tk.Label(self, text=f"MAC: {self.mac_address}", font=("Arial", 12))
        self.channel_label = tk.Label(self, text="Channel: Unknown", font=("Arial", 12))
        self.rssi_label = tk.Label(self, text="RSSI: N/A", font=("Arial", 12))

        # Упаковка меток
        self.mac_label.pack()
        self.channel_label.pack()
        self.rssi_label.pack()

        # Кнопка "Пауза/Старт"
        self.pause_start_button = tk.Button(self, text="Пауза", command=self.toggle_pause)
        self.pause_start_button.pack()

        # График для отображения RSSI
        fig = plt.figure(figsize=(6, 3), dpi=100)
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()

        # Данные для графика
        self.rssi_values = []
        self.timestamps = []

        # Запускаем фоновый поток для регулярного обновления данных
        self.thread_running = True
        self.paused = False
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

    def stop_updating(self):
        # Останавливаем цикл обновления данных
        self.thread_running = False
        self.proc.kill()  # Завершаем процесс tshark

    def pause_or_resume_process(self):
        if self.paused:
            # Возобновляем процесс tshark
            self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
            self.data_update_thread.daemon = True
            self.data_update_thread.start()
        else:
            # Приостанавливаем процесс tshark
            self.proc.kill()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
            self.pause_or_resume_process()
        else:
            self.pause_start_button.config(text="Пауза")
            self.pause_or_resume_process()

    def update_data_from_stream(self):
        generator = get_data_stream(self.proc)
        while self.thread_running:
            # Получаем свежие данные
            response = next(generator, '')
            if not response:
                continue

            rssi_value = extract_rssi(response)

            # Проверяем, можно ли преобразовать значение в число
            try:
                rssi_float = float(rssi_value)
            except ValueError:
                print(f"Пропущено значение RSSI: '{rssi_value}'")
                continue  # Пропускаем итерацию, если значение нельзя обработать

            # Обновляем интерфейс
            self.rssi_label['text'] = f"RSSI: {rssi_value} dBm"

            # Обновляем график
            timestamp = time.time()
            self.rssi_values.append(rssi_float)
            self.timestamps.append(timestamp)

            # Удаляем лишние точки (эффект затухания)
            if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                self.rssi_values.pop(0)
                self.timestamps.pop(0)

            self.plot_graph()

            # Пауза между обновлениями (можно убрать паузу, так как данные поступают потоком)
            # time.sleep(1)

    def plot_graph(self):
        # Обновляем график RSSI
        self.ax.clear()
        self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('RSSI (dBm)')
        self.ax.grid(True)
        # self.canvas.draw()
        self.canvas.draw_idle()

    def destroy(self):
        # Завершаем поток при закрытии окна
        self.stop_updating()
        super().destroy()


# Тестовый запуск окна
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root, mac_address="48:8B:0A:A1:05:70")
    root.withdraw()  # Скрываем корневое окно
    app.mainloop()