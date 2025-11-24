# app.py
from ui import MainWindow
from settings_window import SettingsWindow
from export_dialog import ExportDialog

if __name__ == "__main__":
    window = MainWindow(SettingsWindow, ExportDialog)
    window.mainloop()