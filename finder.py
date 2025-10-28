import subprocess
import re
import threading
from tkinter import *


# Функция для запуска процесса tshark и считывания значений RSSI
def start_tshark(mac_address):
    global rssi_value

    # Команда tshark с фильтром по MAC адрессу
    # cmd = f'tshark -i wlan1 -Y "wlan.addr=={mac_address}" -T fields -e radiotap.dbm_antsignal'
    # cmd = f'tshark -i wlan1 -Y "wlan.addr eq {mac_address})" -T fields -e radiotap.dbm_antsignal'
    # cmd = f'tshark -i wlan1 -Y "wlan.addr == {mac_address}" -T fields -e radiotap.dbm_antsignal'

    cmd= [
        "tshark", "-i", "wlan0", "-l", "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "wlan.sa",
        "-e", "wlan_radio.signal_dbm",
        "-e", "wlan.fc.type_subtype"
    ]

    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)

    while True:
        output = process.stdout.readline().decode('utf-8').strip()

        if not output:
            break

        try:
            # Парсим значение RSSI
            rssi_match = re.search(r'-?\d+', output)
            if rssi_match:
                rssi_value.set(f"{rssi_match.group()}")
        except Exception as e:
            print("Ошибка:", str(e))


# Функционал обновления окна
def update_gui():
    root.after(1000, update_gui)  # Повторять обновление каждую секунду


# Основной поток программы
if __name__ == "__main__":
    # mac_address = input("Введите MAC адрес устройства: ")
    mac_address = '48:8B:0A:A1:05:70'

    root = Tk()
    root.title("Монитор RSSI")

    label_mac = Label(root, text=f"МAC адрес: {mac_address}", font=("Arial", 14))
    label_mac.pack(pady=10)

    rssi_value = StringVar(value="Нет данных")
    label_rssi = Label(root, textvariable=rssi_value, font=("Arial", 18))
    label_rssi.pack(pady=10)

    # Создаем фоновый поток для чтения данных tshark
    thread = threading.Thread(target=start_tshark, args=(mac_address,))
    thread.daemon = True
    thread.start()

    # Периодическое обновление интерфейса
    update_gui()

    root.mainloop()