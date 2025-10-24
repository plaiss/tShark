import tkinter as tk
from tkinter import ttk
import subprocess
import time

import config


# Функция для непосредственного получения данных о сигнале и канале
def get_data():
    # Замещаете эту заглушку реальной командой для получения данных
    TSHARK_CMD1 = [
        "tshark", "-i", "wlan1",
        "-Y", "wlan.addr==48:8B:0A:A1:05:70",
        "-T", "fields",
        "-E", "separator = / t",
        "-e", "radiotap.dbm_antsignal"
    ]

    # tshark - i
    # wlan1 - Y
    # "wlan.addr==<YOUR_MAC_ADDRESS>" - T
    # fields - E
    # separator = / t - e
    # wlan.sa - e
    # radiotap.dbm_antsignal



    result = subprocess.check_output(TSHARK_CMD1, shell=True).decode('utf-8').strip()
    return result


class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")

        # Интерфейс для отображения RSSI и канала
        self.rssi_label = tk.Label(self, text="RSSI:")
        self.channel_label = tk.Label(self, text="Channel:")
        self.rssi_label.pack()
        self.channel_label.pack()

        # Начинаем периодическое обновление данных
        self.update_data_periodically()

    def update_data_periodically(self):
        # Непосредственно получаем данные
        response = get_data()
        # Извлекаем необходимые данные (пример)
        rssi_value = extract_rssi(response)
        channel_value = extract_channel(response)

        # Обновляем интерфейс
        self.rssi_label['text'] = f"RSSI: {rssi_value}"
        self.channel_label['text'] = f"Channel: {channel_value}"

        # Повторяем обновление через небольшой промежуток времени
        self.after(1000, self.update_data_periodically)


# Запуск окна
if __name__ == "__main__":
    root = tk.Tk()
    app = SecondWindow(root)
    root.withdraw()  # Скрываем корневое окно
    app.mainloop()