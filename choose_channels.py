import tkinter as tk
from tkinter import simpledialog, messagebox, Frame, Label, Checkbutton, Button, OptionMenu, StringVar, BooleanVar

class ChannelSelectorDialog(simpledialog.Dialog):
    def __init__(self, parent, interface):
        self.parent = parent
        self.interface = interface
        self.selected_channels = []       # Массив выбранных каналов
        self.delay_time = 1               # Задержка по умолчанию
        self.all_channels_selected = False  # Флаг текущего состояния
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
        for i, ch in enumerate(range(1, 14)):  # Каналы 2.4 GHz
            var = tk.BooleanVar()
            cb = tk.Checkbutton(container, text=str(ch), variable=var)
            cb.grid(row=i+1, column=0, sticky=tk.W)
            self.checkboxes_2_4.append((cb, var))

        # Диапазон 5 GHz
        tk.Label(container, text="Диапазон 5 GHz").grid(row=0, column=1, sticky=tk.W)
        self.checkboxes_5 = []
        five_g_hz_channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        for i, ch in enumerate(five_g_hz_channels):
            var = tk.BooleanVar()
            cb = tk.Checkbutton(container, text=str(ch), variable=var)
            cb.grid(row=i+1, column=1, sticky=tk.W)
            self.checkboxes_5.append((cb, var))

        # Кнопка "Выбрать/снять все"
        self.toggle_button = tk.Button(master, text="Выбрать все", command=self.toggle_selection)
        self.toggle_button.pack(pady=5)

        # Выбор времени задержки (предварительно настроено)
        tk.Label(master, text="Время на канале (секунды):").pack()
        self.delay_options = ["0.25", "0.5", "1", "2"]
        self.delay_choice = tk.StringVar(value=self.delay_options[2])
        tk.OptionMenu(master, self.delay_choice, *self.delay_options).pack()

    def toggle_selection(self):
        if self.all_channels_selected:
            # Снятие выделения всех каналов
            for _, var in self.checkboxes_2_4 + self.checkboxes_5:
                var.set(False)
            self.toggle_button.config(text="Выбрать все")
            self.all_channels_selected = False
        else:
            # Выбираем все каналы
            for _, var in self.checkboxes_2_4 + self.checkboxes_5:
                var.set(True)
            self.toggle_button.config(text="Снять все")
            self.all_channels_selected = True

    def validate(self):
        return True  # Ничего не проверяется

    def apply(self):
        self.selected_channels = []
        for widget, _ in self.checkboxes_2_4 + self.checkboxes_5:
            if _.get():  # Проверяем, отмечен ли чекбокс
                self.selected_channels.append(int(widget['text']))  # Забираем текст из самого чекбокса
        self.delay_time = float(self.delay_choice.get())  # Взять выбранное время задержки

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Скрываем основное окно
    app = ChannelSelectorDialog(root, "wlan0mon")  # Можете поменять интерфейс на нужный
    root.mainloop()