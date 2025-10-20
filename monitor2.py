
#!/usr/bin/env python3
# coding: utf-8

import argparse
import subprocess
import threading
import time
import signal
import sys
import re



# Конфигурация по умолчанию
TSHARK_CMD = ["tshark", "-i", "wlan1", "-l", "-T", "fields",
              "-e", "frame.time_epoch",
              "-e", "wlan.sa",
              "-e", "wlan_radio.signal_dbm",
              "-e", "wlan.fc.type_subtype"]
WHITELIST_PATH = 'whitelist.txt'
# SEEN_TTL_SECONDS = 30  # если None — не очищать по времени
SEEN_TTL_SECONDS = None  # если None — не очищать по времени

# Глобальные структуры и блокировки
_whitelist = set()
_whitelist_lock = threading.Lock()

# Используем словарь mac -> last_seen_timestamp для точной TTL-логики
_last_seen = {}
_seen_lock = threading.Lock()

_stop = threading.Event()

MAC_RE = re.compile(r'[^0-9a-f]')

# Преобразует любую форму MAC (aa:bb:cc:dd:ee:ff, aabb.ccdd.eeff, AA-BB-CC-...) в OUI и возвращает производителя


import sqlite3

DB_PATH = "oui.db"

def normalize_mac_OUI(mac):
    s = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
    return s[:6] if len(s) >= 6 else None
    # return s if len(s) >= 6 else None
def normalize_mac(mac):
    s = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
    return s if len(s) >= 6 else None

def lookup_vendor_db(mac, db_path=DB_PATH):
    oui = normalize_mac_OUI(mac)
    if not oui:
        return None
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT org FROM oui WHERE oui = ?", (oui,))
        row = cur.fetchone()
        if is_locally_administered(mac):
            mac = mac + ' (locally administered)'
        else:

            if row[0]:
                mac = mac + ' ('+row[0] + ')'
            else:
                mac = None
        return mac


def is_locally_administered(mac: str) -> bool:
    """
    Проверяет, установлен ли бит локально администрируемого адреса (LAA) в MAC.

    Возвращает True если LAA (локально администрируемый), иначе False.
    Принимает MAC в виде строк:
      - "aa:bb:cc:dd:ee:ff"
      - "aa-bb-cc-dd-ee-ff"
      - "aabbccddeeff"
    """
    if not isinstance(mac, str):
        raise TypeError("mac must be a str")
    # Убираем разделители и пробелы, приводим к нижнему регистру
    s = mac.replace(":", "").replace("-", "").replace(".", "").strip().lower()
    if len(s) != 12 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError("invalid MAC address format")
    first_octet = int(s[0:2], 16)
    # Проверяем второй младший бит (0x02)
    return (first_octet & 0x02) != 0


def load_whitelist(path):
    s = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                mac = normalize_mac(line)
                if len(mac) == 12:
                    s.add(mac)
    except Exception as e:
        print(f"Failed to load whitelist {path}: {e}", file=sys.stderr)
    return s

def handle_sighup(signum, frame):
    # Перезагрузить whitelist при SIGHUP
    global WHITELIST_PATH
    if WHITELIST_PATH:
        with _whitelist_lock:
            _whitelist.clear()
            _whitelist.update(load_whitelist(WHITELIST_PATH))
        print("Whitelist reloaded", file=sys.stderr)

def seen_cleaner(ttl):
    if ttl is None:
        return
    while not _stop.wait(ttl):
        now = time.time()
        removed = 0
        with _seen_lock:
            keys = list(_last_seen.keys())
            for k in keys:
                if now - _last_seen.get(k, 0) > ttl:
                    _last_seen.pop(k, None)
                    removed += 1
        if removed:
            print(f"Removed {removed} entries from seen (TTL {ttl}s)", file=sys.stderr)

def parse_time_epoch(text):
    try:
        t = float(text)
        sec = int(t)
        ms = int((t - sec) * 1000)
        return f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))}.{ms:03d}"
    except Exception:
        return text


