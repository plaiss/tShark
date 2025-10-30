import time
import signal
import subprocess

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog

#
import utils
from config import _stop
import config
from wifi_monitor import WifiMonitor  # Импортируем класс из отдельного файла



class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Настройки")
        self.geometry("400x300")

        # Интерфейс настройки пока пустой, можно расширить позже
        save_btn = tk.Button(self, text="Сохранить", command=self.save_settings)
        save_btn.pack(pady=10)

    def save_settings(self):
        # Здесь реализуйте сохранение настроек
        pass


def tshark_worker(root, cmd, ttl):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
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
            if len(parts) < 2:
                continue
            raw_time = parts[0]
            mac = parts[1] if len(parts) > 1 else ""
            rssi = parts[2] if len(parts) > 2 else ""
            subtype = parts[3] if len(parts) > 3 else ""

            mac_n = utils.normalize_mac(mac)
            if not mac_n:
                continue

            if config._whitelist:
                allowed = mac_n not in config._whitelist
            else:
                allowed = True

            now = time.time()
            with config._seen_lock:
                last = config._last_seen.get(mac_n)
                if last is not None:
                    if ttl is None:
                        continue
                    if now - last <= ttl:
                        continue
                config._last_seen[mac_n] = now
                config._seen_count[mac_n] = config._seen_count.get(mac_n, 0) + 1

            pretty_time = utils.parse_time_epoch(raw_time)
            mac = utils.lookup_vendor_db(mac)
            if len(mac) <= 50:
                dop = 50 - len(mac)
                mac = mac + ' ' * dop
            else:
                mac = mac[:50]

            root.update_tree(mac_n, utils.lookup_vendor_db(mac_n, config.DB_PATH, False), rssi, pretty_time)
            root.add_text(f"{mac} | {rssi} dBi | {utils.decode_wlan_type_subtype(subtype)} | {pretty_time}")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass

def main():
    global WHITELIST_PATH, SEEN_TTL_SECONDS
    root = WifiMonitor()

    # cmd = config.TSHARK_CMD
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

    if SEEN_TTL_SECONDS is not None:
        t = threading.Thread(target=utils.seen_cleaner, args=(SEEN_TTL_SECONDS,), daemon=True)
        t.start()

    if utils.get_wlan_mode(config.interface) == 'Monitor':
        # Запускаем поток и передаем ссылку на него в класс App
        tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD, SEEN_TTL_SECONDS), daemon=True)
        tshark_thread.start()
        root.tshark_thread = tshark_thread  # Присваиваем ссылку на поток в экземпляр App

    root.mainloop()

if __name__ == "__main__":
    main()