# export_dialog.py
import tkinter as tk
from tkinter import filedialog
import csv


class ExportDialog:
    def __init__(self, master, treeview):
        """
        Диалоговое окно для экспорта данных из таблицы Treeview в CSV.
        :param master: родительский виджет (окно верхнего уровня)
        :param treeview: объект Treeview, содержащий данные
        """
        self.master = master
        self.treeview = treeview
        self.dialog = tk.Toplevel(master)
        self.dialog.title("Export to CSV")
        self.dialog.transient(master)
        self.dialog.grab_set()

        # Label и кнопка для подтверждения экспорта
        lbl = tk.Label(self.dialog, text="Choose a location to save the CSV file:", font=("Arial", 12))
        lbl.pack(pady=10)

        btn_save = tk.Button(self.dialog, text="Save As...", command=self.save_to_csv)
        btn_save.pack(pady=10)

        # Показываем диалог поверх основного окна
        self.center_window()

    def center_window(self):
        """
        Центрирование окна на экране.
        """
        self.dialog.update_idletasks()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        dialog_width = self.dialog.winfo_reqwidth()
        dialog_height = self.dialog.winfo_reqheight()
        x_pos = (screen_width // 2) - (dialog_width // 2)
        y_pos = (screen_height // 2) - (dialog_height // 2)
        self.dialog.geometry("+{}+{}".format(x_pos, y_pos))

    def save_to_csv(self):
        """
        Сохраняет данные из Treeview в выбранный CSV-файл.
        """
        # Открываем диалог для выбора местоположения файла
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return

        # Экспорт данных
        with open(file_path, "w", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Сначала записываем заголовки
            headers = ["MAC Address", "Vendor", "Signal Strength (dBm)", "Last Seen", "Channel"]
            writer.writerow(headers)

            # А затем сами данные
            for item in self.treeview.get_children():
                values = self.treeview.item(item)["values"]
                writer.writerow(values)

        # Сообщаем пользователю об успешном экспорте
        tk.messagebox.showinfo("Success", f"Data exported successfully to {file_path}.")

        # Закрываем диалоговое окно
        self.dialog.destroy()