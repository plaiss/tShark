import tkinter as tk
from tkinter import filedialog, messagebox

class ExportDialog:
    def __init__(self, parent, treeview):
        self.parent = parent
        self.treeview = treeview
        self.export_to_txt()

    def export_to_txt(self):
        if not self.treeview.get_children():
            messagebox.showwarning("Пустые данные", "В таблице нет данных для экспорта.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
            title="Сохранить TXT-файл"
        )
        if not file_path:
            messagebox.showwarning("Отмена", "Экспорт отменён.")
            return

        # Порядок колонок фиксирован: #1=MAC, #2=Производитель
        mac_col = "#1"
        vendor_col = "#2"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for item in self.treeview.get_children():
                    # Получаем значения по идентификаторам колонок
                    mac = self.treeview.set(item, mac_col)
                    vendor = self.treeview.set(item, vendor_col)
                    f.write(f"{mac} {vendor}\n")
            messagebox.showinfo("Успех", f"Данные успешно экспортированы в {file_path}.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")
