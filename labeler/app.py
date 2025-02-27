import os
import sys
import json
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, Canvas, Menu
from PIL import Image, ImageTk

from .utils.scaler import ImageScaler
from .utils.cropper import ImageCropper
from .utils.colors import colors
from .utils.data_analysis import plot_from_labels, plot_from_file

class ImageLabelerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeler")
        self.root.geometry('1440x900+300+200')
        self.root.resizable(False, False)
        self.__appid = 'svapp.imagelabeler.v1' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.__appid)
        self.root.iconbitmap(r"labeler/icon.ico")
        
        self.GALLERY_HEIGHT = 880
        self.GALLERY_WIDTH = 1000
        self.INFO_HEIGHT = 880
        self.INFO_WIDTH = 410

        self.folder = ""
        self.selected_index = None
        self.image_files = []
        self.labeled_files = {}
        self.save_copy_check = tk.BooleanVar(value=True)

        # UI Layout
        self.gallery_container = tk.Frame(self.root, width=self.GALLERY_WIDTH, height=self.GALLERY_HEIGHT)
        self.gallery_container.place(x=10, y=10)

        self.canvas = Canvas(self.gallery_container, width=self.GALLERY_WIDTH, height=self.GALLERY_HEIGHT, background=colors['gray'])
        self.scrollbar = ttk.Scrollbar(self.gallery_container, orient="vertical", command=self.canvas.yview)

        self.gallery_frame = tk.Frame(self.canvas, background=colors['gray'])
        self.gallery_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.gallery_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self.__on_mousewheel)

        self.info_frame = tk.Frame(self.root, height=self.INFO_HEIGHT, width=self.INFO_WIDTH, background=colors['gray'])
        self.info_frame.place(x=1020, y=10)

        self.info_label = tk.Label(self.info_frame, text="Выберите папку", font=("Arial", 12), background=colors['gray'])
        self.info_label.place(x=self.INFO_WIDTH // 2 - 70, y=self.INFO_HEIGHT // 2)

        self.select_folder_button = tk.Button(self.gallery_container, text="Выберите папку", width=15, command=self.select_folder)
        self.select_folder_button.place(x=self.GALLERY_WIDTH // 2, y=self.GALLERY_HEIGHT // 2 - 50)

        self.initToolbar()


    def __on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    
    def __restart_programm(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    
    def __clear_info_frame(self):
        try:
            self.classes_select.place_forget()
        except Exception:
            pass
        try:
            for widget in self.gallery_frame.winfo_children():
                widget.destroy()
        except Exception:
            pass


    def initToolbar(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        fileMenu = Menu(menubar)
        fileMenu.add_command(label="Открыть папку", underline=0, command=self.select_folder)
        menubar.add_cascade(label="Файл", underline=0, menu=fileMenu)

        classMenu = Menu(menubar)
        classMenu.add_command(label="Изменить классы", underline=0, command=self.create_class_config)
        classMenu.add_command(label="Очистить классы", underline=0, command=self.clear_classes)
        menubar.add_cascade(label="Настройка классов", underline=0, menu=classMenu)

        exportMenu = Menu(menubar)
        exportMenu.add_command(label="Экспорт папки в txt", underline=0, command=self.export_to_txt)
        menubar.add_cascade(label="Экспорт", underline=0, menu=exportMenu)

        anasysisMenu = Menu(menubar)
        anasysisMenu.add_command(label="Текущая директория", underline=0, command=self.plot_current_labels)
        anasysisMenu.add_command(label="Выбрать файл", underline=0, command=self.plot_selected_file)
        menubar.add_cascade(label="Анализ", underline=0, menu=anasysisMenu)

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.folder = folder_path
        self.select_folder_button.place_forget()
        self.config_path = os.path.join(self.folder, "config.json")

        self.selected_index = None
        self.image_files = []
        self.__clear_info_frame()

        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.classes = list(json.load(f).keys())
                self.class_to_index = {str(name): i for i, name in enumerate(self.classes)}
                self.index_to_class = {i: str(name) for i, name in enumerate(self.classes)}
        else:
            self.classes = []

        self.labeled_files = {}
        self.info_label.config(text="Выберите изображение")
        self.load_images(folder_path)
        self.load_existing_labels()

        
    def create_class_config(self):
        if not self.folder:
            tk.messagebox.showerror("Ошибка", "Папка не выбрана")
            return
        self.class_window = tk.Toplevel(self.root)
        self.class_window.title("Настройка классов")
        self.class_window.geometry("400x500+300+200")

        
        self.class_entries = []
        self.class_frame = tk.Frame(self.class_window)
        self.class_frame.pack(pady=10)

        for class_name in self.classes:
            entry = tk.Entry(self.class_frame)
            entry.insert(0, class_name)
            entry.pack(pady=2)
            self.class_entries.append(entry)
        
        self.add_class_field()
        
        add_button = tk.Button(self.class_window, text="+", command=self.add_class_field)
        add_button.pack(pady=5)

        hint_text = tk.Label(self.class_window, text="Чтобы удалить класс, оставьте поле пустым", font=("Arial", 8), foreground="gray")
        hint_text.pack(pady=10)
        
        save_button = tk.Button(self.class_window, text="Сохранить", command=lambda: self.save_classes())
        save_button.pack(pady=5)

    def add_class_field(self):
        entry = tk.Entry(self.class_frame)
        entry.pack(pady=2)
        self.class_entries.append(entry)

    def save_classes(self):
        class_mapping = {}
        for i, entry in enumerate(self.class_entries):
            class_name = entry.get().strip()
            if class_name:
                class_mapping[class_name] = str(i)
        
        if class_mapping:
            self.classes = list(class_mapping.keys())
            self.class_to_index = {str(name): i for i, name in enumerate(self.classes)}
            self.index_to_class = {i: str(name) for i, name in enumerate(self.classes)}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(class_mapping, f, ensure_ascii=False, indent=4)
            self.class_window.destroy()
            # self.setup_ui()
            self.load_images(self.folder)


    def clear_classes(self):
        if not self.folder:
            tk.messagebox.showerror("Ошибка", "Папка не выбрана")
            return
        self.classes = []
        self.index_to_class = {}
        self.class_to_index = {}

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.index_to_class, f, ensure_ascii=False, indent=4)

        self.__restart_programm()
        

    def load_existing_labels(self):
        labels_path = os.path.join(self.folder, "labels.json")
        if not os.path.exists(labels_path): return
        try:
            with open(labels_path, "r", encoding="utf-8") as file:
                self.labeled_files = json.load(file)
        except Exception as e:
            print(f"Ошибка загрузки labels.json: {e}")

    def select_image(self, index):
        # clearing UI elements
        try:
            self.classes_not_set_label.place_forget()
        except Exception:
            pass
        try:
            self.crop_save_copy_check.place_forget()
            self.crop_image_button.place_forget()
            self.classes_select_label.place_forget()
            self.classes_select.place_forget()
        except Exception:
            pass

        image_path = self.image_files[index]
        self.selected_index = index

        IMG_size = self.INFO_WIDTH - 20

        image = Image.open(image_path)
        image = image.resize((IMG_size, IMG_size))
        photo = ImageTk.PhotoImage(image)

        self.info_label.place_forget()
        self.info_label = tk.Label(self.info_frame, image=photo, background=colors['gray'])
        self.info_label.place(x=10, y=10)
        self.info_label.config(image=photo)
        self.info_label.image = photo

        if not self.classes:
            self.classes_not_set_label = tk.Label(self.info_frame, text="Не настроены классы для разметки", font=("Arial", 12), background=colors['gray'])
            self.classes_not_set_label.place(x=10, y=IMG_size + 20)
            try:
                self.classes_select.place_forget()
            except Exception:
                pass
            return
        
        self.crop_image_button = tk.Button(self.info_frame, text="Обрезать Изображение", font=("Arial", 12), command=self.crop_image, background=colors['gray'])
        self.crop_image_button.place(x=10, y=IMG_size + 20)
        self.crop_save_copy_check = tk.Checkbutton(self.info_frame, text="Сохранить копию", font=("Arial", 12), variable=self.save_copy_check, onvalue=True, offvalue=False, background=colors['gray'])
        self.crop_save_copy_check.place(x=10, y=IMG_size + 60)
        
        self.classes_select_label = tk.Label(self.info_frame, text="Выберите класс", font=("Arial", 12), background=colors['gray'])
        self.classes_select_label.place(x=10, y=IMG_size + 100)
        self.classes_select = ttk.Combobox(self.info_frame, values=self.classes, state="readonly")
        self.classes_select.place(x=10, y=IMG_size + 130, width=self.INFO_WIDTH - 20)
        self.classes_select.bind("<<ComboboxSelected>>", self.save_label)
            

        image_name = os.path.basename(image_path)
        if image_name in self.labeled_files:
            class_number = self.labeled_files[image_name]
            self.classes_select.set(self.index_to_class.get(int(class_number), ""))

    def load_images(self, folder_path):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(supported_formats)]

        IMG_size = 85
        pad_x = 5
        pad_y = 5
        img_per_row = 10

        for idx, image in enumerate(self.image_files):
            image = Image.open(image)
            image = image.resize((IMG_size, IMG_size))
            photo = ImageTk.PhotoImage(image)

            label = tk.Label(self.gallery_frame, image=photo)
            label.image = photo
            label.bind("<Button-1>", lambda event, idx=idx: self.select_image(idx))
            label.grid(row=idx // img_per_row, column=idx % img_per_row, padx=pad_x, pady=pad_y)

        self.gallery_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def save_label(self, event):
        if self.selected_index is None:
            return
        class_name = self.classes_select.get()
        class_number = self.class_to_index.get(class_name)
        if class_number is None:
            return
        image_name = os.path.basename(self.image_files[self.selected_index])
        self.labeled_files[image_name] = str(class_number)
        self.save_labels()

    def save_labels(self):
        if not self.folder:
            return
        labels_path = os.path.join(self.folder, "labels.json")
        try:
            with open(labels_path, "w", encoding="utf-8") as file:
                json.dump(self.labeled_files, file, ensure_ascii=False, indent=4)
            print(f"Labels saved successfully to {labels_path}")
        except Exception as e:
            print(f"Ошибка при записи в файл: {e}")


    def crop_image(self):
        if self.selected_index is None:
            return
        
        cropper_window = tk.Toplevel(self.root)
        
        image_path = self.image_files[self.selected_index]
        cropper = ImageCropper(cropper_window)
        cropper.set_file(image_path)
        cropper.set_save_copy(self.save_copy_check.get())
        def on_cropper_close():
            self.load_images(self.folder)
            cropper_window.destroy()

        cropper_window.protocol("WM_DELETE_WINDOW", on_cropper_close)

        if not cropper.run():
            tk.messagebox.showerror("Ошибка", "Размер изображения слишком мал")

    def export_to_txt(self):
        if not self.folder:
            return
        
        scaler_window = tk.Toplevel(self.root)
        scaler_window.geometry("300x200")
        scaler_window.resizable(False, False)
        scaler = ImageScaler(scaler_window, self.folder)
        scaler_window.protocol("WM_DELETE_WINDOW", scaler_window.destroy)

    
    def plot_current_labels(self):
        plot_from_labels(self.folder)


    def plot_selected_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not file_path:
            return

        plot_from_file(file_path)