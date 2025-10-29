import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import time
import threading

import config


# Максимальная длина графика
MAX_POINTS_ON_GRAPH = 50


# Генерирует потоки данных из tshark
def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output


# Функция извлечения RSSI
def extract_rssi(data):
    parts = data.strip().split("\t")
    if len(parts) >= 4:
        return parts[3]  # Четвёртое поле - сигнал (RSSI)
    return "-"


# Класс окна детальной информации
class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")

        # Мак-адрес устройства передается из родительского окна или оставляется текущий
        self.mac_address = data[0] or "2c:57:41:83:32:03"

        # Новый запрос к tshark
        TSHARK_CMD1 = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "wlan.ra",  # Поле RA (Receiver Address)
            "-e", "wlan.ra.oui_resolved",  # Производитель (OUI Resolved)
            "-e", "wlan_radio.channel",  # Номер канала
            "-e", "wlan_radio.signal_dbm",  # Уровень сигнала (RSSI)
            "-Y", f"wlan.ra=={self.mac_address}",  # Фильтруем по MAC-адресу
            # "-Y", "wlan.ra==2c:57:41:83:32:03",  # Фильтруем по MAC-адресу
            "-l"  # Включаем line buffering mode
            ]

        # Метки для отображения MAC, канала и RSSI
        self.mac_label = tk.Label(self, text=f"MAC: {self.mac_address}", font=("Arial", 12))
        self.channel_label = tk.Label(self, text="Channel: Unknown", font=("Arial", 12))
        self.manufacturer_label = tk.Label(self, text="Manufacturer: Unknown", font=("Arial", 12))
        self.rssi_label = tk.Label(self, text="RSSI: N/A", font=("Arial", 12))

        # Упаковка меток
        self.mac_label.pack()
        self.channel_label.pack()
        self.manufacturer_label.pack()
        self.rssi_label.pack()

        # Кнопка паузы/старта
        self.pause_start_button = tk.Button(self, text="Пауза", command=self.toggle_pause)
        self.pause_start_button.pack()

        # Создаем фигуру для графика
        fig = plt.figure(figsize=(6, 4))  # Увеличили высоту фигуры
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()

        # Данные для графика
        self.rssi_values = []
        self.timestamps = []

        # Начинаем сбор данных
        self.thread_running = True
        self.paused = False
        print(f"[DEBUG] Starting tshark with command: {' '.join(TSHARK_CMD1)}")
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

    def stop_updating(self):
        """Завершить обновление"""
        self.thread_running = False
        if self.proc.poll() is None:
            print("[DEBUG] Killing tshark process...")
            self.proc.kill()
            self.proc.wait()

    def toggle_pause(self):
        """Переключатель паузы"""
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
        else:
            self.pause_start_button.config(text="Пауза")

    def update_data_from_stream(self):
        """Обновление данных из потока tshark"""
        generator = get_data_stream(self.proc)
        while self.thread_running:
            if self.paused:
                time.sleep(1)
                continue

            # Читаем новую порцию данных
            response = next(generator, '')
            if not response:
                continue

            # Парсим вывод tshark
            parts = response.strip().split("\t")
            if len(parts) >= 4:
                ra = parts[0]  # Receiver address
                manufacturer = parts[1]  # Производитель
                channel = parts[2]  # Канал
                rssi_value = parts[3]  # Сигнал (RSSI)

                # Обновляем интерфейс
                self.channel_label["text"] = f"Channel: {channel}"
                self.manufacturer_label["text"] = f"Manufacturer: {manufacturer}"
                self.rssi_label["text"] = f"RSSI: {rssi_value} dBm"

                # Сохраняем RSSI для графика
                try:
                    rssi_float = float(rssi_value)
                except ValueError:
                    print(f"[DEBUG] Skipped invalid RSSI value: '{rssi_value}'")
                    continue

                # Обновляем график
                timestamp = time.time()
                self.rssi_values.append(rssi_float)
                self.timestamps.append(timestamp)

                # Ограничиваем длину графика
                if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                    self.rssi_values.pop(0)
                    self.timestamps.pop(0)

                self.plot_graph()

    # def plot_graph(self):
    #     """Рисование графика"""
    #     self.ax.clear()
    #     self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')
    #     self.ax.set_xlabel('Time')
    #     self.ax.set_ylabel('RSSI (dBm)')
    #     self.ax.grid(True)
    #     self.canvas.draw_idle()
    #
    def plot_graph(self):
        """Рисование графика"""
        self.ax.clear()
        self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')  # Нет аргументов legend
        # self.ax.set_xlabel('Time')
        self.ax.xaxis.set_visible(False)
        self.ax.set_ylabel('RSSI (dBm)')
        self.ax.grid(True)
        self.canvas.draw_idle()



    # def plot_graph(self):
    #     """Рисование графика"""
    #     self.ax.clear()
    #     self.ax.plot(self.timestamps, self.rssi_values, marker='o', color='blue')
    #
    #     # Устанавливаем фиксированную ось Y (-100..0 дБм)
    #     self.ax.set_ylim(-100, 0)
    #
    #     # Убираем временную шкалу снизу (ось X)
    #     self.ax.xaxis.set_visible(False)
    #
    #     # Оставляем подписи осей
    #     self.ax.set_ylabel('RSSI (dBm)')
    #     self.ax.grid(True)
    #     self.canvas.draw_idle()

    def destroy(self):
        """Завершение потоков и очистка окон"""
        self.stop_updating()
        self.data_update_thread.join()
        time.sleep(0.5)
        plt.close('all')
        super().destroy()
        if __name__ == "__main__":
            root.destroy()


# Тестовый запуск окна
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root)
    # app = SecondWindow(root, mac_address="48:8B:0A:A1:05:70")
    root.withdraw()  # Скрываем корневое окно
    app.mainloop()