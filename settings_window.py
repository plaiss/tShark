import tkinter as tk
from tkinter import messagebox
import os
import re
import utils
import config
import oui_to_sqlite

# Глобальная переменная с состоянием интерфейса
# interface = "wlan1"  # Текущий интерфейс (можете заменить на свою глобальную переменную)

# Класс окна настроек
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Network Interface Settings")
        self.geometry("800x400")  # Изменяем размер окна
        self.resizable(True, True)  # Разрешаем изменение размеров окна
        
        # Метка с указанием текущего интерфейса
        current_interface_label = tk.Label(self, text=f"Current Network Interface: {interface}")
        current_interface_label.pack(pady=(20, 10))
        
        # Получаем информацию о Wi-Fi канале
        try:
            wifi_info = os.popen(f"iw dev {interface} info").read()
            channel_num, frequency = utils.parse_wifi_info(wifi_info)
            
            # Лейбл с информацией о Wi-Fi канале
            wifi_channel_label = tk.Label(
                self,
                text=f"Wi-Fi Channel Information:\nChannel Number: {channel_num}\nFrequency: {frequency}",
                justify='center',
                font=('Arial', 12),
                bg='#f0f0f0'
            )
            wifi_channel_label.pack(fill='both', expand=True, pady=20)
        except Exception as e:
            error_message = f"Error retrieving Wi-Fi information: {e}"
            print(error_message)
            messagebox.showerror("Wi-Fi Info Error", error_message)
        
        # Список доступных интерфейсов (пример)
        available_interfaces = ["eth0", "wlan0", "wlan1"] # нужно будет заменить на IWLIST
        self.var_interface = tk.StringVar(value=interface)
        
        # Выпадающий список для выбора интерфейса
        dropdown = tk.OptionMenu(self, self.var_interface, *available_interfaces)
        dropdown.config(width=30)
        dropdown.pack(pady=20)
        
        # Кнопка обновления БД OUI
        update_oui_button = tk.Button(
            self,
            text="Обновить БД OUI",
            command=self.update_oui_db,
            bg="#4CAF50",  # Зелёный фон для акцента
            fg="white",
            font=("Arial", 10, "bold")
        )
        update_oui_button.pack(pady=15)
        
        # Кнопки ОК и Cancel
        button_frame = tk.Frame(self)
        button_frame.pack(pady=20)
        
        button_ok = tk.Button(button_frame, text="Apply Changes", command=self.apply_settings)
        button_cancel = tk.Button(button_frame, text="Cancel", command=self.destroy)
        
        button_ok.pack(side="left", padx=10)
        button_cancel.pack(side="right", padx=10)
    
    def update_oui_db(self):
        """Обработчик кнопки «Обновить БД OUI»"""
        try:
            oui_to_sqlite.build_db()
            messagebox.showinfo("Успех", "База данных OUI успешно обновлена!")
        except Exception as e:
            error_msg = f"Ошибка при обновлении БД OUI:\n{str(e)}"
            messagebox.showerror("Ошибка", error_msg)
            print(f"Exception in update_oui_db: {e}")
    
    def apply_settings(self):
        """Применяет выбранный интерфейс"""
        new_interface = self.var_interface.get()
        global interface
        config.interface = new_interface
        messagebox.showinfo("Success", f"Changed network interface to {new_interface}. Please restart the scanning.")
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SettingsWindow(root)
    root.mainloop()
