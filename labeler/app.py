import os
import sys
import json
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, Canvas, Menu, messagebox
from PIL import Image, ImageTk
from random import choice
from string import hexdigits

from .utils.scaler import ImageScaler
from .utils.cropper import ImageCropper
from .utils.colors import colors, random_colors
from .utils.data_analysis import plot_from_labels, plot_from_file, plot_from_csv
from .utils.mnist_loader import load_mnist
from .utils.styles import widget_styles


class ImageLabelerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeler")
        self.root.geometry('1440x900+300+200')
        self.root.resizable(False, False)
        self.__appid = 'svapp.imagelabeler.v1' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.__appid)
        self.root.iconbitmap(r"labeler/icon.ico")
        
        self.GALLERY_HEIGHT = 860
        self.GALLERY_WIDTH = 1000
        self.INFO_HEIGHT = 860
        self.INFO_WIDTH = 410

        self.folder = ""
        self.project = None
        self.selected_index = None
        self.image_files = []
        self.labeled_files = {}
        self.classes = []
        self.class_to_index = {}
        self.index_to_class = {}
        self.class_color_map = {}
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
        self.info_label.configure(widget_styles['label_bold'])
        self.info_label.place(x=self.INFO_WIDTH // 2 - 70, y=self.INFO_HEIGHT // 2)

        self.welcome_label = tk.Label(self.gallery_container, text="Добро пожаловать!")
        self.welcome_label.configure(widget_styles['startscreen_label'])
        self.welcome_label.place(x=self.GALLERY_WIDTH // 2 - 85, y=100)

        self.select_folder_button = tk.Button(self.gallery_container, text="Выберите папку", command=self.select_folder)
        self.select_folder_button.configure(widget_styles['startscreen_button'])
        self.select_folder_button.place(x=self.GALLERY_WIDTH // 2 - 80, y=self.GALLERY_HEIGHT // 2 - 100)

        self.open_project_button = tk.Button(self.gallery_container, text="Открыть проект", command=self.open_project)
        self.open_project_button.configure(widget_styles['startscreen_button'])
        self.open_project_button.place(x=self.GALLERY_WIDTH // 2 - 80, y=self.GALLERY_HEIGHT // 2 - 50)

        self.create_project_button = tk.Button(self.gallery_container, text="Создать проект", command=self.create_project)
        self.create_project_button.configure(widget_styles['startscreen_button'])
        self.create_project_button.place(x=self.GALLERY_WIDTH // 2 - 80, y=self.GALLERY_HEIGHT // 2)

        self.initToolbar()


    def __on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    
    def __restart_programm(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    
    def __clear_info_frame(self, clear_gallery=True):
        try:
            self.crop_save_copy_check.place_forget()
            self.crop_image_button.place_forget()
            self.classes_select_label.place_forget()
            self.classes_select.place_forget()
            self.image_info_label.place_forget()
            self.image_name_label.place_forget()
            self.image_extension_label.place_forget()
            self.image_size_label.place_forget()
        except Exception:
            pass
        else:
            try:
                self.info_label.place_forget()
                self.info_label = tk.Label(self.info_frame, text="Выберите изображение")
                self.info_label.configure(widget_styles['label_bold'])
                self.info_label.place(x=self.INFO_WIDTH // 2 - 50, y=self.INFO_HEIGHT // 2)
            except:
                pass
        try:
            self.classes_select.place_forget()
        except Exception:
            pass
        if clear_gallery:
            try:
                for widget in self.gallery_frame.winfo_children():
                    widget.destroy()
            except Exception:
                pass

    
    def __reload_app_state(self, place_forget=False, dump_project_data=False):
        if place_forget:
            self.welcome_label.place_forget()
            self.select_folder_button.place_forget()
            self.create_project_button.place_forget()
            self.open_project_button.place_forget()

        if dump_project_data and self.project:
            if not os.path.exists(self.project["config"]):
                with open(self.project["config"], "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)
            if not os.path.exists(self.project["labels"]):
                with open(self.project["labels"], "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)

        self.selected_index = None
        self.image_files = []
        self.__clear_info_frame()

        self.load_class_config()
        self.labeled_files = {}
        self.info_label.place_forget()
        self.info_label.place(x=self.INFO_WIDTH // 2 - 90, y=self.INFO_HEIGHT // 2)
        self.info_label.config(text="Выберите изображение")
        self.load_existing_labels()
        self.load_images(self.folder)


    def __get_image_bg_color(self, image_name : str):
        image_bg_color = "#FFFFFF"
        try:
            image_bg_color = self.class_color_map[self.index_to_class[int(self.labeled_files[image_name])]]
        except KeyError:
            pass
        return image_bg_color


    def initToolbar(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        fileMenu = Menu(menubar)
        fileMenu.add_command(label="Открыть папку", underline=0, command=self.select_folder)
        menubar.add_cascade(label="Файл", underline=0, menu=fileMenu)

        projectMenu = Menu(menubar)
        projectMenu.add_command(label="Открыть проект", underline=0, command=self.open_project)
        projectMenu.add_command(label="Настройки проекта", underline=0, command=self.configure_project)
        menubar.add_cascade(label="Проект", underline=0, menu=projectMenu)

        classMenu = Menu(menubar)
        classMenu.add_command(label="Изменить классы", underline=0, command=self.create_class_config)
        classMenu.add_command(label="Очистить классы", underline=0, command=self.clear_classes)
        menubar.add_cascade(label="Настройка классов", underline=0, menu=classMenu)

        exportMenu = Menu(menubar)
        exportMenu.add_command(label="Экспорт папки в txt", underline=0, command=self.export_to_txt)
        exportMenu.add_command(label="Экспорт папки в csv", underline=0, command=self.export_to_csv)
        menubar.add_cascade(label="Экспорт", underline=0, menu=exportMenu)

        premadeDatasetMenu = Menu(menubar)
        premadeDatasetMenu.add_command(label="MNIST Digits", underline=0, command=self.parse_mnist_digits)
        premadeDatasetMenu.add_command(label="MNIST Fashion", underline=0, command=self.parse_mnist_fashion)
        menubar.add_cascade(label="Готовые датасеты", underline=0, menu=premadeDatasetMenu)

        anasysisMenu = Menu(menubar)
        anasysisMenu.add_command(label="Текущая директория", underline=0, command=self.plot_current_labels)
        anasysisMenu.add_command(label="Выбрать файл txt", underline=0, command=self.plot_selected_txt)
        anasysisMenu.add_command(label="Выбрать файл csv", underline=0, command=self.plot_selected_csv)
        menubar.add_cascade(label="Анализ", underline=0, menu=anasysisMenu)


    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.folder = folder_path
        self.config_path = os.path.join(self.folder, "config.json")

        self.project = None
        
        self.__reload_app_state(place_forget=True)


    def open_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("Labeler Projects", "*.labelproj.json")])
        if not file_path:
            return
        try:
            with open(file_path) as f:
                project_data = json.load(f)
                self.project = project_data
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при открытии проекта: {e}")
            return
        
        self.folder = self.project["images"]
        self.config_path = self.project["config"]

        self.__reload_app_state(place_forget=True)
        

    def create_project(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        
        project_data = {
            "name": os.path.basename(folder_path).replace(" ", "_"),
            "root": folder_path,
            "labels": os.path.join(folder_path, "labels.json"),
            "config": os.path.join(folder_path, "config.json"),
            "images": os.path.join(folder_path, "images")
        }
        
        if not os.path.exists(project_data["images"]):
            os.mkdir(project_data["images"])

        self.project = project_data
        self._update_project_data()

        self.folder = self.project["images"]
        self.config_path = self.project["config"]

        self.__reload_app_state(place_forget=True, dump_project_data=True)

    
    def configure_project(self):
        if not self.project:
            return

        config_window = tk.Toplevel(self.root)
        config_window.title(f"Настройка проекта: {self.project['name']}")
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        config_window.geometry(f"600x400+{x+200}+{y+250}")

        form_frame = ttk.Frame(config_window, padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}


        def add_field_with_browse(row, label_text, field_name, is_folder=True):
            ttk.Label(form_frame, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=5)
            
            entry = ttk.Entry(form_frame, width=50)
            entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
            entry.insert(0, self.project.get(field_name, ""))
            entries[field_name] = entry
            if field_name == "name":
                entry.config(state="readonly")
            
            def browse():
                if is_folder:
                    path = filedialog.askdirectory()
                else:
                    path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
                if path:
                    entry.delete(0, tk.END)
                    entry.insert(0, path)
                
                config_window.focus_set()
            
            browse_btn = ttk.Button(form_frame, text="Обзор...", command=browse)
            browse_btn.grid(row=row, column=2, padx=5)

        add_field_with_browse(0, "Название проекта:", "name", is_folder=False)
        add_field_with_browse(1, "Корневая папка:", "root", is_folder=True)
        add_field_with_browse(2, "Файл меток:", "labels", is_folder=False)
        add_field_with_browse(3, "Конфигурация классов:", "config", is_folder=False)
        add_field_with_browse(4, "Папка изображений:", "images", is_folder=True)


        def save_config():
            try:
                for field_name, entry in entries.items():
                    self.project[field_name] = entry.get()

                self._update_project_data()

                config_window.destroy()
                
                self.folder = self.project["images"]
                self.config_path = self.project["config"]


                self.__reload_app_state(place_forget=True, dump_project_data=True)
                    
            except Exception as e:
                tk.messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{str(e)}")

        button_frame = ttk.Frame(config_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        save_btn = ttk.Button(button_frame, text="Сохранить", command=save_config)
        save_btn.pack(side=tk.RIGHT, padx=5)

        cancel_btn = ttk.Button(button_frame, text="Отмена", command=config_window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        form_frame.columnconfigure(1, weight=1)

        config_window.protocol("WM_DELETE_WINDOW", config_window.destroy)


    def _update_project_data(self):
        if not self.project:
            return

        try:
            with open(os.path.join(self.project["root"], f"{self.project['name']}.labelproj.json"), 'w', encoding='utf-8') as f:
                json.dump(self.project, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Ошибка!", repr(e))


    def load_class_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.classes = list(config.keys())
                self.class_to_index = {str(name): i for i, name in enumerate(self.classes)}
                self.index_to_class = {i: str(name) for i, name in enumerate(self.classes)}
                self.class_color_map = {name : config[name]['color'] for name in config}
        else:
            self.classes = []

        
    def create_class_config(self):
        if not self.folder:
            tk.messagebox.showerror("Ошибка", "Папка не выбрана")
            return
        self.class_window = tk.Toplevel(self.root)
        self.class_window.title("Настройка классов")
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.class_window.geometry(f"400x500+{x+300}+{y+200}")

        
        self.class_entries = []
        self.class_frame = tk.Frame(self.class_window)
        self.class_frame.pack(pady=10)

        for class_name in self.classes:
            entry = tk.Entry(self.class_frame)
            entry.insert(0, class_name)
            entry.configure({"background" : self.class_color_map[class_name]})
            entry.pack(pady=2)
            self.class_entries.append(entry)
        
        self.add_class_field()
        
        add_button = tk.Button(self.class_window, text="+", command=self.add_class_field)
        add_button.pack(pady=5)

        hint_text = tk.Label(self.class_window, text="Чтобы удалить класс, оставьте поле пустым", font=("Arial", 8), foreground="gray")
        hint_text.pack(pady=10)
        save_button = tk.Button(self.class_window, text="Сохранить", command=lambda: self.save_classes())
        save_button.pack(pady=5)
        hint_text2 = tk.Label(self.class_window, text="Для применения изменений программа перезапустится", font=("Arial", 8), foreground="#FAA0A0")
        hint_text2.pack(pady=5)


    def add_class_field(self):
        entry = tk.Entry(self.class_frame)
        entry.pack(pady=2)
        self.class_entries.append(entry)


    def save_classes(self):
        class_mapping = {}
        for i, entry in enumerate(self.class_entries):
            class_name = entry.get().strip()
            if not class_name:
                continue
            
            class_color = self.class_color_map.get(class_name, None)
            if class_color is not None:
                self.class_color_map[class_name] = class_color
            elif len(self.class_color_map) < 30:
                class_color = choice(list(set(list(random_colors)) - set([x['color'] for x in class_mapping.values()])))
            else:
                class_color = f'#{"".join(choice(hexdigits).lower() for _ in range(6))}'

            class_mapping[class_name] = {
                "index": i,
                "color": class_color
            }
        
        if class_mapping:
            self.classes = list(class_mapping.keys())
            self.class_to_index = {str(name): i for i, name in enumerate(self.classes)}
            self.index_to_class = {i: str(name) for i, name in enumerate(self.classes)}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(class_mapping, f, ensure_ascii=False, indent=4)
            self.class_window.destroy()
            # self.setup_ui()
            self.load_images(self.folder)
        
        self.__restart_programm()


    def clear_classes(self):
        if not self.folder:
            tk.messagebox.showerror("Ошибка", "Папка не выбрана")
            return
        if not tk.messagebox.askokcancel("Подтверждение", "Вы уверены, что хотите удалить все классы?"):
            return
        self.classes = []
        self.index_to_class = {}
        self.class_to_index = {}
        self.class_color_map = {}

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.index_to_class, f, ensure_ascii=False, indent=4)

        self.__restart_programm()
        

    def load_existing_labels(self):
        if not self.project: 
            labels_path = os.path.join(self.folder, "labels.json")
        else:
            labels_path = self.project["labels"]
        if not os.path.exists(labels_path): return
        try:
            with open(labels_path, "r", encoding="utf-8") as file:
                self.labeled_files = json.load(file)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки labels.json: {e}")
            # print(f"Ошибка загрузки labels.json: {e}")


    def select_image(self, index):
        try:
            self.classes_not_set_label.place_forget()
        except Exception:
            pass

        self.__clear_info_frame(clear_gallery=False)
        
        image_path = self.image_files[index]
        self.selected_index = index

        IMG_size = self.INFO_WIDTH - 20

        image = Image.open(image_path)

        image_name, image_extension = os.path.basename(self.image_files[self.selected_index]).split('.')
        im_width, im_height = image.size

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
        
        self.crop_image_button = tk.Button(self.info_frame, text="Обрезать Изображение", command=self.crop_image)
        self.crop_image_button.configure(widget_styles['button_flat'])
        self.crop_image_button.place(x=10, y=IMG_size + 20)
        self.crop_save_copy_check = tk.Checkbutton(self.info_frame, text="Сохранить копию", font=("Arial", 12), variable=self.save_copy_check, onvalue=True, offvalue=False, background=colors['gray'])
        self.crop_save_copy_check.place(x=10, y=IMG_size + 60)
        
        self.classes_select_label = tk.Label(self.info_frame, text="Выберите класс")
        self.classes_select_label.configure(widget_styles['label_bold'])
        self.classes_select_label.place(x=10, y=IMG_size + 100)
        self.classes_select = ttk.Combobox(self.info_frame, values=self.classes, state="readonly")
        self.classes_select.place(x=10, y=IMG_size + 130, width=self.INFO_WIDTH - 20)
        self.classes_select.bind("<<ComboboxSelected>>", self.save_label)

        self.image_info_label = tk.Label(self.info_frame, text="Информация об изображении")
        self.image_info_label.configure(widget_styles['label_bold'])
        self.image_info_label.place(x=10, y=IMG_size + 170)

        self.image_name_label = tk.Label(self.info_frame, text=f"Название файла: {image_name}", font=("Arial", 10), background=colors['gray'])
        self.image_extension_label = tk.Label(self.info_frame, text=f"Расширение: {image_extension}", font=("Arial", 10), background=colors['gray'])
        self.image_size_label = tk.Label(self.info_frame, text=f"Размер изображения: {im_width}x{im_height}", font=("Arial", 10), background=colors['gray'])

        self.image_name_label.place(x=10, y=IMG_size + 210)
        self.image_extension_label.place(x=10, y=IMG_size + 240)
        self.image_size_label.place(x=10, y=IMG_size + 270)

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

        for idx, image_name in enumerate(self.image_files):
            image = Image.open(image_name)
            image = image.resize((IMG_size, IMG_size))
            photo = ImageTk.PhotoImage(image)

            label = tk.Label(self.gallery_frame, image=photo)
            label.image = photo
            base_image_name = os.path.basename(image_name)
            image_bg_color = self.__get_image_bg_color(base_image_name)
            label.configure({"background" : image_bg_color})
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
        image_bg_color = self.__get_image_bg_color(image_name)
        list(self.gallery_frame.children.values())[self.selected_index].configure({"background" : image_bg_color})
        self.save_labels()


    def save_labels(self):
        if not self.folder:
            return
        if not self.project: 
            labels_path = os.path.join(self.folder, "labels.json")
        else:
            labels_path = self.project["labels"]
        try:
            with open(labels_path, "w", encoding="utf-8") as file:
                json.dump(self.labeled_files, file, ensure_ascii=False, indent=4)
            # print(f"Labels saved successfully to {labels_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при записи в файл: {e}")
            # print(f"Ошибка при записи в файл: {e}")


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
            messagebox.showwarning("Предупреждение", "Папка не выбрана")
            return
        
        scaler_window = tk.Toplevel(self.root)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        scaler_window.geometry(f"300x200+{x+200}+{y+200}")
        scaler_window.resizable(False, False)
        scaler = ImageScaler(scaler_window, "txt", self.folder)
        scaler_window.protocol("WM_DELETE_WINDOW", scaler_window.destroy)


    def export_to_csv(self):
        if not self.folder:
            messagebox.showwarning("Предупреждение", "Папка не выбрана")
            return
        
        scaler_window = tk.Toplevel(self.root)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        scaler_window.geometry(f"300x200+{x+200}+{y+200}")
        scaler_window.resizable(False, False)
        scaler = ImageScaler(scaler_window, "csv", self.folder)
        scaler_window.protocol("WM_DELETE_WINDOW", scaler_window.destroy)

    
    def plot_current_labels(self):
        if not self.project and not self.folder:
            messagebox.showwarning("Предупреждение", "Папка не выбрана")
            return
        if self.project:
            plot_from_labels(self.project["labels"])
            return
        plot_from_labels(os.path.join(self.folder, "labels.json"))


    def plot_selected_txt(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not file_path:
            return

        plot_from_file(file_path)


    def plot_selected_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        plot_from_csv(file_path)

    
    def parse_mnist(self, kind : str):
        if not self.folder:
            messagebox.showwarning("Предупреждение", "Папка не выбрана")
            return
        digits_loader_window = tk.Toplevel(self.root)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        digits_loader_window.geometry(f"400x250+{x+250}+{y+200}")
        digits_loader_window.resizable(False, False)
        digits_loader_window.title(f"Загрузка MNIST {kind}")

        tk.Label(digits_loader_window, text="").pack(pady=10, padx=20)

        entry_frame = tk.Frame(digits_loader_window)
        entry_frame.pack()

        train_data_size_label = tk.Label(entry_frame, text="Размер тренировочной выборки:")
        train_data_size_entry = tk.Entry(entry_frame)
        train_data_size_entry.insert(0, "60000")
        train_data_size_label.grid(row=1, column=0, pady=10, padx=20, sticky="e")
        train_data_size_entry.grid(row=1, column=1, pady=10, padx=5, sticky="w")

        test_data_size_label = tk.Label(entry_frame, text="Размер тестовой выборки:")
        test_data_size_entry = tk.Entry(entry_frame)
        test_data_size_entry.insert(0, "10000")
        test_data_size_label.grid(row=2, column=0, pady=10, padx=20, sticky="e")
        test_data_size_entry.grid(row=2, column=1, pady=10, padx=5, sticky="w")

        status_label = tk.Label(digits_loader_window, text="")
        status_label.pack(pady=10, padx=20)


        def _load_digits():
            train_data_size = int(train_data_size_entry.get())
            test_data_size = int(test_data_size_entry.get())
            output_folder = os.path.join(self.folder, "mnist")
            try:
                if not os.path.exists(output_folder):
                    os.mkdir(output_folder)
                load_mnist(output_folder, kind, train_data_size, test_data_size)
            except Exception as e:
                status_label.config(text="Ошибка при загрузке")
                status_label.config(fg="red")
                # print(e)
                return


        def load_digits():
            status_label.config(text="Загрузка...")
            status_label.config(fg="grey")
            digits_loader_window.update_idletasks()

            _load_digits()

            status_label.config(text="Загрузка завершена")
            status_label.config(fg="green")
            
        
        load_digits_btn = tk.Button(digits_loader_window, text="Загрузить", width=20, command=load_digits)
        load_digits_btn.pack(pady=20, padx=20)
        
        digits_loader_window.protocol("WM_DELETE_WINDOW", digits_loader_window.destroy)


    def parse_mnist_digits(self):
        self.parse_mnist("digits")


    def parse_mnist_fashion(self):
        self.parse_mnist("fashion")
