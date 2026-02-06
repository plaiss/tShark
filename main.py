import time
import signal
import subprocess
import logging 
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from tkinter.messagebox import showinfo
from tkinter import simpledialog
import utils
from config import _stop
import config
from wifi_monitor import WifiMonitor  # Импортируем класс из отдельного файла
from collections import deque, OrderedDict
import queue
import logging.handlers
from whitelist_window import DatabaseManager  # Импортируем менеджер базы данных
import os 

_packets_received = 0
_is_worker_running = False  # Флаг, показывающий, запущен ли уже поток

LOG_FORMAT = '%(asctime)s [%(levelname)-8s]: %(message)s (%(filename)s:%(lineno)d)'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
file_handler = logging.handlers.RotatingFileHandler(
    filename='app.log',  # Основной файл логов
    maxBytes=10 * 1024 * 1024,  # Лимит размера файла (~10 MB)
    backupCount=5,               # Количество резервных копий старых файлов
    encoding='utf-8'
)
# logging.basicConfig(level=logging.INFO, handlers=[file_handler])
logging.basicConfig(level=logging.INFO, handlers=[file_handler], format=LOG_FORMAT, datefmt=DATE_FORMAT)
logger = logging.getLogger(__name__)
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)

# Класс для ограничения размера кэша с использованием LRU-стратегии
class LimitedSizeCache(OrderedDict):
    def __init__(self, max_size=1000):
        """
        Конструктор принимает максимальный размер кэша.
        :param max_size: Максимальное количество элементов в кэше.
        """
        super().__init__()
        self.max_size = max_size

    def add(self, key, value):
        """
        Добавляет элемент в кэш.
        Если достигает предела размера, удаляется самый старый элемент.
        """
        # Добавляем элемент в начало очереди
        self[key] = value
        # Если превысили размеры, удаляем последний элемент
        if len(self) > self.max_size:
            self.popitem(last=False)

    def get(self, key):
        """
        Возвращает значение по ключу и передвигает элемент в начало.
        Если ключа нет, возвращает None.
        """
        if key in self:
            # Получаем элемент и перемещаем его в начало (так как он стал недавно используемым)
            value = self.pop(key)
            self[key] = value
            return value
        else:
            return None
vendor_cache = LimitedSizeCache(max_size=1000) # Новый словарь для кеша, с ограниченной вместимостью


def cached_lookup_vendor_db(mac, db_path, verbose=False):
    # Проверяем, есть ли мак-адрес в кэше
    if mac in vendor_cache:
        return vendor_cache.get(mac)
    # Если нет, ищем в базе данных
    vendor = utils.lookup_vendor_db(mac, db_path, verbose)
    # Сохраняем результат в кэш
    vendor_cache.add(mac, vendor)
    return vendor


PACKET_THRESHOLD = 100000  # порог сброса после достижения 100 тыс. пакетов

def cleanup_resources():
    """
    Функция для очистки ресурсов и сброса счётчиков.
    """
    global _packets_received
    _packets_received = 0
    logger.info("Очистка ресурсов и сброс счётчиков...")
    config._seen_count.clear()
    config._last_seen.clear()
    # дополнительная чистка, если требуется

# def kill_tshark_process(proc):
#     """
#     Завершает активный процесс tshark.
#     """
#     try:
#         proc.terminate()
#         proc.wait(timeout=1) # сокращаем тайм-аут до 1 секунды
#     except subprocess.TimeoutExpired:
#         logger.warning("Timeout истек при попытке завершения tshark. Осуществляется принудительная остановка.")
#         proc.kill() # принудительно останавливаем процесс
#     except Exception as e:
#         logger.error(f"Ошибка при закрытии tshark: {e}")

def kill_tshark_process(proc):
    logger.info(f"[KILL_TSHARK] Попытка завершения процесса PID={proc.pid}")
    
    if proc.poll() is not None:
        logger.info("[KILL_TSHARK] Процесс уже завершён.")
        return

    try:
        proc.terminate()
        logger.debug("[KILL_TSHARK] Отправлен SIGTERM. Ожидание завершения...")
        proc.wait(timeout=5)
        logger.info("[KILL_TSHARK] Процесс успешно завершён.")
    except subprocess.TimeoutExpired:
        logger.warning("[KILL_TSHARK] Таймаут ожидания. Принудительное завершение.")
        try:
            process = psutil.Process(proc.pid)
            process.kill()
            logger.info("[KILL_TSHARK] Процесс убит через psutil.")
        except psutil.NoSuchProcess:
            logger.info("[KILL_TSHARK] Процесс уже завершился.")
        except Exception as e:
            logger.error(f"[KILL_TSHARK] Ошибка при убийстве процесса: {e}")
    except Exception as e:
        logger.error(f"[KILL_TSHARK] Неожиданная ошибка: {e}")

def start_new_tshark_session(cmd):
    """
    Начинает новую сессию tshark.
    """
        # Проверка на висячие процессы
    try:
        result = subprocess.run(['pgrep', 'tshark'], capture_output=True, text=True)
        if result.stdout:
            logger.warning(f"Найден запущенный tshark (PID: {result.stdout.strip()})")
    except Exception as e:
        logger.debug(f"Не удалось проверить процессы tshark: {e}")
                     
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

def restart_tshark_if_needed(proc):
    """
    Функция проверяет условие для перезапуска tshark и инициирует его.
    """
    global _packets_received
    if _packets_received >= PACKET_THRESHOLD:
        logger.info("Перезапуск tshark ввиду достижения лимита пакетов.")
        logger.info(f"Перезапуск tshark (пакетов: {_packets_received}). PID старого процесса: {proc.pid}")
        _packets_received = 0
        kill_tshark_process(proc)
        time.sleep(2)  # Пауза перед новым запуском
        new_proc = start_new_tshark_session(config.TSHARK_CMD)
        logger.info(f"Новый процесс tshark запущен. PID: {new_proc.pid}")
        return new_proc
        # return start_new_tshark_session(config.TSHARK_CMD)
    return proc

