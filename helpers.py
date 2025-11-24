# helpers.py
import subprocess
import threading
import re
import socket
import platform
import os
import sys
import time


def available_interfaces():
    if platform.system() == "Linux":
        cmd = "ip link show"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        lines = output.split("\n")
        interfaces = []
        for line in lines:
            match = re.match(r"\d+: ([^\s]+):.*", line)
            if match:
                iface = match.group(1)
                if iface.startswith("wl"):
                    interfaces.append(iface)
        return interfaces
    elif platform.system() == "Windows":
        # Windows-поддержка пока упрощённая
        return ["wlan0", "wlan1"]
    else:
        raise NotImplementedError("Unsupported OS")


def capture_wifi_devices(app_instance):
    while app_instance.is_running:
        # Здесь выполняйте запросы к устройству и собирайте данные
        # Например, с помощью tshark или другого инструмента
        mock_data = [
            ("AA:BB:CC:DD:EE:FF", "Apple Inc.", "-65", "Just Now", "6"),
            ("11:22:33:44:55:66", "Samsung Electronics Co.,Ltd", "-70", "1 minute ago", "11"),
        ]
        app_instance.update_device_list(mock_data)
        time.sleep(5)