import time
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog
import utils
from config import _stop
import config
from wifi_monitor import WifiMonitor  # Импортируем класс из отдельного файла
from collections import deque
import queue
import logging
from packet_processor import tshark_worker

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Глобальные переменные для управления буферами
tree_buffer = deque(maxlen=1000)
log_queue = queue.Queue()

# Функция сброса буферов
def flush_buffers(root):
    logging.info("flush_buffers: tree_buffer size=%d, log_queue size=%d", len(tree_buffer), log_queue.qsize())
    # Массовое обновление дерева
    while tree_buffer:
        mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes = tree_buffer.popleft()
        root.update_tree(mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes)

    # Сообщения лога
    messages = []
    while not log_queue.empty():
        messages.append(log_queue.get())
    logging.info("flush_buffers: выведено %d сообщений", len(messages))
    if messages:
        root.add_text("\n".join(messages))

# Планирование периодической очистки буферов
def schedule_flush(root):
    root.after(1000, lambda: flush_buffers(root))  # Повторять каждые 1000 мс
    root.after(1000, lambda: schedule_flush(root))  # Самозапланироваться через 1 сек


def main():
    global WHITELIST_PATH, SEEN_TTL_SECONDS
    root = WifiMonitor()
    WHITELIST_PATH = config.WHITELIST_PATH
    SEEN_TTL_SECONDS = config.SEEN_TTL_SECONDS
    if WHITELIST_PATH:
        with config._whitelist_lock:
            config._whitelist.clear()
            config._whitelist.update(utils.load_whitelist(WHITELIST_PATH))

    try:
        signal.signal(signal.SIGHUP, utils.handle_sighup)
    except Exception:
        pass

    # Начинаем регулярное опустошение буферов
    schedule_flush(root)

    if SEEN_TTL_SECONDS is not None:
        t = threading.Thread(target=utils.seen_cleaner, args=(SEEN_TTL_SECONDS,), daemon=True)
        t.start()

    if utils.get_wlan_mode(config.interface) == 'Monitor':
        # Запускаем поток и передаем ссылку на него в класс App
        tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        tshark_thread.start()
        root.tshark_thread = tshark_thread  # Присваиваем ссылку на поток в экземпляр App

    root.mainloop()

if __name__ == "__main__":
    main()