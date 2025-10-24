import re
import sqlite3
import time
import subprocess
import subprocess
import getpass

import config
import main

def handle_sighup(signum, frame):
    # Перезагрузка whitelist при получении сигнала SIGHUP
    global WHITELIST_PATH
    if WHITELIST_PATH:
        with config._whitelist_lock:
            config._whitelist.clear()
            config._whitelist.update(load_whitelist(WHITELIST_PATH))
        print("Whitelist reloaded", file=sys.stderr)

def normalize_mac_OUI(mac):
    s = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
    return s[:6] if len(s) >= 6 else None

def normalize_mac(mac):
    s = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
    return s if len(s) >= 6 else None

def lookup_vendor_db(mac, db_path=config.DB_PATH, return_full=True):
    oui = normalize_mac_OUI(mac)
    if not oui:
        return None
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT org FROM oui WHERE oui = ?", (oui,))
        row = cur.fetchone()
        if is_locally_administered(mac):
            description = 'locally administered'
        else:
            description = str(row[0])

        if not return_full:
            return description
        else:
            # mac = mac + ' ('+ description + ')'
            mac = f' {mac}  |   ({description})'

        return mac

def is_locally_administered(mac: str) -> bool:
    """
    Проверяет, установлен ли бит локально администрируемого адреса (LAA) в MAC.
    """
    if not isinstance(mac, str):
        raise TypeError("mac must be a str")
    s = mac.replace(":", "").replace("-", "").replace(".", "").strip().lower()
    if len(s) != 12 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError("invalid MAC address format")
    first_octet = int(s[0:2], 16)
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

def seen_cleaner(ttl):
    if ttl is None:
        return
    while not config._stop.wait(ttl):
        now = time.time()
        removed = 0
        with config._seen_lock:
            keys = list(config._last_seen.keys())
            for k in keys:
                if now - config._last_seen.get(k, 0) > ttl:
                    config._last_seen.pop(k, None)
                    config._seen_count.pop(k, None)
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

def get_wlan_mode(interface='wlan0'):
    try:
        # Выполняем команду iwconfig для получения информации о wlan0
        result = subprocess.run(['iwconfig', interface], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Ошибка при получении информации об интерфейсе {interface}: {result.stderr}")
            return None

        # Выводим результат
        output = result.stdout

        # Ищем строку с режимом работы
        for line in output.split('\n'):
            if 'Mode:' in line:
                mode = line.split('Mode:')[1].split()[0]
                return mode

    except Exception as e:
        print(f"Произошла ошибка: {e}")

    return None




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
    # main.tshark_thread.restart()
    return True
