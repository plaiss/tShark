
#!/usr/bin/env python3
# oui_to_sqlite.py
# Требования: Python 3.7+, модуль requests (pip install requests)

import re
import sqlite3
import requests
import sys
from pathlib import Path
import config


# def download_oui_txt(url=config.IEEE_OUI_URL, timeout=30):
#     """Скачать текстовый файл OUI с сайта IEEE"""
#     r = requests.get(url, timeout=timeout)
#     r.raise_for_status()
#     return r.text

def download_oui_txt(url=config.IEEE_OUI_URL, timeout=30):
    """Скачать текстовый файл OUI с сайта IEEE с реалистичными заголовками"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_oui_text(text):
    """
    Парсит текст oui.txt и возвращает генератор (OUI, organization) где OUI = 'AABBCC'
    Обрабатывает строки формата '00-00-00   (hex)        XEROX CORPORATION'
    """
    pattern = re.compile(r'^([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})\s+\(hex\)\s+(.+)$')
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            oui = (m.group(1) + m.group(2) + m.group(3)).upper()
            org = m.group(4).strip()
            yield oui, org

def init_db(db_path=config.DB_PATH):
    """Создать или открыть базу и таблицу"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS oui (
        oui TEXT PRIMARY KEY,
        org TEXT NOT NULL
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_oui ON oui(oui)")
    conn.commit()
    return conn

def populate_db(conn, entries):
    """Вставляет или обновляет записи OUI → org"""
    cur = conn.cursor()
    cur.executemany("INSERT OR REPLACE INTO oui(oui, org) VALUES(?, ?)", entries)
    conn.commit()

def build_db(url=config.IEEE_OUI_URL, db_path=config.DB_PATH):
    """Скачать, распарсить и сохранить в sqlite"""
    print("Скачиваем", url)
    txt = download_oui_txt(url)
    print("Парсим")
    entries = list(parse_oui_text(txt))
    print(f"Найдено записей: {len(entries)}")
    conn = init_db(db_path)
    populate_db(conn, entries)
    conn.close()
    print("База обновлена:", db_path)

# # Утилита поиска
# def normalize_mac(mac):
#     """Оставляет только hex и возвращает верхний регистр"""
#     if not mac:
#         return None
#     s = re.sub(r'[^0-9A-Fa-f]', '', mac)
#     s = s.upper()
#     return s if len(s) >= 6 else None

# def lookup_vendor(mac, conn=None, db_path=DB_PATH):
#     """
#     Возвращает производителя по MAC или None.
#     Принимает любую форму MAC: aa:bb:cc:dd:ee:ff, aabb.ccdd.eeff, AA-BB-CC-...
#     """
#     s = normalize_mac(mac)
#     if not s:
#         return None
#     oui = s[:6]
#     close_conn = False
#     if conn is None:
#         conn = sqlite3.connect(str(db_path))
#         close_conn = True
#     cur = conn.cursor()
#     cur.execute("SELECT org FROM oui WHERE oui = ?", (oui,))
#     row = cur.fetchone()
#     if close_conn:
#         conn.close()
#     return row[0] if row else None


if __name__ == "__main__":
    # main(sys.argv)
    # main('lookup b2:0d:87:9d:5d:73' )
    build_db()
