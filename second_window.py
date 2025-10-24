
import tkinter as tk
from tkinter import ttk

import utils
import config

class SecondWindow(tk.Toplevel):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.parent = parent  # Сохраняем ссылку на родительское окно
        self.title("Подробности устройства")
        self.geometry("640x480")
        # self.parent.toggle_scanning()


        if data is not None:
            self.mac_address = data[0]  # Сохраняем MAC адрес для последующих запросов
            details = f"MAC: {data[0]} | Производитель: {utils.lookup_vendor_db(data[0], config.DB_PATH, False)}\nКол-во сигналов: {data[1]}\nПоследний раз обнаружен: {data[2]}"
            label = tk.Label(self, text=details)
            label.pack(pady=20)
        else:
            label = tk.Label(self, text="Нет доступной информации")
            label.pack(pady=20)

        # Элементы интерфейса для отображения текущей информации
        self.rssi_label = tk.Label(self, text="RSSI: ")
        self.channel_label = tk.Label(self, text="Канала: ")
        self.rssi_label.pack()
        self.channel_label.pack()

        close_btn = tk.Button(self, text="Закрыть", command=self.destroy)
        close_btn.pack(pady=10)

        find_btn = tk.Button(self, text="Искать", command=self.run_find)
        find_btn.pack(pady=10)

        # Начнем периодическое получение данных
        self.update_interval_ms = 1000  # Периодичность обновления (1 секунда)
        self.update_data_periodically()

    def run_find(self):
        # Переопределим действие кнопки, чтобы начать автоматическое обновление
        self.update_data_periodically()

    def update_data_periodically(self):
        # Получаем текущие данные о сигнале и канале
        current_rssi = self.get_current_rssi()
        current_channel = self.get_current_channel()

        # Обновляем интерфейс
        self.rssi_label['text'] = f"RSSI: {current_rssi}"
        self.channel_label['text'] = f"Канал: {current_channel}"

        # Повторяем обновление через интервал
        self.after(self.update_interval_ms, self.update_data_periodically)

    def get_current_rssi(self):
        # Можно реализовать получение актуальной информации о сигнале из основного потока
        # Простой пример, заменяйте на реальный источник данных
        return "42 дБи"

    def get_current_channel(self):
        # Аналогично получаем текущий номер канала
        return "6"