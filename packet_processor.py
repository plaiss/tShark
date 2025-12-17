import subprocess
import threading
import time
import config
import utils
import logging
from collections import deque
import queue

# Глобальные буферы (можно перенести в config.py)
tree_buffer = deque(maxlen=1000)
log_queue = queue.Queue()

def tshark_worker(root, cmd, ttl):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        logging.info("Процесс tshark запущен, PID: %d", proc.pid)
    except Exception as e:
        logging.error("Ошибка при старте tshark: %s", e)
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

            useful_bytes = 0
            if not subtype.startswith(("Beacon", "Probe Response", "Probe Request")):
                useful_bytes = len(raw.encode('utf-8'))

            config._traffic_by_mac[mac_n] = config._traffic_by_mac.get(mac_n, 0) + useful_bytes

            if config._whitelist:
                allowed = mac_n not in config._whitelist
            else:
                allowed = True

            if not allowed:
                continue

            now = time.time()
            with config._seen_lock:
                config._seen_count[mac_n] = config._seen_count.get(mac_n, 0) + 1
                mac_count = config._seen_count[mac_n]
                config._last_seen[mac_n] = now

            pretty_time = utils.parse_time_epoch(raw_time)
            mac_vendor = utils.lookup_vendor_db(mac_n, config.DB_PATH, False)

            tree_buffer.append((mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, config._traffic_by_mac.get(mac_n)))
            log_queue.put(f"{mac}|{rssi}| {utils.decode_wlan_type_subtype(subtype)} | {pretty_time} | Канал: {channel}")
            root.debug_status()

    finally:
        root.clean_buffers(controlled=True)
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        root.clean_buffers()
