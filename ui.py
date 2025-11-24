# ui.py
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from helpers import capture_wifi_devices


class MainWindow(tk.Tk):
    def __init__(self, settings_class, export_class):
        super().__init__()
        self.settings_class = settings_class
        self.export_class = export_class
        self.title("Wi-Fi Devices Monitor")
        self.wm_geometry("800x600")

        # Frame для верхней панели инструментов
        top_frame = tk.Frame(self)
        top_frame.pack(fill="x", side="top")

        # Чекбокс "Enable Monitor Mode"
        self.chk_enable_monitor_mode = tk.IntVar()
        chkbox_monitor_mode = tk.Checkbutton(top_frame, text="Enable Monitor Mode", variable=self.chk_enable_monitor_mode)
        chkbox_monitor_mode.pack(side="left", padx=10, pady=10)

        # Button "Настроить интерфейс"
        btn_settings = tk.Button(top_frame, text="Настроить интерфейс", command=self.open_settings)
        btn_settings.pack(side="left", padx=10, pady=10)

        # Комбо-бокс выбора канала
        channels = ["Авто"] + list(map(str, range(1, 15))) + ["36", "40", "44", "48", "52", "56", "60", "64", "100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "149", "153", "157", "161", "165"]
        self.current_channel = tk.StringVar(value="Авто")
        combobox_channels = ttk.Combobox(top_frame, textvariable=self.current_channel, values=channels)
        combobox_channels.pack(side="right", padx=10, pady=10)

        # Table Treeview
        self.treeview = ttk.Treeview(self, columns=("MAC", "Vendor", "RSSI", "Last Seen", "Channel"), show="headings")
        self.treeview.heading("MAC", text="MAC Address")
        self.treeview.heading("Vendor", text="Vendor")
        self.treeview.heading("RSSI", text="Signal Strength (dBm)")
        self.treeview.heading("Last Seen", text="Last Seen")
        self.treeview.heading("Channel", text="Channel")
        self.treeview.pack(fill="both", expand=True)

        # Кнопка экспорта в CSV
        btn_export_csv = tk.Button(self, text="Экспорт в CSV", command=lambda: self.export_class(self.treeview))
        btn_export_csv.pack(side="bottom", pady=10)

    def open_settings(self):
        settings_win = self.settings_class(self)
        settings_win.grab_set()

    def update_device_list(self, devices):
        for device in devices:
            mac, vendor, rssi, last_seen, channel = device
            found = False
            for child in self.treeview.get_children():
                if self.treeview.item(child)['values'][0] == mac:
                    found = True
                    self.treeview.item(child, values=(mac, vendor, rssi, last_seen, channel))
                    break
            if not found:
                self.treeview.insert("", "end", values=(mac, vendor, rssi, last_seen, channel))