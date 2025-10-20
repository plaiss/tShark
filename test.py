import tkinter as tk


def open_second_window():
    # Получаем текст из первого окна
    text_value = entry.get()

    # Создаем второе окно
    second_window = tk.Toplevel(root)
    second_window.title("Второе окно")

    # Отображаем переданное значение во втором окне
    label = tk.Label(second_window, text=text_value)
    label.pack(pady=20)


# Основное окно
root = tk.Tk()
root.title("Первое окно")

# Поле ввода для передачи значения
entry = tk.Entry(root)
entry.pack(pady=20)

# Кнопка для открытия второго окна
button = tk.Button(root, text="Открыть второе окно", command=open_second_window)
button.pack(pady=20)

# Запуск основного цикла приложения
root.mainloop()
