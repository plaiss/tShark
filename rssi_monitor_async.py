import logging
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import asyncio
import threading
import numpy as np
from collections import deque
import re
import os
import shutil
import signal
import sys
from typing import Optional
import time

# Конфигурируемые параметры
MAX_POINTS_ON_GRAPH = 1000
EMA_ALPHA = 0.2
UPDATE_INTERVAL_MS = 50      # Чтение данных (мс)
PLOT_UPDATE_INTERVAL_MS = 100  # Перерисовка графика (мс)
TSHARK_TIMEOUT_SEC = 60

# Настройка логгера для модуля rssi_monitor_async
logger = logging.getLogger("rssi_monitor_async")
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень детализации логирования

# Создаем обработчик для записи в файл rssi_monitor.log
file_handler = logging.FileHandler("LOGS/rssi_monitor.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# Форматировщик
LOG_FORMAT = '%(asctime)s [%(levelname)-8s]: %(message)s (%(filename)s:%(lineno)d)'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
file_handler.setFormatter(formatter)

# Добавляем обработчик к логгеру и отключаем передачу в корневые обработчики
logger.addHandler(file_handler)
logger.propagate = False

# Дополнительно добавляем вывод в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class SecondWindow(tk.Toplevel):
    def __init__(self, parent, mac_address=None, manufacturer=None, channel=None, interface="wlan1"):
        super().__init__(parent)
        self.geometry("800x480")
        self.parent = parent
        self.title("Мониторинг RSSI")
        self.interface = interface
        logger.info("Запуск мониторинга...")
        self.paused = False
        self.device_type = ""
        self.last_valid_time = time.time()
        self.ssid = "N/A"
        self.mac_address = mac_address or "7A:6C:06:3C:F7:DF"

        # Валидация MAC
        if not re.match(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$", self.mac_address):
            logger.warning(f"Некорректный MAC-адрес. Используем дефолтный: {self.mac_address}")
            self.mac_address = "7A:6C:06:3C:F7:DF"

        # Проверка tshark и интерфейса
        if not shutil.which("tshark"):
            logger.error("tshark не установлен! Завершаем работу.")
            self.destroy()
            return
        if not os.path.exists(f"/sys/class/net/{self.interface}"):
            logger.error(f"Интерфейс {self.interface} не найден!")
            self.destroy()
            return

        # GUI setup
        self._setup_ui(manufacturer, channel)

        # Асинхронный цикл и задача
        self.loop = asyncio.new_event_loop()
        self.task = None

        # Сохраняем глобально цикл событий для последующего использования
        global main_loop
        main_loop = self.loop

        # Запуск асинхронной задачи в отдельном потоке
        threading.Thread(target=self._run_async_in_thread, args=(self.loop,)).start()

        # ЗАПУСКАЕМ ОБНОВЛЕНИЕ ГРАФИКА В САМОМ КОНЦЕ
        self.after(100, self.schedule_plot_update)

    def _run_async_in_thread(self, loop):
        """Запускает asyncio-цикл в отдельном потоке."""
        asyncio.set_event_loop(loop)
        try:
            task = loop.create_task(self._main_async())
            loop.run_forever()  # Работаем вечно, пока есть задачи
        finally:
            loop.close()

    def _stop_asyncio(self):
        """Останавливает асинхронную задачу и цикл."""
        if self.task and not self.task.done():
            self.task.cancel()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

    async def _main_async(self):
        """Основной асинхронный процесс: определение роли + мониторинг RSSI."""
        await self._run_tshark_discovery()
        if self.device_type:  # Роль определена
            await self._run_tshark_monitor()
        else:
            self._update_status("Не удалось определить роль устройства", "red")

    async def _run_tshark_discovery(self):
        """Этап 1: Определение роли устройства (AP/STA)."""
        cmd = [
            'tshark', '-l', '-i', self.interface,
            '-T', 'fields', '-E', 'separator=\t',
            '-e', 'wlan.fc.type', '-e', 'wlan.fc.subtype',
            '-e', 'wlan.sa', '-e', 'wlan.da', '-e', 'wlan.bssid',
            '-e', 'frame.number', '-e', 'wlan_radio.signal_dbm',
            '-Y', f'(wlan.sa == {self.mac_address} or wlan.da == {self.mac_address} or wlan.bssid == {self.mac_address}) and (wlan.fc.type == 0 or wlan.fc.type == 2)'
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            logger.info(f"Запущена команда: {' '.join(cmd)}")

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                if not line_str:
                    continue
                parts = line_str.split('\t', 6)
                if len(parts) != 7:
                    continue

                fc_type, fc_subtype, sa, da, bssid, _, signal = parts
                role = self._determine_role(fc_type, fc_subtype, sa, da, bssid)
                if role:
                    self.device_type = role
                    self._update_ui_after_check()
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        process.kill()
                    return

        except Exception as e:
            logger.error(f"Ошибка при определении роли: {e}")
            self._update_status(f"Ошибка: {e}", "red")

    def _determine_role(self, fc_type: str, fc_subtype: str, sa: str, da: str, bssid: str) -> Optional[str]:
        """Определяет роль устройства по полям кадра."""
        if fc_type == "0":  # Management
            if fc_subtype == "8" and bssid.lower() == self.mac_address.lower():
                return "Access Point (AP)"
            elif (sa.lower() == self.mac_address.lower() or da.lower() == self.mac_address.lower()) and fc_subtype in ("4", "5", "0", "1"):
                return "Station (STA)"
        elif fc_type == "2":  # Data
            if sa.lower() == self.mac_address.lower():
                return "Station (STA)"
            elif da.lower() == self.mac_address.lower() and bssid.lower() != self.mac_address.lower():
                return "Station (STA)"
        return None

    def _update_ui_after_check(self):
        """Обновляет интерфейс после определения роли."""
        self.labels["Тип устройства"]["text"] = self.device_type
        self.status_label.config(text="Готово", fg="green")

    def _update_status(self, text: str, color: str):
        """Обновляет статусную метку."""
        if not self.winfo_exists():
            return
        self.status_label.config(text=text, fg=color)

    async def _run_tshark_monitor(self):
        """Этап 2: Мониторинг RSSI с фильтром по роли."""
        if self.device_type == "Access Point (AP)":
            filter_expr = f'wlan.bssid == {self.mac_address} or wlan.ra == {self.mac_address}'
        elif self.device_type == "Station (STA)":
            filter_expr = f'wlan.ta == {self.mac_address}'
        else:
            logger.error("Не определена роль устройства, мониторинг невозможен")
            return

        cmd = [
            'tshark', '-l', '-i', self.interface,
            '-T', 'fields', '-E', 'separator= ',
            '-e', 'frame.number', '-e', 'wlan_radio.signal_dbm',
            '-Y', filter_expr
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            logger.info(f"Запущен tshark с фильтром: {filter_expr}")
            self._update_status(f"Мониторинг RSSI ({self.device_type})", "green")

            while not self.paused:  # Проверяем флаг паузы на каждой итерации
                try:
                    # Читаем линию из stdin
                    line = await process.stdout.readline()
                    if not line:
                        logger.warning("tshark завершил работу (stdout пуст)")
                        break
                    # Обработка полученной линии аналогична прошлой реализации
                    # ...
                except asyncio.CancelledError:
                    # Если задача была отменена, корректно завершаем её
                    logger.info("Задача мониторинга была отменена")
                    break
                except Exception as e:
                    logger.error(f"Ошибка мониторинга: {e}", exc_info=True)
                    if self.winfo_exists():  # Только если окно существует
                        self._update_status(f"Ошибка: {e}", "red")

            # Завершаем процесс tshark после выхода из цикла
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()

        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}", exc_info=True)
            if self.winfo_exists():  # Только если окно существует
                self._update_status(f"Ошибка: {e}", "red")

    def _process_rssi(self, pack_num: str, rssi: int):
        """Обрабатывает полученное значение RSSI."""
        current_time = time.time()
        self.last_valid_time = current_time

        # Проверяем существование окна (не разрушилось?)
        if not self.winfo_exists():
            return

        # Обновляем метки UI
        self.labels["Текущий кадр"]["text"] = pack_num
        self.labels["RSSI"]["text"] = f"{rssi} dBm"

        # Добавляем в буферы
        self.rssi_values.append(rssi)
        self.timestamps.append(current_time)

        # Применяем EMA-фильтр, если включен
        if self.use_filter_var.get():
            if self.ema_value is None:
                self.ema_value = rssi
            else:
                self.ema_value = self.alpha * rssi + (1 - self.alpha) * self.ema_value
            filtered_rssi = round(self.ema_value)
        else:
            filtered_rssi = rssi

        # Для графика используем фильтрованное значение
        self.rssi_buffer.append(filtered_rssi)

    def schedule_plot_update(self):
        """Планирует периодическое обновление графика."""
        self._update_plot()
        self.after(PLOT_UPDATE_INTERVAL_MS, self.schedule_plot_update)

    def _update_plot(self):
        """Перерисовывает график с прокруткой вправо и заливкой."""
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
        self.ax.plot(x_data, self.rssi_values, color='blue', linewidth=1.5, zorder=2)

        # Заливка
        self.ax.fill_between(
            x_data, self.rssi_values, -100,
            color='skyblue', alpha=0.4, zorder=1
        )

        # Окно просмотра
        window_sec = 60
        x_min = max(0, x_data[-1] - window_sec)
        x_max = x_data[0]
        self.ax.set_xlim(x_max, x_min)

        self.canvas.draw()

    def _setup_ui(self, manufacturer, channel):
        # Основной grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=5)

        # Левый контейнер
        left_frame = tk.Frame(self, padx=5, pady=5)
        left_frame.grid(row=0, column=0, sticky="nsew")

        # Шапка таблицы
        headers = ["Характеристика", "Значение"]
        for col, header in enumerate(headers):
            hdr = tk.Label(
                left_frame, text=header, relief=tk.RAISED,
                padx=8, pady=4, font=("Arial", 11, "bold"),
                bg="#f0f0f0", width=15
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
        row_idx = 0
        for idx, (key, _) in enumerate(rows):
            key_label = tk.Label(left_frame, text=key, anchor="w", width=15, font=("Arial", 10), padx=5)
            key_label.grid(row=row_idx+1, column=0, sticky="w", pady=2)

            if idx == 0:
                value_widget = tk.Text(left_frame, height=1, width=18, state="normal", font=("Arial", 10),
                                      borderwidth=0, highlightthickness=0, background="#EFEFEF")
                value_widget.insert("1.0", self.mac_address)
                value_widget.tag_add("centered", "1.0", "end")
                value_widget.tag_configure("centered", justify="center")
                value_widget.config(state="disabled")
                value_widget.grid(row=row_idx+1, column=1, sticky="w", pady=2)
                self.create_context_menu(value_widget)
            else:
                value_label = tk.Label(left_frame, text=_ or "", anchor="w", font=("Arial", 10), padx=5, width=18)
                value_label.grid(row=row_idx+1, column=1, sticky="w", pady=2)
            self.labels[key] = value_widget if idx == 0 else value_label
            row_idx += 1

        # Панель управления
        control_frame = tk.Frame(left_frame, pady=10)
        control_frame.grid(row=len(rows)+1, column=0, columnspan=2, sticky="ew")
        control_frame.columnconfigure(1, weight=2)

        self.pause_start_button = tk.Button(
            control_frame, text="Пауза", command=self.toggle_pause, font=("Arial", 10), width=10
        )
        self.pause_start_button.grid(row=0, column=0, padx=3, pady=5)

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
            left_frame, text="Определение роли устройства...",
            fg="orange", font=("Arial", 9), anchor="w"
        )
        self.status_label.grid(row=len(rows)+2, column=0, columnspan=2, sticky="w", pady=2)

        # Инициализация данных для графика
        self.rssi_buffer = []
        self.ema_value = None
        self.use_filter_var = tk.BooleanVar(value=True)
        self.alpha = EMA_ALPHA

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

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_start_button.config(text="Старт")
            # При постановке на паузу отменяем текущую задачу
            if self.task and not self.task.done():
                self.task.cancel()
        else:
            self.pause_start_button.config(text="Пауза")
            # При снятии паузы создаем новую задачу
            self.task = main_loop.create_task(self._run_tshark_monitor())

    def on_closing(self):
        logger.info("Закрытие окна мониторинга")
        self.paused = True  # Немедленно останавливаем обработку данных
        
        # Отменяем асинхронную задачу и ожидаем её завершения
        if self.task and not self.task.done():
            try:
                main_loop.call_soon_threadsafe(self.task.cancel)
                # Ждем завершения задачи в потоке asyncio
                future = asyncio.run_coroutine_threadsafe(asyncio.wait_for(self.task, timeout=2.0), main_loop)
                future.result()  # Блокируем до завершения
            except asyncio.CancelledError:
                logger.info("Задача была корректно отменена")
            except asyncio.TimeoutError:
                logger.warning("Время ожидания задачи истекло, выполняем форсированное завершение")
                self.task.cancel()
        
        # Останавливаем цикл asyncio
        self._stop_asyncio()
        logger.info("Ожидание завершения асинхронных задач...")
        self.destroy()  # Уничтожаем окно только после завершения задач

    def __del__(self):
        self._stop_asyncio()

    def _stop_asyncio(self):
        """Останавливает асинхронную задачу и цикл."""
        if self.task and not self.task.done():
            self.task.cancel()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

# --- Пример вызова (для тестирования) ---
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Скрываем главное окно

    # Пример вызова второго окна
    window = SecondWindow(
        parent=root,
        mac_address="7A:6C:06:3C:F7:DF",
        manufacturer="TP-Link",
        channel=6,
        interface="wlan1"
    )

    window.protocol("WM_DELETE_WINDOW", window.on_closing)
    window.mainloop()