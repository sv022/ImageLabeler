import tkinter as tk
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

        self.gallery_frame = tk.Frame(self.root, height=self.GALLERY_HEIGHT, width=self.GALLERY_WIDTH, background=colors['gray'])
        self.gallery_frame.place(x=10, y=10)

        self.info_frame = tk.Frame(self.root, height=self.INFO_HEIGHT, width=self.INFO_WIDTH, background=colors['gray'])
        self.info_frame.place(x=1020, y=10)

        self.select_folder_button = tk.Button(self.gallery_frame, text="Select Folder", width=10, command=self.select_folder)
        self.select_folder_button.place(x=self.GALLERY_WIDTH // 2, y=self.GALLERY_HEIGHT // 2 - 50)


    def select_folder(self):
        folder_path = tk.filedialog.askdirectory()
        if folder_path:
            self.folder = folder_path
            