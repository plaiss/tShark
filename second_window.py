import tkinter as tk
from tkinter import ttk
import subprocess
import time
import threading

import config


# Команда для отслеживания сигнала конкретного устройства
TSHARK_CMD1 = [
    "tshark", "-i", "wlan1",
    "-Y", "wlan.addr==48:8B:0A:A1:05:70",
    "-T", "fields",
    "-E", "separator=/t",
    "-e", "radiotap.dbm_antsignal"
]

# Время ожидания выполнения команды (секунды)
TIMEOUT = 10


def get_data():
    try:
        # Запускаем команду tshark и ждем результата
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


def extract_channel(data):
    # Примечание: здесь вам нужно дополнить, если нужны данные о канале
    return '-'  # Просто подставляйте реальную логику


class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")

        # Метки для показа RSSI и канала
        self.rssi_label = tk.Label(self, text="RSSI:")
        self.channel_label = tk.Label(self, text="Channel:")
        self.rssi_label.pack()
        self.channel_label.pack()

        # Запустим фоновый поток для регулярного обновления данных
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
            channel_value = extract_channel(response)

            # Обновляем интерфейс
            self.rssi_label['text'] = f"RSSI: {rssi_value}"
            self.channel_label['text'] = f"Channel: {channel_value}"

            # Пауза между обновлениями (1 секунда)
            time.sleep(1)

    def destroy(self):
        # Завершаем поток при закрытии окна
        self.stop_updating()
        super().destroy()


# Тестовый запуск окна
# if __name__ == "__main__":
#     root = tk.Tk()
#     app = SecondWindow(root)
#     root.withdraw()  # Скрываем корневое окно
#     app.mainloop()