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

# Парсер информации о Wi-Fi
# def parse_wifi_info(output):
#     pattern = r'channel\s*(\d+)\s*([^)]+)'
#     # pattern = r'channel\s*(\d+)\s*$([^)]+)$'
#     match = re.search(pattern, output)
#     if match:
#         channel_num = match.group(1)
#         frequency = match.group(2)[1:]
#         return channel_num, frequency
#     return None, None

# Генерирует потоки данных из tshark
def get_data_stream(proc):
    for line in iter(proc.stdout.readline, b''):
        output = line.decode().strip()
        if output:
            yield output

# Функция извлечения RSSI
def extract_rssi(data):
    parts = data.strip().split("\t")
    if len(parts) >= 2:
        return parts[1]  # Второе поле — сигнал (RSSI)
    return "-"

# Класс окна детальной информации
class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Подробности устройства")
        self.geometry("640x480")

        # MAC-адрес устройства
        self.mac_address = mac_address or "5E:CE:BA:35:67:AD"

        # Получаем информацию о Wi-Fi-канале
        wifi_info = os.popen(f"iw dev wlan1 info").read()
        channel_num, frequency = utils.parse_wifi_info(wifi_info)
        if channel_num != channel_num:
            
            print('Текущий канал не равен заказанному!!!!!')

        # Команда для tshark
        TSHARK_CMD1 = [
            "tshark", "-i", "wlan1",
            "-s", "0",
            "-T", "fields",
            "-e", "frame.number",  # Номер кадра
            "-e", "wlan_radio.signal_dbm",  # RSSI
            "-Y", f"wlan.ta=={self.mac_address}",
            "-l"  # Буферизация
        ]
        # Команда для tshark
        # TSHARK_CMD2 = [
        #     "tshark", "-i", "wlan1",
        #     "-s", "0",
        #     "-T", "fields",
        #     "-e", "wlan.ta",  # RA (приёмник)
        #     "-e", "wlan.ta.oui_resolved",  # производитель
        #     "-e", "wlan_radio.channel",  # канал
        #     "-e", "wlan_radio.signal_dbm",  # RSSI
        #     "-f", f'\"ether src {self.mac_address}\"',
        #     "-l"  # Буферизация
        # ]
        #tshark -i wlan1 -s 0 -T fields -e frame.number -e wlan_radio.channel -e wlan_radio.signal_dbm -f "ether src 36:6F:D8:75:91:57" -l


        # Переменная состояния для хранения производителя
        # self.updated_manufacturer = False


        # Последняя успешная временная отметка
        self.last_valid_time = None

        # Лейбл для отображения времени задержки
        self.delay_label = tk.Label(self, text="Последнее обновление: N/A", font=("Arial", 12))
        self.delay_label.pack()

        # Лейбл для отображения номера кадра
        self.frame_number_label = tk.Label(self, text="Frame Number: N/A", font=("Arial", 12))
        self.frame_number_label.pack()

        # Лейбл для отображения канала и частоты
        self.channel_label = tk.Label(self, text=f"Channel: {channel}, Frequency: {frequency}", font=("Arial", 12))
        # self.channel_label = tk.Label(self, text=f"Channel: {channel_num}, Frequency: {frequency}", font=("Arial", 12))
        self.channel_label.pack()

        # Другие метки
        self.mac_label = tk.Label(self, text=f"MAC: {self.mac_address}", font=("Arial", 12))
        self.manufacturer_label = tk.Label(self, text=f"Manufacturer: {manufacturer}", font=("Arial", 12))
        self.rssi_label = tk.Label(self, text="RSSI: N/A", font=("Arial", 12))

        # Упаковка остальных меток
        self.mac_label.pack()
        self.manufacturer_label.pack()
        self.rssi_label.pack()

        # Кнопка паузы / старта
        self.pause_start_button = tk.Button(self, text="Пауза", command=self.toggle_pause)
        self.pause_start_button.pack()

        # Холст для графика
        fig = plt.Figure(figsize=(6, 4))
        self.ax = fig.add_subplot(111)
        self.ax.grid(True)
        self.ax.set_ylabel('RSSI (dBm)')
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()

        # Данные для графика
        self.rssi_values = []
        self.timestamps = []

        # Параметры фильтра
        self.alpha = 0.2
        self.use_filter_var = tk.BooleanVar(value=True)

        # Элементы управления фильтром
        self.alpha_slider = tk.Scale(
            self, from_=0.01, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
            label="Коэффициент сглаживания:", length=200
        )
        self.alpha_slider.set(self.alpha)
        self.alpha_slider.pack()
        self.alpha_slider.bind("<ButtonRelease-1>", lambda e: self.update_alpha())

        # Фильтр вкл./выкл.
        self.filter_toggle = tk.Checkbutton(
            self, text="Скользящее среднее включено", variable=self.use_filter_var,
            command=lambda: self.toggle_filter()
        )
        self.filter_toggle.pack()

        # Стартуем мониторинг
        self.thread_running = True
        self.paused = False
        # print(f"[DEBUG] Запуск TSHARK_CMD1 командой: {' '.join(TSHARK_CMD1)}")
        self.proc = subprocess.Popen(TSHARK_CMD1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.data_update_thread = threading.Thread(target=self.update_data_from_stream)
        self.data_update_thread.daemon = True
        self.data_update_thread.start()

        # Начальная точка скользящей средней
        self.ema_value = None

    def stop_updating(self):
        """Завершаем поток сбора данных."""
        self.thread_running = False
        if self.proc.poll() is None:
            # print(f"[DEBUG] Процесс поиска {self.mac_address} завершен")
            self.proc.kill()
            self.proc.wait()

    def toggle_pause(self):
        """Переключение режима пауза/продолжить."""
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
        else:
            self.pause_start_button.config(text="Пауза")

    def update_alpha(self):
        """Обновляет коэффициент сглаживания."""
        self.alpha = self.alpha_slider.get()
        print(f"Новый коэффициент сглаживания: {self.alpha}")

    def toggle_filter(self):
        """Включает/отключает фильтр."""
        filter_state = "включено" if self.use_filter_var.get() else "отключено"
        print(f"Состояние фильтра: {filter_state}")

    def update_data_from_stream(self):
        """Обновляет данные из потока tshark."""
        decimation_counter = 0  # Контроллер децимации

        generator = get_data_stream(self.proc)
        while self.thread_running:
            if self.paused:
                time.sleep(1)
                continue

            # Получаем новую порцию данных
            response = next(generator, '')
            if not response:
                continue

            # Проводим децимацию данных
            decimation_counter += 1
            if decimation_counter % 2 != 0:  # Оставляем только каждый пятый пакет
                continue

            # Парсим строку
            parts = response.strip().split("\t")
            if len(parts) != 2:
                print(f"[DEBUG] Недостаточно полей в выводе: {response}")
                continue

            frame_number = parts[0]  # Номер кадра
            rssi_value = parts[1].strip()  # RSSI

            # Преобразование значения RSSI
            try:
                current_rssi = float(rssi_value)

                # Проверка корректности данных
                if current_rssi < -20 and current_rssi >= -100:
                    # Обновляем интерфейс
                    self.frame_number_label["text"] = f"Frame Number: {frame_number}"  # Обновляем номер кадра

                    # Сохраняем текущую временную отметку
                    now = time.time()
                    self.last_valid_time = now

                    # Никакой надписи не ставим, пока идут корректные данные
                    self.delay_label["text"] = ""

                    # Продолжаем стандартную обработку данных
                    if self.use_filter_var.get():
                        if self.ema_value is None:
                            self.ema_value = current_rssi
                        else:
                            self.ema_value = self.alpha * current_rssi + (1 - self.alpha) * self.ema_value

                        # Показываем сглаженное значение
                        self.rssi_label["text"] = f"RSSI: {self.ema_value:.2f} dBm"
                        self.rssi_values.append(self.ema_value)
                    else:
                        # Показываем необработанное значение
                        self.rssi_label["text"] = f"RSSI: {current_rssi:.2f} dBm"
                        self.rssi_values.append(current_rssi)

                    # Время временной отметки
                    timestamp = time.time()
                    self.timestamps.append(timestamp)

                    # Ограничиваем количество точек на графике
                    if len(self.rssi_values) > MAX_POINTS_ON_GRAPH:
                        self.rssi_values.pop(0)
                        self.timestamps.pop(0)

                    # Обновляем график
                    self.plot_graph()
                else:
                    # Если пришли некорректные данные, начинаем отсчет времени задержки
                    if self.last_valid_time is not None:
                        delay_seconds = int(time.time() - self.last_valid_time)
                        self.delay_label["text"] = f"Последнее обновление: {delay_seconds} секунд назад"
            except ValueError:
                print(f"[DEBUG] Пропущено некорректное значение RSSI: '{rssi_value}'")
                continue

    def plot_graph(self):
        if hasattr(self, 'canvas'):
            """
            Отображает график значений RSSI.
            """
            self.ax.clear()  # Очищаем график перед новым построением

            # Установим точно диапазон оси Y
            yticks = list(range(-100, -20, 10))  # Каждое деление составляет 10 дБм
            self.ax.set_yticks(yticks)
            self.ax.set_ylim(-100, -20)  # Зафиксировали диапазон от -100 до -20 дБм

            # Включаем сетку
            self.ax.yaxis.grid(True, which='both')

            # Постройте график
            self.ax.plot(self.timestamps, self.rssi_values, color='blue')
            self.ax.set_ylabel('RSSI (dBm)')
            self.ax.xaxis.set_visible(False)  # Скрываем ось X
            self.canvas.draw_idle()  # Обновляем график

    def destroy(self):
        """Завершает работу программы."""
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
    root.withdraw()  # Скрываем основное окно
    app.mainloop()