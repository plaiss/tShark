import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import time
import threading

import config


#tshark -i wlan1  -s 0 -T fields -e wlan_radio.signal_dbm -Y wlan.ra==28:e3:47:fe:34:44

TSHARK_CMD1 = [
    "tshark", "-i", "wlan1",
    "-s",  "0",
    "-T", "fields",
    "-e", "wlan_radio.signal_dbm"
    "-Y", "wlan.ra==28:e3:47:fe:34:44"
]
# Максимальное количество точек на графике
MAX_POINTS_ON_GRAPH = 100


def get_data_stream(proc):
    while True:
        output = proc.stdout.readline().decode()
        # output = proc.stdout.readline().decode().strip()
        print(f"[DEBUG] Received from tshark: {output}")  # Вывод полученных данных
        yield output


# def extract_rssi(data):
#     return data
#     # Возвращаем последнее измеренное значение RSSI
#     lines = data.splitlines()
#     if lines:
#         value = lines[-1].split('\t')[0]
#         if value.startswith('-'):
#             return value  # RSSI в dBm
#         return '-'  # Недоступные данные
#     return '-'


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
        print(f"[DEBUG] Starting tshark with command: {' '.join(TSHARK_CMD1)}")  # Печать команды
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

    def stop_updating(self):
        # Останавливаем цикл обновления данных
        self.thread_running = False
        # Форсированное завершение процесса tshark
        if self.proc.poll() is None:
            print("[DEBUG] Killing tshark process...")  # Печать перед завершением
            self.proc.kill()  # Обязательно завершать процесс, если он еще активен
            self.proc.wait()  # Ожидаем завершения процесса

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
        else:
            self.pause_start_button.config(text="Пауза")

    def update_data_from_stream(self):
        generator = get_data_stream(self.proc)
        while self.thread_running:
            if self.paused:
                time.sleep(1)  # Пауза на секунду, чтобы не нагружать процессор
                continue

            # Получаем свежие данные
            response = next(generator, '')
            if not response:
                continue

            rssi_value = extract_rssi(response)

            # Проверяем, можно ли преобразовать значение в число
            try:
                rssi_float = float(rssi_value)
            except ValueError:
                print(f"[DEBUG] Skipped invalid RSSI value: '{rssi_value}'")  # Вывод пропущенных значений
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

    def plot_graph(self):
        # Обновляем график RSSI
        self.ax.clear()
        self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('RSSI (dBm)')
        self.ax.grid(True)
        self.canvas.draw_idle()

    def destroy(self):
        # Завершаем поток при закрытии окна
        self.stop_updating()
        # Дождемся завершения потока
        self.data_update_thread.join()
        # Небольшая задержка для гарантии освобождения ресурсов
        time.sleep(0.5)
        # Освобождение ресурсов
        plt.close('all')
        super().destroy()
        root.destroy()


# Тестовый запуск окна
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root)
    # app = SecondWindow(root, mac_address="48:8B:0A:A1:05:70")
    root.withdraw()  # Скрываем корневое окно
    app.mainloop()