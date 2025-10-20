import tkinter as tk
from tkinter import ttk


def create_colored_label():
    root = tk.Tk()
    text = tk.Text(root, height=1, width=30)
    text.pack()

    # Вставляем текст
    text.insert(tk.END, "Это обычный текст и это  слово красным.")

    # Вставляем слово с выделением
    start_index = '1.16'  # Начало слова "красным"
    end_index = '1.32'  # Конец слова "красным"

    # Создаем тег для выделения
    text.tag_add("red", start_index, end_index)

    # Настраиваем цвет тега
    text.tag_config("red", foreground="red")

    text.config(state=tk.DISABLED)  # Делаем текст недоступным для редактирования

    root.mainloop()


create_colored_label()
