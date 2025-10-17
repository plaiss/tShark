# main.py
import threading
import time
import signal
import sys
import subprocess

import config
import gui
# import worker
import utils


def tshark_worker(root, cmd, ttl):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    except Exception as e:
        root.add_text(f"Ошибка при старте tshark: {e}")
        config._stop.set()
        return

    def stderr_reader():
        for line in proc.stderr:
            # root.add_text(f"[tshark stderr] {line.rstrip()}")
             root.add_text(f"[$$$$$$$$] {line.rstrip()}")

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
            mac = utils.lookup_vendor_db(mac, config.DB_PATH)
            if len(mac) <= 50:
                dop = 50 - len(mac)
                mac = mac + ' ' * dop
            else:
                mac = mac[:50]

            # Обновляем таблицу TreeView
            root.update_tree(mac_n, mac_n, pretty_time)
            # root.update_tree(mac_n, config._seen_count[mac_n], pretty_time)

            # Отправляем вывод в окно приложения
            root.add_text(f"{pretty_time} Mac={mac} {rssi} dBi Type: {utils.decode_wlan_type_subtype(subtype)}")
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
    root = gui.App()

    cmd = config.TSHARK_CMD
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

    tshark_thread = threading.Thread(target=tshark_worker, args=(root, cmd, SEEN_TTL_SECONDS), daemon=True)
    tshark_thread.start()

    def refresh_status():
        total_devices = len(config._last_seen)
        devices_in_white_list = sum(1 for mac in config._last_seen if mac in config._whitelist)
        root.update_status(total_devices, devices_in_white_list)
        root.after(1000, refresh_status)

    refresh_status()

    root.mainloop()

if __name__ == "__main__":
    main()