def tshark_worker(root, cmd):
    global _packets_received, _is_worker_running
    if _is_worker_running:
        logger.warning("Поток tshark_worker уже запущен. Повторный запуск игнорируется.")
        return
    _is_worker_running = True
    logger.info("Запуск tshark worker.")  # Зарегистрировали старт
    logger.info(f"Процесс tshark успешно стартовал. PID={os.getpid()}, Thread={threading.get_ident()}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.info("Процесс tshark успешно стартовал.")
    except Exception as e:
        root.add_text(f"Ошибка при старте tshark: {e}" + "\n")
        logger.error(f"Не удалось запустить tshark: {e}")
        config._stop.set()
        return

    def stderr_reader():
        for line in proc.stderr:
            root.log_queue.put(line.rstrip())

    threading.Thread(target=stderr_reader, daemon=True).start()

    try:
        while not config._stop.is_set():  # Пока не установлен флаг остановки
            for raw in proc.stdout:
                if config._stop.is_set():  # Дополнительная проверка внутри цикла
                    break
                _packets_received += 1
                config.total_packet_count += 1  # Общий счётчик всех пакетов
                logger.debug(f"Принято {_packets_received} пакетов (всего: {config.total_packet_count}).")

                # Логирование каждые 5000 пакетов
                if (_packets_received % 5000 == 0):
                    logger.info(f"Получено пакетов с текущего перезапуска: {_packets_received}, всего пакетов с начала работы: {config.total_packet_count}.")

                if _packets_received >= PACKET_THRESHOLD:
                    proc = restart_tshark_if_needed(proc)
                    # Очищаем ресурсы и возвращаемся к началу внешнего цикла
                    cleanup_resources()
                    continue
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
                    config._seen_count[mac_n] = config._seen_count.get(mac_n, 0) + 1
                    mac_count = config._seen_count[mac_n]
                    # Обновляем время последнего обнаружения
                    config._last_seen[mac_n] = now

                pretty_time = utils.parse_time_epoch(raw_time)
                mac_vendor = cached_lookup_vendor_db(mac_n, config.DB_PATH, False)
                
                # Складываем данные в буферы класса
                root.tree_buffer.append((mac_n, mac_vendor, rssi, pretty_time, channel, mac_count, config._traffic_by_mac.get(mac_n)))
                root.log_queue.put(f"{mac}|{rssi}| {utils.decode_wlan_type_subtype(subtype)} | {pretty_time} | Канал: {channel}")

    finally:
        # Флаг для отслеживания состояния завершения
        cleanup_completed = False
        
        try:
            # 1. Проверяем, существует ли процесс и ещё работает
            if proc is not None and proc.poll() is None:
                logger.info(f"[FINALLY] Попытка завершения процесса PID={proc.pid}")
                
                # 2. Отправляем SIGTERM (корректное завершение)
                proc.terminate()
                
                # 3. Ждём завершения с таймаутом (5 сек)
                try:
                    proc.wait(timeout=70)
                    logger.info(f"[FINALLY] Процесс PID={proc.pid} успешно завершён.")
                except subprocess.TimeoutExpired:
                    logger.warning(f"[FINALLY] Таймаут ожидания PID={proc.pid}. Принудительное завершение.")
                    # 4. Принудительно убиваем процесс
                    proc.kill()
                    try:
                        proc.wait(timeout=2)  # Ждём подтверждения убийства
                        logger.info(f"[FINALLY] Процесс PID={proc.pid} убит.")
                    except subprocess.TimeoutExpired:
                        logger.error(f"[FINALLY] Не удалось завершить процесс PID={proc.pid}!")
            
            else:
                if proc is None:
                    logger.debug("[FINALLY] proc равен None (процесс не был запущен).")
                else:
                    logger.debug(f"[FINALLY] Процесс PID={proc.pid} уже завершён (код возврата: {proc.poll()}).")
            
            
            # 5. Контролируемая очистка буферов
            root.clean_buffers(controlled=True)
            cleanup_completed = True
            
        except Exception as e:
            logger.error(f"[FINALLY] Ошибка при завершении процесса: {e}", exc_info=True)
        finally:
            # 6. Гарантированная очистка буферов (даже при ошибке)
            try:
                root.clean_buffers()  # Неконтролируемая очистка
            except Exception as e:
                logger.error(f"[FINALLY] Ошибка при очистке буферов: {e}")
            
            # 7. Снимаем флаг активности
            _is_worker_running = False
            logger.info("[FINALLY] Рабочий поток остановлен. Флаг _is_worker_running = False")


def main():
    global DATABASE_NAME
    DATABASE_NAME = config.DB_PATH
    root = WifiMonitor()
    if DATABASE_NAME:
        with config._whitelist_lock:
            config._whitelist.clear()
            db_manager = DatabaseManager()
            config._whitelist.update({rec[0] for rec in db_manager.fetch_all_mac_addresses()})

    if utils.get_wlan_mode(config.interface) == 'Monitor':
        # Запускаем поток и передаем ссылку на него в класс App
        tshark_thread = threading.Thread(target=tshark_worker, args=(root, config.TSHARK_CMD), daemon=True)
        tshark_thread.start()
        logger.info("Создание нового потока tshar из main.py, строка 250 завершено")
        root.tshark_thread = tshark_thread  # сохраняем ссылку на поток в экземпляр App
    root.mainloop()
    

if __name__ == "__main__":
    main()