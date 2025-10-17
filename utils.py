# utils.py
import re
import sqlite3
import time

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

def lookup_vendor_db(mac, db_path):
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
    Декодирует типы и подтипы фреймов Wi-Fi.
    """
    try:
        n = int(val, 0)
    except Exception:
        return str(val)

    subtype = n & 0xF
    type_ = (n >> 4) & 0x3
    to_ds = (n >> 8) & 0x1
    from_ds = (n >> 9) & 0x1
    protected = (n >> 14) & 0x1
    order = (n >> 15) & 0x1

    mgmt_subtypes = {...}
    ctrl_subtypes = {...}
    data_subtypes = {...}

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