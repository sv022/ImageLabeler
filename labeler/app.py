import os
import tkinter as tk
from tkinter import ttk, filedialog, Canvas
from PIL import Image, ImageTk
from .utils.colors import colors

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

        # Создание фрейма-контейнера для прокрутки
        self.gallery_container = tk.Frame(self.root, width=self.GALLERY_WIDTH, height=self.GALLERY_HEIGHT)
        self.gallery_container.place(x=10, y=10)
        
        # Создание холста для отображения изображений
        self.canvas = Canvas(self.gallery_container, width=self.GALLERY_WIDTH, height=self.GALLERY_HEIGHT, background=colors['gray'])

        self.scrollbar = ttk.Scrollbar(self.gallery_container, orient="vertical", command=self.canvas.yview)
        
        # Создание внутреннего фрейма, который будет прокручиваться
        self.gallery_frame = tk.Frame(self.canvas, background=colors['gray'])
        
        self.gallery_frame.bind(
            "<Configure>", 
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.gallery_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)   


        self.info_frame = tk.Frame(self.root, height=self.INFO_HEIGHT, width=self.INFO_WIDTH, background=colors['gray'])
        self.info_frame.place(x=1020, y=10)

        self.select_folder_button = tk.Button(self.gallery_container, text="Select Folder", width=10, command=self.select_folder)
        self.select_folder_button.place(x=self.GALLERY_WIDTH // 2, y=self.GALLERY_HEIGHT // 2 - 50)
        

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")  


    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.folder = folder_path
        self.select_folder_button.place_forget()
        self.load_images(folder_path)

    
    def load_images(self, folder_path):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
        self.image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(supported_formats)]
        self.image_labels = []

        IMG_height = 85
        IMG_width = 85
        pad_x = 5
        pad_y = 5
        img_per_row = 10

        for idx, image in enumerate(self.image_files):
            image = Image.open(image)
            image = image.resize((IMG_width, IMG_height))
            photo = ImageTk.PhotoImage(image)
            
            self.image_labels.append(tk.Label(self.gallery_frame, image=photo))

            # place_x_coord = ((idx % img_per_row) * IMG_height + pad_x * (idx % img_per_row + 1))
            # place_y_coord = (idx // img_per_row * IMG_width) + pad_y * (idx // img_per_row + 1)
            # self.image_labels[idx].place(x=place_x_coord, y=place_y_coord, width=IMG_height, height=IMG_width)

            label = tk.Label(self.gallery_frame, image=photo)
            label.image = photo
            label.grid(row=idx // img_per_row, column=idx % img_per_row, padx=pad_x, pady=pad_y)
        
        self.gallery_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))