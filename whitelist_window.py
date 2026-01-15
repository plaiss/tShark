import tkinter as tk
from tkinter import filedialog, messagebox
import os


class WhitelistEditor(tk.Toplevel):
    def __init__(self, master=None, file_path="./whitelist.txt"):
        super().__init__(master=master)
        
        # Полностью удаляем рамку окна и разворачиваем его на весь экран
        self.overrideredirect(True)
        self.attributes('-fullscreen', True)  # Полноэкранный режим
        
        # Получаем размер экрана
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Контейнер для основных компонентов
        container = tk.Frame(self)
        container.pack(fill='both', expand=True)
        
        # Полоса прокрутки слева от текстового поля
        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side='right', fill='y')
        
        # Текстовая область с полосой прокрутки
        self.text_widget = tk.Text(container, yscrollcommand=scrollbar.set, wrap='none')
        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.text_widget.yview)
        
        # Панель с кнопками снизу
        button_panel = tk.Frame(self)
        button_panel.pack(side='bottom', anchor='s', fill='x')
        
        # Кнопка "Сохранить"
        save_button = tk.Button(button_panel, text="Сохранить", command=self.save_changes)
        save_button.pack(side='left', padx=10, pady=10)
        
        # Кнопка "Отменить изменения и закрыть"
        discard_button = tk.Button(button_panel, text="Отменить изменения и закрыть", command=self.discard_and_close)
        discard_button.pack(side='left', padx=10, pady=10)
        
        # Кнопка "Закрыть"
        close_button = tk.Button(button_panel, text="Закрыть", command=self.close_without_save)
        close_button.pack(side='right', padx=10, pady=10)
        
        # Читаем файл и вставляем контент
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                content = file.read()
                self.text_widget.insert('1.0', content)
        else:
            self.text_widget.insert('1.0', "Файл пуст.")
        
        # Сохраняем оригинальное содержимое файла для проверки изменений
        self.original_content = self.text_widget.get('1.0', 'end').strip()
    
    def save_changes(self):
        """
        Сохраняет изменения в файл.
        """
        current_text = self.text_widget.get('1.0', 'end').strip()
        with open('./whitelist.txt', 'w') as file:
            file.write(current_text)
        messagebox.showinfo("Готово", "Изменения сохранены.")
        self.destroy()
    
    def discard_and_close(self):
        """
        Закрывает окно, отменяя любые изменения.
        """
        self.destroy()
    
    def close_without_save(self):
        """
        Проверяет, были ли внесены изменения, и предупреждает пользователя.
        """
        current_text = self.text_widget.get('1.0', 'end').strip()
        if current_text != self.original_content:
            result = messagebox.askyesno("Подтверждение", "Вы внесли изменения. Хотите сохранить?")
            if result:
                self.save_changes()
            else:
                self.destroy()
        else:
            self.destroy()

# Тестовый запуск модуля отдельно
if __name__ == "__main__":
    root = tk.Tk()
    editor = WhitelistEditor(root)
    root.withdraw()  # Скрываем корневое окно Tkinter
    root.mainloop()