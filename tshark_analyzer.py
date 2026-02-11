import asyncio
import subprocess
import time
from typing import Optional

# mac_address = "e0:cc:f8:bb:75:45"
mac_address = "7A:6C:06:3C:F7:DF"
device_role = None  # "AP", "STA" или None

def determine_role(fc_type: str, fc_subtype: str, sa: str, da: str, bssid: str, target_mac: str) -> Optional[str]:
    if fc_type == "0":  # Management
        if fc_subtype == "8" and bssid.lower() == target_mac.lower():
            return "AP"
        elif (sa.lower() == target_mac.lower() or da.lower() == target_mac.lower()) and fc_subtype in ("4", "5", "0", "1"):
            return "STA"
    elif fc_type == "2":  # Data
        if sa.lower() == target_mac.lower():
            return "STA"
        elif da.lower() == target_mac.lower() and bssid.lower() != target_mac.lower():
            return "STA"
    return None

async def safe_print(*args):
    await asyncio.to_thread(print, *args)

async def run_tshark_discovery(interface: str):
    """Этап 1: Определение роли (широкий фильтр)."""
    packet_queue = asyncio.Queue(maxsize=100)
    cmd = [
        'tshark', '-l', '-i', interface,
        '-T', 'fields', '-E', 'separator=\t',
        '-e', 'wlan.fc.type', '-e', 'wlan.fc.subtype',
        '-e', 'wlan.sa', '-e', 'wlan.da', '-e', 'wlan.bssid',
        '-e', 'frame.number', '-e', 'wlan_radio.signal_dbm',
        '-Y', f'(wlan.sa == {mac_address} or wlan.da == {mac_address} or wlan.bssid == {mac_address}) and (wlan.fc.type == 0 or wlan.fc.type == 2)'
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await safe_print(f"[*] Discovery mode on {interface}...")

        while True:
            line = await process.stdout.readline()
            if not line: break
            line_str = line.decode('utf-8', errors='ignore').strip()
            if not line_str: continue
            parts = line_str.split('\t', 6)
            if len(parts) != 7: continue

            fc_type, fc_subtype, sa, da, bssid, _, signal = parts
            role = determine_role(fc_type, fc_subtype, sa, da, bssid, mac_address)
            if role:
                global device_role
                device_role = role
                await safe_print(f"[ROLE] Device identified as: {device_role}")
                process.terminate()
                return  # Выход после определения роли
    except Exception as e:
        await safe_print(f"[!] Discovery error: {e}")


async def run_tshark_monitor(interface: str):
    """Этап 2: Мониторинг dBm (узкий фильтр под роль)."""
    # Формируем фильтр в зависимости от роли
    if device_role == "AP":
        # Для AP: только кадры, где BSSID == наш MAC (мы — точка доступа)
        # filter_expr = f'wlan.bssid == {mac_address} and wlan.fc.type == 2'
        filter_expr = f'wlan.bssid == {mac_address} or wlan.ra == {mac_address}) and (wlan.fc.type == 2 or (wlan.fc.type == 1 and wlan.fc.subtype == 13)'
    elif device_role == "STA":
        # Для STA: только кадры, где DA == наш MAC (нам отправляют данные)
        # filter_expr = f'wlan.da == {mac_address} and wlan.fc.type == 2'
        filter_expr = f'wlan.ta == {mac_address}'
    else:
        await safe_print("[!] Role not determined. Exiting.")
        return

    cmd = [
        'tshark', '-l', '-i', interface,
        '-T', 'fields', '-E', 'separator= ',
        '-e', 'frame.number', '-e', 'wlan_radio.signal_dbm',
        '-Y', filter_expr
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await safe_print(f"[*] Monitoring mode ({device_role}) on {interface}. dBm only.")
        await safe_print(cmd)
        await safe_print("-" * 50)

        packet_count = 0
        start_time = time.time()

        while True:
            line = await process.stdout.readline()
            if not line: break
            line_str = line.decode('utf-8', errors='ignore').strip()
            if not line_str: continue

            parts = line_str.split()
            if len(parts) == 2:
                pack_num, signal = parts
                packet_count += 1

                # Выводим только dBm
                await safe_print(f"Packet {pack_num}: {signal} dBm")


    except Exception as e:
        await safe_print(f"[!] Monitoring error: {e}")

async def main():
    interface = 'wlan1'
    await run_tshark_discovery(interface)  # Этап 1: определить роль
    if device_role:
        await run_tshark_monitor(interface)  # Этап 2: мониторить dBm
    else:
        await safe_print("[!] Failed to determine role. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
