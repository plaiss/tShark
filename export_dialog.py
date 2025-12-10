# export_dialog.py
import tkinter as tk
from tkinter import filedialog
import csv

class ExportDialog:
    def __init__(self, parent, treeview):
        """
        Экспорт данных из Treeview в CSV без создания дополнительного окна.
        :param parent: Родительский виджет (главное окно).
        :param treeview: Объект Treeview, содержащий данные.
        """
        self.parent = parent
        self.treeview = treeview
        self.export_to_csv()

    def export_to_csv(self):
        """
        Непосредственно экспортирует данные в CSV-файл.
        """
        # Выбор файла для сохранения
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV файлы", "*.csv")])
        if not file_path:
            return  # Выход, если файл не выбран

        # Этап экспорта данных
        with open(file_path, "w", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            headers = ["MAC адрес", "Производитель", "Сила сигнала (dBm)", "Время последнего обнаружения", "Канал"]
            writer.writerow(headers)

            # Сбор данных из Treeview
            for item in self.treeview.get_children():
                row_values = self.treeview.item(item)["values"]
                writer.writerow(row_values)

        # Информирование пользователя об успешном сохранении
        tk.messagebox.showinfo("Успех", f"Данные успешно экспортированы в {file_path}.")