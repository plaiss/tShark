import tkinter as tk

def toggle_button():
    if button['relief'] == 'sunken':
        button.config(relief='raised', text="raised")
    else:
        button.config(relief='sunken', text="sunken")

root = tk.Tk()
button = tk.Button(root, text="Старт позишня", command=toggle_button)
button.pack(pady=20)

root.mainloop()