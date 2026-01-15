import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import re

# Имя базы данных
DATABASE_NAME = 'database.db'
TABLE_NAME = 'whitelist'

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME)
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        """Создаёт таблицу, если её ещё нет"""
        sql_create_table = f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            mac_address TEXT PRIMARY KEY
        );
        '''
        self.conn.execute(sql_create_table)
        self.conn.commit()

    def fetch_all_mac_addresses(self, order_by='ASC'):
        """Возвращает все MAC-адреса из таблицы с указанной сортировкой"""
        cursor = self.conn.cursor()
        cursor.execute(f'SELECT * FROM {TABLE_NAME} ORDER BY mac_address {order_by}')
        return cursor.fetchall()

    def insert_mac_address(self, mac_address):
        """Добавляет новый MAC-адрес в таблицу"""
        cursor = self.conn.cursor()
        cursor.execute(f'INSERT OR IGNORE INTO {TABLE_NAME}(mac_address) VALUES(?)', (mac_address,))
        self.conn.commit()

    def update_mac_address(self, old_mac, new_mac):
        """Обновляет MAC-адрес в таблице"""
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE {TABLE_NAME} SET mac_address=? WHERE mac_address=?', (new_mac, old_mac))
        self.conn.commit()

    def delete_mac_address_by_mask(self, mask):
        """Удаляет MAC-адреса, соответствующие маске"""
        cursor = self.conn.cursor()
        cursor.execute(f'DELETE FROM {TABLE_NAME} WHERE mac_address LIKE ?', ('%' + mask + '%',))
        self.conn.commit()

    def search_mac_addresses(self, search_term):
        """Ищет MAC-адреса по заданному критерию"""
        cursor = self.conn.cursor()
        cursor.execute(f'SELECT * FROM {TABLE_NAME} WHERE mac_address LIKE ?', ('%' + search_term + '%',))
        return cursor.fetchall()

    def load_mac_addresses_from_file(self, filename):
        """Импортирует MAC-адреса из файла"""
        with open(filename, 'r') as file:
            lines = file.readlines()
            for line in lines:
                mac_address = line.strip()
                if mac_address:
                    self.insert_mac_address(mac_address)

class EditorWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Редактор белого списка")
        self.resizable(False, False)  # Заблокируем изменение размеров окна
        self.geometry("800x480+0+0")  # Размер окна 800х480 пикселей, левый верхний угол
        self.attributes("-topmost", True)  # Окно поверх всех остальных окон

        # Инициализируем менеджер базы данных
        self.db_manager = DatabaseManager()

        # Кол-во записей
        self.record_count_label = tk.Label(self, text="Всего записей: ")
        self.record_count_label.grid(row=1, column=0, sticky='sw')

        # Показать все (скрытая кнопка, активируется только при наличии выборки)
        self.show_all_btn = tk.Button(self, text="Показать все", command=self.refresh_tree_view)
        self.show_all_btn.grid(row=1, column=1, sticky='ne')
        self.show_all_btn.grid_remove()  # Прячем кнопку по умолчанию

        # Дерево
        self.tree_view = ttk.Treeview(self, columns=('MAC Address'), show='headings')
        self.tree_view.heading('#1', text='MAC Address', command=self.on_column_click)
        self.tree_view.grid(row=0, column=0, sticky='nsew')

        # Прокрутка
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree_view.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.tree_view.configure(yscrollcommand=vsb.set)

        # Конфигурация grid, чтобы дерево занимало всё пространство окна
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Меню
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        # Файл меню
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Импорт из файла...", command=self.import_from_file)
        menu_bar.add_cascade(label="Файл", menu=file_menu)

        # Редактирование меню
        edit_menu = tk.Menu(menu_bar, tearoff=False)
        edit_menu.add_command(label="Добавить MAC-адрес", command=self.add_new_mac)
        edit_menu.add_command(label="Редактировать выбранный MAC-адрес", command=self.edit_selected_mac)
        edit_menu.add_command(label="Удалить выбранный MAC-адрес", command=self.delete_selected_mac)
        edit_menu.add_separator()
        edit_menu.add_command(label="Искать MAC-адрес", command=self.search_mac)
        menu_bar.add_cascade(label="Редактировать", menu=edit_menu)

        # Горячая клавиша для поиска
        self.bind("<Control-f>", lambda event: self.search_mac())

        # Обновляем TreeView при старте
        self.refresh_tree_view()

    def on_column_click(self):
        """Обработчик события клик на заголовке столбца (для сортировки)"""
        direction = getattr(self, 'direction', 'ASC')
        if direction == 'ASC':
            direction = 'DESC'
        else:
            direction = 'ASC'
        self.direction = direction
        if hasattr(self, 'current_data'):  # Работаем с выборкой
            self.refresh_tree_view_with_results(self.current_data, direction)
        else:
            self.refresh_tree_view(direction)

    def refresh_tree_view(self, order_by='ASC'):
        """Обновляет представление данных в дереве"""
        items = self.tree_view.get_children()
        for item in items:
            self.tree_view.delete(item)

        data = self.db_manager.fetch_all_mac_addresses(order_by)
        for record in data:
            # Формируем MAC-адрес с разделителями двоеточиями
            normalized_mac = ':'.join(record[0][i:i+2] for i in range(0, len(record[0]), 2))
            self.tree_view.insert('', 'end', values=(normalized_mac,))

        # Обновляем счётчик записей
        self.record_count_label['text'] = f"Всего записей: {len(data)}"
        self.show_all_btn.grid_remove()  # Прячем кнопку "Показать все"

    def add_new_mac(self):
        """Диалог для добавления нового MAC-адреса"""
        entry_dialog = AddMacDialog(self)
        entry_dialog.top.transient(self)  # Диалог поверх окна
        entry_dialog.top.lift()  # Убедимся, что окно поднимается поверх всех окон
        entry_dialog.entry.focus_set()  # Ставим фокус на текстовое поле
        entry_dialog.top.bind('<Return>', lambda e: entry_dialog.ok())
        self.wait_window(entry_dialog.top)
        if entry_dialog.result:
            self.db_manager.insert_mac_address(entry_dialog.result)
            self.refresh_tree_view()

    def edit_selected_mac(self):
        """Диалог для редактирования выбранного MAC-адреса"""
        selected_item = self.tree_view.selection()
        if not selected_item:
            messagebox.showwarning("Предупреждение", "Выберите MAC-адрес для редактирования.")
            return
        old_mac = self.tree_view.item(selected_item)['values'][0]
        entry_dialog = EditMacDialog(self, old_mac)
        entry_dialog.top.transient(self)  # Диалог поверх окна
        entry_dialog.top.lift()  # Убедимся, что окно поднимается поверх всех окон
        entry_dialog.entry.focus_set()  # Ставим фокус на текстовое поле
        entry_dialog.top.bind('<Return>', lambda e: entry_dialog.ok())
        self.wait_window(entry_dialog.top)
        if entry_dialog.result:
            new_mac = entry_dialog.result.replace(':', '')
            self.db_manager.update_mac_address(old_mac.replace(':', ''), new_mac)
            self.refresh_tree_view()

    def delete_selected_mac(self):
        """Удаляет выбранный MAC-адрес"""
        selected_items = self.tree_view.selection()
        if not selected_items:
            messagebox.showwarning("Предупреждение", "Выберите MAC-адрес для удаления.")
            return
        answer = messagebox.askokcancel("Подтверждение", "Вы действительно хотите удалить выбранные MAC-адреса?")
        if answer:
            for item in selected_items:
                mac_address = self.tree_view.item(item)['values'][0]
                self.db_manager.delete_mac_address_by_mask(mac_address.replace(':', ''))
            self.refresh_tree_view()

    def search_mac(self):
        """Диалог для поиска MAC-адреса"""
        entry_dialog = SearchMacDialog(self)
        entry_dialog.top.transient(self)  # Диалог поверх окна
        entry_dialog.top.lift()  # Убедимся, что окно поднимается поверх всех окон
        entry_dialog.entry.focus_set()  # Ставим фокус на текстовое поле
        entry_dialog.top.bind('<Return>', lambda e: entry_dialog.ok())
        self.wait_window(entry_dialog.top)
        if entry_dialog.result:
            # Автоудаляем разделители из запроса
            cleaned_query = re.sub(r'[^\da-fA-F]+', '', entry_dialog.result.lower())
            results = self.db_manager.search_mac_addresses(cleaned_query)
            if results:
                self.current_data = results  # запоминаем текущую выборку
                self.refresh_tree_view_with_results(results)
                self.show_all_btn.grid()  # показываем кнопку "Показать все"
                self.record_count_label['text'] = f"Совпадений ({cleaned_query}): {len(results)}"
            else:
                messagebox.showinfo("Результат поиска", "Совпадений не найдено.")

    def refresh_tree_view_with_results(self, results, order_by='ASC'):
        """Обновляет представление данных с результатами поиска"""
        items = self.tree_view.get_children()
        for item in items:
            self.tree_view.delete(item)

        for record in results:
            normalized_mac = ':'.join(record[0][i:i+2] for i in range(0, len(record[0]), 2))
            self.tree_view.insert('', 'end', values=(normalized_mac,))

        # Обновляем счётчик записей
        self.record_count_label['text'] = f"Совпадений: {len(results)}"

    def import_from_file(self):
        """Импортирует MAC-адреса из файла"""
        filename = filedialog.askopenfilename(title="Выберите файл для импорта", filetypes=(("Text Files", "*.txt"), ("All Files", "*.*")))
        if filename:
            self.db_manager.load_mac_addresses_from_file(filename)
            self.refresh_tree_view()

class AddMacDialog:
    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        self.parent = parent
        self.result = None

        label = tk.Label(top, text="Введите новый MAC-адрес:")
        label.pack()
        self.entry = tk.Entry(top)
        self.entry.pack()
        self.button = tk.Button(top, text="OK", command=self.ok)
        self.button.pack()

    def ok(self):
        value = self.entry.get().strip()
        if value:
            self.result = value
        self.top.destroy()

class EditMacDialog(AddMacDialog):
    def __init__(self, parent, initial_value):
        super().__init__(parent)
        self.entry.insert(0, initial_value)

class SearchMacDialog(AddMacDialog):
    pass

if __name__ == '__main__':
    app = EditorWindow()
    app.mainloop()