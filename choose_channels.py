import tkinter as tk
from tkinter import simpledialog, messagebox, Frame, Label, Checkbutton, Button, OptionMenu, StringVar, BooleanVar
import utils

import subprocess
import re

class ChannelSelectorDialog(simpledialog.Dialog):
    def __init__(self, parent, interface, channels=None, delay_time=None):
        self.parent = parent
        self.interface = interface
        self.channels = channels or []
        self.delay_time = delay_time
        self.selected_channels = []
        super().__init__(parent, "Выбор каналов")

    def buttonbox(self):
        box = tk.Frame(self)
        
        tk.Button(
            box, text="OK", width=10, command=self.ok, default=tk.ACTIVE
        ).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(
            box, text="Cancel", width=10, command=self.cancel
        ).pack(side=tk.LEFT, padx=5, pady=5)
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def ok(self, event=None):
        if not self.validate():
            self.initial_focus.focus_set()
            return
        self.apply()
        self.cancel()

    def cancel(self, event=None):
        self.parent.focus_set()
        self.destroy()

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
                if str(widget["text"]) == str(cur_channel[0]):
                    var.set(True)                     
                    widget.config(font=("Arial", 11, "bold"))  
                    break
        
        # Получаем доступные каналы для интерфейса
        available_channels = self.get_available_channels(self.interface)
        # Отключаем неподдерживаемые каналы
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            channel_num = int(widget["text"])
            if channel_num not in available_channels:
                widget.config(state="disabled", fg="gray50")
                var.set(False)  
        

        # Контейнер для кнопок (внизу окна)
        button_frame = tk.Frame(master)
        button_frame.pack(pady=5, padx=10, fill=tk.X)

        # Кнопка OK
        ok_button = tk.Button(
            button_frame,
            text="OK",
            command=self.ok,
            width=10,
            height=20, 
            font=("Arial", 10),
            relief="flat",           
            bg="#4CAF50",          
            fg="white",             
            activebackground="#45a049",
            activeforeground="white"
        )
        ok_button.pack(side=tk.LEFT, padx=10)

        # Кнопка Cancel
        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=10,
            font=("Arial", 10),
            relief="flat",
            bg="#f44336",          
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white"
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)

        self.geometry("350x450")  
        self.overrideredirect(True)  

        self.update_button_texts()

    def toggle_range_selection(self, group):
        all_vars = [var for _, var in group]
        initial_state = any(var.get() for var in all_vars)
        new_state = not initial_state
        
        for widget, var in group:
            if widget['state'] != 'disabled':
                var.set(new_state)
        self.update_button_texts()  # Обновить тексты после изменения
                
        button_text = "Снять весь диапазон" if new_state else "Выбрать весь диапазон"
        btn_widget = self.btn_range_2_4 if group is self.checkboxes_2_4 else self.btn_range_5
        btn_widget.config(text=button_text)

    def toggle_selection(self):
        current_state = bool(any(var.get() for _, var in self.checkboxes_2_4 + self.checkboxes_5))
        new_state = not current_state
        
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            if widget['state'] != 'disabled':
                var.set(new_state)
                
        button_text = "Снять все" if new_state else "Выбрать все"
        self.toggle_button.config(text=button_text)
        self.update_button_texts()  # Обновить тексты после изменения

    def apply(self):
        selected_channels = []
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            if var.get():
                selected_channels.append(int(widget["text"]))
        delay_time = float(self.delay_choice.get())
        self.result = (selected_channels, delay_time)

    def get_available_channels(self, interface):
        try:
            result = subprocess.run(
                ["iwlist", interface, "channel"],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout

            channels = set()
            for line in output.splitlines():
                match = re.search(r"Channel\s+(\d+)\s*:", line)
                if match:
                    channels.add(int(match.group(1)))
            return channels

        except subprocess.CalledProcessError as e:
            print(f"Ошибка при выполнении iwlist: {e}")
            return set()
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            return set()
        
    def update_button_texts(self):
        """Обновляет текст на кнопках в зависимости от текущего состояния чекбоксов."""
        
        # Проверяем, есть ли хотя бы один отмеченный канал в 2.4 GHz
        any_2_4_selected = any(var.get() for _, var in self.checkboxes_2_4)
        # Обновляем кнопку для диапазона 2.4 GHz
        self.btn_range_2_4.config(
            text="Снять весь диапазон" if any_2_4_selected else "Выбрать весь диапазон"
        )

        # Проверяем, есть ли хотя бы один отмеченный канал в 5 GHz
        any_5_selected = any(var.get() for _, var in self.checkboxes_5)
        # Обновляем кнопку для диапазона 5 GHz
        self.btn_range_5.config(
            text="Снять весь диапазон" if any_5_selected else "Выбрать весь диапазон"
        )

        # Проверяем, есть ли хоть один отмеченный канал в обоих диапазонах
        any_selected = any_2_4_selected or any_5_selected
        # Обновляем основную кнопку «Выбрать/снять все»
        self.toggle_button.config(
            text="Снять все" if any_selected else "Выбрать все"
    )


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  
    previous_channels = [1, 6, 10, 36]  
    previous_delay = 0.5              
    app = ChannelSelectorDialog(root, "wlan1", channels=previous_channels, delay_time=previous_delay)
    root.mainloop()