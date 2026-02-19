import customtkinter as ctk
import tkinter as tk
import utils
import config
import subprocess
import re



class ChannelSelectorDialog(ctk.CTkToplevel):
    def __init__(self, parent, interface, channels=None, delay_time=None):
        super().__init__(parent)
        self.parent = parent
        self.interface = interface
        self.channels = channels or []
        self.delay_time = delay_time
        self.selected_channels = []

        # Настройка окна
        self.title("Выбор каналов")
        self.geometry("450x600")
        self.resizable(False, False)
        self.transient(parent)  # Модальное окно

        # Основной фрейм
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Заголовок
        ctk.CTkLabel(
            main_frame,
            text="Выберите каналы для сканирования:",
            font=("TkDefaultFont", 12, "bold")
        ).pack(pady=(0, 10))

        # Контейнер для каналов
        container = ctk.CTkFrame(main_frame)
        container.pack(fill="both", expand=True, pady=(0, 10))

        # Диапазон 2.4 GHz
        ctk.CTkLabel(container, text="Диапазон 2.4 GHz", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(5, 2)
        )

        # Кнопка для диапазона 2.4 GHz (слева от чекбоксов)
        self.btn_range_2_4 = ctk.CTkButton(
            container,
            text="Выбрать весь диапазон",
            command=lambda: self.toggle_range_selection(self.checkboxes_2_4),
            width=120,
            height=25,
            font=("Arial", 9)
        )
        self.btn_range_2_4.grid(row=1, column=0, rowspan=4, sticky="ns", padx=(0, 5), pady=(2, 0))

        # Чекбоксы для 2.4 GHz (начинаются с column=1)
        self.checkboxes_2_4 = []
        for i, ch in enumerate(range(1, 15)):
            var = tk.BooleanVar()
            cb = ctk.CTkCheckBox(container, text=str(ch), variable=var)
            cb.grid(row=(i // 4) + 1, column=1 + (i % 4), sticky="w", padx=2, pady=2)
            self.checkboxes_2_4.append((cb, var))


        # Диапазон 5 GHz
        ctk.CTkLabel(container, text="Диапазон 5 GHz", font=("TkDefaultFont", 11, "bold")).grid(
            row=5, column=0, sticky="w", pady=(10, 2)
        )

        # Кнопка для диапазона 5 GHz (слева от чекбоксов)
        self.btn_range_5 = ctk.CTkButton(
            container,
            text="Выбрать весь диапазон",
            command=lambda: self.toggle_range_selection(self.checkboxes_5),
            width=120,
            height=25,
            font=("Arial", 9)
        )
        self.btn_range_5.grid(row=6, column=0, rowspan=6, sticky="ns", padx=(0, 5), pady=(2, 0))


        # Чекбоксы для 5 GHz (начинаются с column=1)
        self.checkboxes_5 = []
        five_g_hz_channels = [
            36, 40, 44, 48, 52, 56, 60, 64,
            100, 104, 108, 112, 116, 120, 124, 128,
            132, 136, 140, 144, 149, 153, 157, 161, 165
        ]
        for i, ch in enumerate(five_g_hz_channels):
            var = tk.BooleanVar()
            cb = ctk.CTkCheckBox(container, text=str(ch), variable=var)
            cb.grid(row=6 + (i // 5), column=1 + (i % 5), sticky="w", padx=2, pady=2)
            self.checkboxes_5.append((cb, var))


        # Основная кнопка "Выбрать/снять все"
        self.toggle_button = ctk.CTkButton(
            main_frame,
            text="Выбрать все",
            command=self.toggle_selection,
            width=200,
            height=30,
            font=("Arial", 10, "bold"),
            fg_color="#4CAF50",
            hover_color="#45a049"
        )
        self.toggle_button.pack(pady=10)


        # Время задержки
        ctk.CTkLabel(main_frame, text="Время на канале (секунды):", font=("TkDefaultFont", 11)).pack(pady=(5, 2))
        self.delay_options = ["0.25", "0.5", "1", "2"]
        self.delay_choice = tk.StringVar(value=self.delay_options[0])
        delay_menu = ctk.CTkOptionMenu(
            main_frame,
            values=self.delay_options,
            variable=self.delay_choice,
            width=150
        )
        delay_menu.pack(pady=(0, 15))

        # Кнопки OK/Cancel
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=10)

        ctk.CTkButton(
            button_frame,
            text="OK",
            command=self.ok,
            width=100,
            height=40,
            font=("Arial", 10),
            fg_color="#4CAF50",
            hover_color="#45a049",
            text_color="white"
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=100,
            height=40,
            font=("Arial", 10),
            fg_color="#f44336",
            hover_color="#d32f2f",
            text_color="white"
        ).pack(side="right", padx=10)

        # Инициализация состояния
        self._init_state()

        # Переносим grab_set() в конец (после отображения окна)
        self.after(100, self._setup_modal)

    def _setup_modal(self):
        """Устанавливает модальность после отображения окна."""
        try:
            self.grab_set()  # Захват фокуса
            self.focus_force()  # Фокусируем окно
        except tk.TclError as e:
            print(f"[ERROR] Не удалось установить grab: {e}")
            # Если grab не удался, просто продолжаем без него
            pass

    def _init_state(self):
        # Заполняем выбранные каналы
        for channel in self.channels:
            for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
                if int(widget._text) == channel:
                    var.set(True)
                    break

        # Заполняем время задержки
        if self.delay_time:
            index = next((i for i, x in enumerate(self.delay_options) if float(x) == self.delay_time), None)
            if index is not None:
                self.delay_choice.set(self.delay_options[index])

        # Получаем доступные каналы
        available_channels = utils.get_available_channels(config.interface)
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            channel_num = int(widget._text)
            if channel_num not in available_channels:
                widget.configure(state="disabled", text=f"{channel_num} (N/A)")
            else:
                widget.configure(state="normal")

    def toggle_selection(self):
        """Переключает состояние всех чекбоксов (выбрать всё / снять всё)."""
        current_text = self.toggle_button._text
        if current_text == "Выбрать все":
            for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
                if widget.cget("state") != "disabled":
                    var.set(True)
            self.toggle_button.configure(text="Снять все")
        else:
            for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
                var.set(False)
            self.toggle_button.configure(text="Выбрать все")


    def toggle_range_selection(self, checkbox_list):
        """Переключает выбор для указанного диапазона каналов."""
        any_checked = any(var.get() for _, var in checkbox_list)
        for widget, var in checkbox_list:
            if widget.cget("state") != "disabled":
                var.set(not any_checked)


    def ok(self):
        """Обработчик кнопки OK — собирает выбранные данные и закрывает окно."""
        self.selected_channels = []
        for widget, var in self.checkboxes_2_4 + self.checkboxes_5:
            if var.get():
                self.selected_channels.append(int(widget._text))

        self.delay_time = float(self.delay_choice.get())
        self.destroy()

    def cancel(self):
        """Обработчик кнопки Cancel — закрывает окно без сохранения."""
        self.selected_channels = None
        self.delay_time = None
        self.destroy()

    def get_result(self):
        """Возвращает выбранные каналы и время задержки после закрытия окна."""
        return self.selected_channels, self.delay_time
