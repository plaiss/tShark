import tkinter as tk
from tkinter import messagebox
import os
import re
import utils

# Глобальная переменная с состоянием интерфейса
interface = "wlan1"  # Текущий интерфейс (можете заменить на свою глобальную переменную)


# Класс окна настроек
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Network Interface Settings")
        self.geometry("800x600")  # Изменяем размер окна
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
        available_interfaces = ["eth0", "wlan0", "wlan1"]
        self.var_interface = tk.StringVar(value=interface)
        
        # Выпадающий список для выбора интерфейса
        dropdown = tk.OptionMenu(self, self.var_interface, *available_interfaces)
        dropdown.config(width=30)
        dropdown.pack(pady=20)
        
        # Кнопки ОК и Cancel
        button_frame = tk.Frame(self)
        button_frame.pack(pady=20)
        
        button_ok = tk.Button(button_frame, text="Apply Changes", command=self.apply_settings)
        button_cancel = tk.Button(button_frame, text="Cancel", command=self.destroy)
        
        button_ok.pack(side="left", padx=10)
        button_cancel.pack(side="right", padx=10)
    
    def apply_settings(self):
        """Применяет выбранный интерфейс"""
        new_interface = self.var_interface.get()
        global interface
        interface = new_interface
        messagebox.showinfo("Success", f"Changed network interface to {new_interface}. Please restart the application.")
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SettingsWindow(root)
    root.mainloop()