# config.py
import threading
import re
import sqlite3

# self.entry_mac.insert(0, '48:8B:0A:A1:05:70')  # Пример MAC-адреса

interface = 'wlan1'
mode = ''
password='kali'
# Конфигурация по умолчанию
TSHARK_CMD = [
    "tshark", "-i", interface, "-l", "-T", "fields",
    "-e", "frame.time_epoch",
    "-e", "wlan.ta",
    "-e", "wlan_radio.signal_dbm",
    "-e", "wlan_radio.channel",  # канал
    "-e", "wlan.fc.type_subtype" 
]

WHITELIST_PATH = 'whitelist.txt'
SEEN_TTL_SECONDS = None  # если None — не очищать по времени

# Глобальные структуры и блокировки
_whitelist = set()
_whitelist_lock = threading.Lock()

# Используем словарь mac -> last_seen_timestamp для точной TTL-логики
_last_seen = {}
_seen_count = {}  # количество обнаружений для каждого MAC
_seen_lock = threading.Lock()
_stop = threading.Event()
_traffic_by_mac = {}

MAC_RE = re.compile(r'[^0-9a-f]')
DB_PATH = "database.db"

IEEE_OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"