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

# Глобальные переменные для управления буферами
# tree_buffer = deque(maxlen=1000)
# log_queue = queue.Queue()

# Функция сброса буферов
def flush_buffers(root):
    # Массовое обновление дерева
    while root.tree_buffer:
        # Извлекаем ровно столько же значений, сколько помещено в буфер
        mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes = root.tree_buffer.popleft()
        root.update_tree(mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, useful_bytes)

    # Сообщения лога
    messages = []
    while not root.log_queue.empty():  # Аналогично для log_queue
        messages.append(root.log_queue.get())
    if messages:
        root.add_text("\n".join(messages))

# Планирование периодической очистки буферов
def schedule_flush(root):
    root.after(1000, lambda: flush_buffers(root))  # Повторять каждые 1 сек
    root.after(1000, lambda: schedule_flush(root))  # Самозапланироваться через 1 сек

def tshark_worker(root, cmd, ttl):
    # Внутри функции используй root.tree_buffer и root.log_queue
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        root.add_text(f"Ошибка при старте tshark: {e}")
        config._stop.set()
        return

    def stderr_reader():
        for line in proc.stderr:
            root.add_text(f"{line.rstrip()}")

    threading.Thread(target=stderr_reader, daemon=True).start()

    try:
        for raw in proc.stdout:
            if config._stop.is_set():
                break
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parts = raw.split("\t")
            if len(parts) < 5:
                continue
            
            raw_time = parts[0]
            mac = parts[1] if len(parts) > 1 else ""
            rssi = parts[2] if len(parts) > 2 else ""
            channel = parts[3] if len(parts) > 3 else ""
            subtype = parts[4] if len(parts) > 4 else ""

            mac_n = utils.normalize_mac(mac)
            if not mac_n:
                continue
                    
            # Вычисляем размер полезных данных (исключая служебные фреймы)
            useful_bytes = 0
            if not subtype.startswith(("Beacon", "Probe Response", "Probe Request")):
                useful_bytes = len(raw.encode('utf-8'))
                
            # Накапливаем полезный трафик для каждого MAC-адреса
            global _traffic_by_mac
            config._traffic_by_mac[mac_n] = config._traffic_by_mac.get(mac_n, 0) + useful_bytes

            # Проверка белого списка
            if config._whitelist:
                allowed = mac_n not in config._whitelist
            else:
                allowed = True

            if not allowed:
                continue  # Пропускаем пакет, если он запрещён

            now = time.time()
            with config._seen_lock:
                # Повышаем счетчик независимо от времени TTL
                config._seen_count[mac_n] = config._seen_count.get(mac_n, 0) + 1
                mac_count = config._seen_count[mac_n]
                # Обновляем время последнего обнаружения
                config._last_seen[mac_n] = now

            pretty_time = utils.parse_time_epoch(raw_time)
            mac_vendor = utils.lookup_vendor_db(mac_n, config.DB_PATH, False)
            
            # Складываем данные в буферы класса
            root.tree_buffer.append((mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, config._traffic_by_mac.get(mac_n)))
            root.log_queue.put(f"{mac}|{rssi}| {utils.decode_wlan_type_subtype(subtype)} | {pretty_time} | Канал: {channel}")

            # Постоянная диагностика
            root.debug_status()

    finally:
        # Здесь можно дополнительно очистить данные
        root.clean_buffers(controlled=True)  # Применяем контролируемую очистку
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=10) # одна секунда достаточна /!!!!!!!!!!!!!!!!!!!!!
        except Exception:
            pass
        # Завершаем очистку буферов
        root.clean_buffers()

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
        # tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD, SEEN_TTL_SECONDS), daemon=True)
        tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD, config.SEEN_TTL_SECONDS), daemon=True)
        tshark_thread.start()
        root.tshark_thread = tshark_thread  # Присваиваем ссылку на поток в экземпляр App

    root.mainloop()

if __name__ == "__main__":
    main()