def decode_wlan_type_subtype(val, show_bits=True, show_codes=True):
    """
    Decode 802.11 frame control type/subtype and key control flags.
    val can be integer or string (e.g. "0x20" or 32). Expects the full Frame Control
    first two bytes value (least significant byte first typical order) or at least
    the first byte containing subtype/type and the second byte containing flags.
    By convention this function treats val as a 16-bit value where:
      - bits 0-3  : subtype
      - bits 4-5  : type
      - bit 6     : to DS
      - bit 7     : from DS
      - bit 8     : more frag (ignored)
      - bit 9     : retry (ignored)
      - bit 10    : pwr mgmt (ignored)
      - bit 11    : more data (ignored)
      - bit 12    : protected flag
      - bit 13    : order flag
    Returns a human-readable string.
    """
    try:
        n = int(val, 0)
    except Exception:
        return str(val)

    subtype = n & 0xF
    type_ = (n >> 4) & 0x3   # bits 4-5 when considering full frame-control little mapping
    # If input was the single first byte, original mapping (bits 0-3 subtype, 2-3 type) may apply.
    # This implementation assumes standard 16-bit Frame Control ordering where type is bits 2-3 of first byte,
    # but when packed into a 16-bit integer with first byte in LSB, shifting by 4 yields same result.
    # Extract flags (ToDS/FromDS are bits 8 and 9 in network-order 16-bit, but practical captures often place them in second byte)
    to_ds = (n >> 8) & 0x1
    from_ds = (n >> 9) & 0x1
    protected = (n >> 14) & 0x1
    order = (n >> 15) & 0x1

    mgmt_subtypes = {
        0: "Assoc Req",
        1: "Assoc Resp",
        2: "Reassoc Req",
        3: "Reassoc Resp",
        4: "Probe Req",
        5: "Probe Resp",
        6: "Reserved",
        7: "Reserved",
        8: "Beacon",
        9: "ATIM",
        10: "Disassoc",
        11: "Auth",
        12: "Deauth",
        13: "Action",
        14: "Action No Ack",
        15: "Reserved"
    }

    ctrl_subtypes = {
        0: "Reserved",
        1: "Reserved",
        2: "Trigger",
        3: "Block Ack Poll",
        4: "Block Ack",
        5: "PS-Poll",
        6: "RTS",
        7: "CTS",
        8: "ACK",
        9: "CF-End",
        10: "CF-End + CF-Ack",
        11: "Control Wrapper",
        12: "Block Ack Req",
        13: "Block Ack (Alt)",
        14: "Vendor/Reserved",
        15: "Vendor/Reserved"
    }

    data_subtypes = {
        0: "Data",
        1: "Data + CF-Ack",
        2: "Data + CF-Poll",
        3: "Data + CF-Ack + CF-Poll",
        4: "Null (No Data)",
        5: "CF-Ack (No Data)",
        6: "CF-Poll (No Data)",
        7: "CF-Ack + CF-Poll (No Data)",
        8: "QoS Data",
        9: "QoS Data + CF-Ack",
        10: "QoS Data + CF-Poll",
        11: "QoS Data + CF-Ack + CF-Poll",
        12: "QoS Null (No Data)",
        13: "Reserved",
        14: "QoS CF-Poll (No Data)",
        15: "QoS CF-Ack + CF-Poll (No Data)"
    }

    type_map = {0: "Mgmt", 1: "Ctrl", 2: "Data", 3: "Reserved"}

    if type_ == 0:
        name = mgmt_subtypes.get(subtype, f"Unknown({subtype})")
    elif type_ == 1:
        name = ctrl_subtypes.get(subtype, f"Unknown({subtype})")
    elif type_ == 2:
        name = data_subtypes.get(subtype, f"Unknown({subtype})")
    else:
        name = f"ReservedType/Subtype({subtype})"

    parts = []
    parts.append(f"{type_map.get(type_, 'Unknown')}/{name}")
    if show_codes:
        parts.append(f"(type={type_} subtype={subtype})")

    if show_bits:
        parts.append(f"[ToDS={to_ds} FromDS={from_ds} Protected={protected} Order={order}]")

    return " ".join(parts)


def tshark_worker(cmd, ttl):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    except Exception as e:
        print(f"Failed to start tshark: {e}", file=sys.stderr)
        _stop.set()
        return

    # stderr reader для дебага
    def stderr_reader():
        for line in proc.stderr:
            print(f"[tshark stderr] {line.rstrip()}", file=sys.stderr)
    threading.Thread(target=stderr_reader, daemon=True).start()

    try:
        for raw in proc.stdout:
            if _stop.is_set():
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

            mac_n = normalize_mac(mac)
            if not mac_n:
                continue

            # with _whitelist_lock:
            #     allowed = True if not _whitelist else (mac_n not in _whitelist)
            # if not allowed:
            #     continue

            if _whitelist:
                allowed = mac_n not in _whitelist
            else:
                allowed = True

            now = time.time()
            with _seen_lock:
                last = _last_seen.get(mac_n)
                if last is not None:
                    # если TTL None — считаем всегда уже виденным
                    if ttl is None:
                        continue
                    if now - last <= ttl:
                        continue
                _last_seen[mac_n] = now

            pretty_time = parse_time_epoch(raw_time)
            mac = lookup_vendor_db(mac)
            if len(mac) <= 60:
                dop = 60 - len(mac)
                mac = mac + ' ' * dop
            else:
                mac = mac[:60]

            # print(f"{pretty_time}  {mac}  {rssi} dBi         {decode_wlan_type_subtype(subtype)}", flush=True)
            #print(f"{mac}", flush=True)
            print(f"{pretty_time} Mac={mac} {rssi} dBi Type: {decode_wlan_type_subtype(subtype)}", flush=True)
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
    parser = argparse.ArgumentParser(description="Print only unique MACs from tshark output")
    parser.add_argument("--tshark-cmd", nargs="+", help="Команда tshark (по умолчанию стандартная)", default=None)
    parser.add_argument("--whitelist", help="Путь к файлу whitelist (по одной записи MAC на строку)", default=None)
    parser.add_argument("--seen-ttl", type=int, help="TTL для списка seen в секундах (None — не очищать)", default=None)
    args = parser.parse_args()

    if args.tshark_cmd:
        cmd = args.tshark_cmd
    else:
        cmd = TSHARK_CMD

    WHITELIST_PATH = args.whitelist or WHITELIST_PATH
    # Если явно задан --seen-ttl, используем его; если не задан, оставляем глобальную константу
    SEEN_TTL_SECONDS = args.seen_ttl if args.seen_ttl is not None else SEEN_TTL_SECONDS

    if WHITELIST_PATH:
        with _whitelist_lock:
            _whitelist.clear()
            _whitelist.update(load_whitelist(WHITELIST_PATH))

    try:
        signal.signal(signal.SIGHUP, handle_sighup)
    except Exception:
        # На Windows signal.SIGHUP может отсутствовать
        pass

    # Запускаем cleaner, если задан TTL (None — не очищать; в нашем дизайне при TTL=None мы считаем "всегда уникальным")
    if SEEN_TTL_SECONDS is not None:
        t = threading.Thread(target=seen_cleaner, args=(SEEN_TTL_SECONDS,), daemon=True)
        t.start()

    try:
        tshark_worker(cmd, SEEN_TTL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()

if __name__ == "__main__":
    main()
