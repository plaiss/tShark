import tkinter as tk
from tkinter import simpledialog
import subprocess


# Функция перевода интерфейса в режим мониторинга
def enable_monitor_mode(interface, password):
    commands = [
        ['sudo', '-S', 'rfkill', 'unblock', 'wifi' ],
        ['sudo', '-S', 'ifconfig', interface, 'down'],
        ['sudo', '-S', 'iwconfig', interface, 'mode', 'monitor'],
        ['sudo', '-S', 'ifconfig', interface, 'up']
    ]

    for cmd in commands:
        try:
            result = subprocess.run(cmd, input=f"{password}\n", encoding="utf-8", check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Ошибка выполнения команды: {cmd}. Сообщение: {e.stderr}")
            return False

    print(f'Интерфейс {interface} успешно переведен в режим монитора.')
    return True


# Запускаем окно для ввода пароля
root = tk.Tk()
root.withdraw()  # Скрываем основное окно Tkinter

# Диалоговое окно для ввода пароля
password = simpledialog.askstring("Ввод пароля", "Введите пароль sudo:", show="*")

if password is not None and len(password.strip()) > 0:
    success = enable_monitor_mode('wlan1', password)
else:
    print("Операция отменена.")