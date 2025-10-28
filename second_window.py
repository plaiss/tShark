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
    "-Y", "wlan.addr==48:8B:0A:A1:05:70",
    "-T", "fields",
    "-E", "separator=\t",
    "-e", "radiotap.dbm_antsignal"
]

# Таймаут для выполнения команды (секунды)
TIMEOUT = 10


def get_data():
    try:
        # Запускаем команду tshark и ждём результата
        process = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        output, _ = process.communicate(timeout=TIMEOUT)
        return output.decode().strip()
    except subprocess.TimeoutExpired:
        print("Команда timed out!")
        return ''
    except Exception as e:
        print(f"Ошибка при выполнении команды: {e}")
        return ''


def extract_rssi(data):
    # Возвращаем последнее измеренное значение RSSI
    lines = data.splitlines()
    if lines:
        return lines[-1].split('\t')[0]
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
        self.data_update_thread = threading.Thread(target=self.update_data_periodically)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

    def stop_updating(self):
        # Останавливаем цикл обновления данных
        self.thread_running = False

    def update_data_periodically(self):
        while self.thread_running:
            # Получаем свежие данные
            response = get_data()
            rssi_value = extract_rssi(response)

            # Проверяем, можно ли преобразовать значение в число
            try:
                rssi_float = float(rssi_value)
            except ValueError:
                print(f"Пропущено значение RSSI: '{rssi_value}'")
                continue  # Пропускаем итерацию, если значение нельзя обработать

            # Обновляем интерфейс
            self.rssi_label['text'] = f"RSSI: {rssi_value}"

            # Обновляем график
            timestamp = time.time()
            self.rssi_values.append(rssi_float)
            self.timestamps.append(timestamp)
            self.plot_graph()

            # Пауза между обновлениями (1 секунда)
            time.sleep(1)

    def plot_graph(self):
        # Обновляем график RSSI
        self.ax.clear()
        self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('RSSI')
        self.ax.grid(True)
        self.canvas.draw()

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