import tkinter as tk
from tkinter import simpledialog, messagebox, Frame, Label, Checkbutton, Button, OptionMenu, StringVar, BooleanVar
# from config import interface
import utils

class ChannelSelectorDialog(simpledialog.Dialog):
    def __init__(self, parent, interface, channels=None, delay_time=None):
        """
        Конструктор принимает дополнительно два параметра:
        :param channels: list[int], список номеров выбранных каналов
        :param delay_time: float, время задержки (секунд)
        """
        self.parent = parent
        self.interface = interface
        self.channels = channels or []          # Переданные каналы
        self.delay_time = delay_time #or 1       # Переданное время задержки
        self.selected_channels = []            # Массив выбранных каналов
        super().__init__(parent, "Выбор каналов")

    def body(self, master):
        # Надпись сверху окна
        tk.Label(master, text="Выберите каналы для сканирования:", justify=tk.LEFT).pack(pady=5)

        # Контейнер для выбора каналов
        container = tk.Frame(master)
        container.pack(fill=tk.BOTH, expand=True)

        # Диапазон 2.4 GHz
        tk.Label(container, text="Диапазон 2.4 GHz").grid(row=0, column=0, sticky=tk.W)
        self.checkboxes_2_4 = []
        for i, ch in enumerate(range(1, 15)):
            var = tk.BooleanVar()
            cb = tk.Checkbutton(container, text=str(ch), variable=var)
            cb.grid(row=(i // 4), column=1 + (i % 4), sticky=tk.W)
            self.checkboxes_2_4.append((cb, var))

        # Кнопка для быстрого выбора/отмены диапазона 2.4 GHz
        self.btn_range_2_4 = tk.Button(
            container,
            text="Выбрать весь диапазон",
            command=lambda: self.toggle_range_selection(self.checkboxes_2_4),
            width=2, height=1, font=("Arial", 8)
        )
        self.btn_range_2_4.grid(row=2, column=0, columnspan=1, sticky=tk.EW)

        # Диапазон 5 GHz
        tk.Label(container, text="Диапазон 5 GHz").grid(row=4, column=0, sticky=tk.W)
        self.checkboxes_5 = []
        five_g_hz_channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        for i, ch in enumerate(five_g_hz_channels):
            var = tk.BooleanVar()
            cb = tk.Checkbutton(container, text=str(ch), variable=var)
            cb.grid(row=5 + (i // 4), column=1 + (i % 4), sticky=tk.W)
            self.checkboxes_5.append((cb, var))

        # Кнопка для быстрого выбора/отмены диапазона 5 GHz
        self.btn_range_5 = tk.Button(
            container,
            text="Выбрать весь диапазон",
            command=lambda: self.toggle_range_selection(self.checkboxes_5),
            width=5, height=1, font=("Arial", 8)
        )
        self.btn_range_5.grid(row=8, column=0, columnspan=1, sticky=tk.EW)

        # Основная кнопка "Выбрать/снять все"
        self.toggle_button = tk.Button(
            master,
            text="Выбрать все",
            command=self.toggle_selection,
            width=30, height=1, font=("Arial", 10, 'bold')
        )
        self.toggle_button.pack(pady=5)

        # Выбор времени задержки (предварительно настроено)
        tk.Label(master, text="Время на канале (секунды):").pack()
        self.delay_options = ["0.25", "0.5", "1", "2"]
        self.delay_choice = tk.StringVar(value=self.delay_options[0])
        tk.OptionMenu(master, self.delay_choice, *self.delay_options).pack()

        # Заполняем предыдущие выбранные каналы
        for channel in self.channels:
            for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
                if int(widget["text"]) == channel:
                    var.set(True)
                    break

        # Заполняем предыдущее время задержки
        if self.delay_time:
            index = next((i for i, x in enumerate(self.delay_options) if float(x) == self.delay_time), None)
            if index is not None:
                self.delay_choice.set(self.delay_options[index])
        

        cur_channel = utils.get_current_channel()
        for checkbox_group in [self.checkboxes_2_4, self.checkboxes_5]:
            for widget, var in checkbox_group:
                if str(widget["text"]) == str(cur_channel):
                    var.set(True)                     # Ставим галочку
                    widget.config(font=("Arial", 11, "bold"))  # Делаем текст жирным
                    break

    def toggle_range_selection(self, group):
        all_vars = [var for _, var in group]
        initial_state = any(var.get() for var in all_vars)
        new_state = not initial_state
        for var in all_vars:
            var.set(new_state)
        button_text = "Снять весь диапазон" if new_state else "Выбрать весь диапазон"
        btn_widget = self.btn_range_2_4 if group is self.checkboxes_2_4 else self.btn_range_5
        btn_widget.config(text=button_text)

    def toggle_selection(self):
        current_state = bool(any(var.get() for _, var in self.checkboxes_2_4 + self.checkboxes_5))
        new_state = not current_state
        for _, var in self.checkboxes_2_4 + self.checkboxes_5:
            var.set(new_state)
        button_text = "Снять все" if new_state else "Выбрать все"
        self.toggle_button.config(text=button_text)

    def apply(self):
        selected_channels = []
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            if var.get():
                selected_channels.append(int(widget["text"]))
        delay_time = float(self.delay_choice.get())
        self.result = (selected_channels, delay_time)

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Скрываем основное окно
    # Примеры передачи предыдущих настроек:
    previous_channels = [1, 6, 10, 36]  # Например, были выбраны каналы 1, 6 и 11
    previous_delay = 0.5             # Предыдущая задержка была 0.5 секунды
    app = ChannelSelectorDialog(root, "wlan1", channels=previous_channels, delay_time=previous_delay)
    # app = ChannelSelectorDialog(root, "wlan1")
    root.mainloop()