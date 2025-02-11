import os
import tkinter as tk
from tkinter import ttk, filedialog, Canvas, Menu
from PIL import Image, ImageTk
from .utils.colors import colors
import json

class ImageLabelerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeler")
        self.root.geometry('1440x900+300+200')
        self.root.resizable(False, False)

        self.GALLERY_HEIGHT = 880
        self.GALLERY_WIDTH = 1000
        self.INFO_HEIGHT = 880
        self.INFO_WIDTH = 410

        self.folder = ""
        self.selected_index = None
        self.image_files = []
        self.labeled_files = {}

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
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.info_frame = tk.Frame(self.root, height=self.INFO_HEIGHT, width=self.INFO_WIDTH, background=colors['gray'])
        self.info_frame.place(x=1020, y=10)

        self.info_label = tk.Label(self.info_frame, text="Выберите папку", font=("Arial", 12), background=colors['gray'])
        self.info_label.place(x=self.INFO_WIDTH // 2 - 70, y=self.INFO_HEIGHT // 2)

        self.select_folder_button = tk.Button(self.gallery_container, text="Выберите папку", width=10, command=self.select_folder)
        self.select_folder_button.place(x=self.GALLERY_WIDTH // 2, y=self.GALLERY_HEIGHT // 2 - 50)

        self.initToolbar()


    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    
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

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.folder = folder_path
        self.select_folder_button.place_forget()
        self.config_path = os.path.join(self.folder, "config.json")

        self.selected_index = None
        self.image_files = []
        
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.classes = list(json.load(f).keys())
                self.class_to_index = {str(name): i for i, name in enumerate(self.classes)}
                self.index_to_class = {i: str(name) for i, name in enumerate(self.classes)}
        else:
            self.classes = []
    
        self.info_label.config(text="Выберите изображение")
        self.load_images(folder_path)
        self.load_existing_labels()

    def create_class_config(self):
        self.class_window = tk.Toplevel(self.root)
        self.class_window.title("Настройка классов")
        self.class_window.geometry("400x300+300+200")
        
        self.class_entries = []
        self.class_frame = tk.Frame(self.class_window)
        self.class_frame.pack(pady=10)
        
        self.add_class_field()
        
        add_button = tk.Button(self.class_window, text="+", command=self.add_class_field)
        add_button.pack(pady=5)
        
        save_button = tk.Button(self.class_window, text="Сохранить", command=lambda: self.save_classes())
        save_button.pack(pady=10)

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
        self.classes = []
        self.index_to_class = {}
        self.class_to_index = {}

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.index_to_class, f, ensure_ascii=False, indent=4)


    def load_existing_labels(self):
        labels_path = os.path.join(self.folder, "labels.json")
        if not os.path.exists(labels_path): return
        try:
            with open(labels_path, "r", encoding="utf-8") as file:
                self.labeled_files = json.load(file)
        except Exception as e:
            print(f"Ошибка загрузки labels.json: {e}")

    def select_image(self, index):
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
            tk.Label(self.info_frame, text="Не настроены классы для разметки", font=("Arial", 12), background=colors['gray']).place(x=10, y=IMG_size + 20)
            try:
                self.classes_select.place_forget()
            except Exception:
                pass
            return
        
        tk.Label(self.info_frame, text="Выберите класс", font=("Arial", 12), background=colors['gray']).place(x=10, y=IMG_size + 20)
        self.classes_select = ttk.Combobox(self.info_frame, values=self.classes, state="readonly")
        self.classes_select.place(x=10, y=IMG_size + 60, width=self.INFO_WIDTH - 20)
        self.classes_select.bind("<<ComboboxSelected>>", self.save_label)
            

        image_name = os.path.basename(image_path)
        if image_name in self.labeled_files:
            class_number = self.labeled_files[image_name]
            self.classes_select.set(self.index_to_class.get(class_number, ""))

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