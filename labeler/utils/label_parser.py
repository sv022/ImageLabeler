import json
import os
from random import choice
from tkinter import IntVar, Label, Radiobutton, Button, Variable, ttk
from .colors import random_colors
from .styles import widget_styles


class LabelParser:
    def __init__(self, root) -> None:
        self.root = root

        self.formats = ["<Метка>_<Номер>", "<Номер>_<Метка>"]

        self.included_subfolders = []
        self.nested_files = {}

        self.labels = {}
        self.label_map = {}
        self.class_mapping = {}

    
    def _init_UI_files(self, folder : str):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
        files = [file for file in os.listdir(folder) if file.lower().endswith(supported_formats)]
        nested_folders = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]
        
        for d in nested_folders:
            self.nested_files[d] = [os.path.relpath(os.path.join(d, f), folder) for f in os.listdir(d) if f.lower().endswith(supported_formats)]

        if files == [] and self.nested_files == {}:
            self.error_label = Label(self.root, foreground="red")
            self.error_label.pack(pady=20, padx=10)
            self.error_label.config(text=f"Выбранная папка не содержит изображений")
            return
        
        self.files = files
        
        self.folder_label = Label(self.root, foreground="green", height=3)
        self.folder_label.pack(pady=20, padx=10)
        self.folder_label.config(text=f"Выбрана папка:\n{folder}\n{len(files) + sum(len(v) for v in self.nested_files.values())} изображений")

        self.select_format_label = Label(self.root, text="Выберите формат названий:")
        self.select_format_label.pack(pady=10, padx=10)

        self.filename_format = IntVar(self.root, value=0)

        for i, name_format in enumerate(self.formats):
            Radiobutton(self.root, text=name_format, variable=self.filename_format, value=i).pack(pady=5, padx=10)

        self.select_subfolders_label = Label(self.root, text="Включать вложенные директории:")
        self.select_subfolders_label.pack(padx=5)

        self.included_subfolders = [Variable(self.root) for _ in range(len(nested_folders))]
        for v in self.included_subfolders:
            v.set(True)
        for idx, d in enumerate(nested_folders):
            ttk.Checkbutton(
                self.root, 
                text=os.path.basename(d), 
                variable=self.included_subfolders[idx]
            ).pack(pady=5, padx=10)


        self.process_button = Button(self.root, text="Обработать", command=self.process_files)
        self.process_button.config(**widget_styles["button_flat_green"])
        self.process_button.pack(pady=10, padx=10, side="bottom")

    
    def process_files(self):
        class_mapping = {}
        files = self.files.copy()
        for idx, d in enumerate(self.nested_files.keys()):
            if int(self.included_subfolders[idx].get()):
                files.extend(self.nested_files[d])
        
        for f in files:
            filename_part = os.path.basename(f).split(".")[0]
            label = filename_part.split("_")[self.filename_format.get()]
            try:
                self.labels[f] = self.label_map[label]
            except KeyError:
                self.label_map[label] = len(self.label_map)
                self.labels[f] = self.label_map[label]

            class_color = choice(list(set(list(random_colors)) - set([x['color'] for x in class_mapping.values()])))

            class_mapping[label] = {
                "index": self.label_map[label],
                "color": class_color
            }

        self.class_mapping = class_mapping

        self.save(self.labels_path, self.config_path)

        self.folder_label.config(text=f"Папка обработана\n{len(self.files) + sum(len(v) for v in self.nested_files.values())} изображений")

    
    def save(self, labels: str, config : str):
        with open(labels, "w", encoding="utf-8") as f:
            json.dump(self.labels, f, ensure_ascii=False, indent=4)
        with open(config, "w", encoding="utf-8") as f:
            json.dump(self.class_mapping, f, ensure_ascii=False, indent=4)
    

    def parse_filenames(self, folder : str, labels : str, config : str):
        self._init_UI_files(folder)
        self.labels_path = labels
        self.config_path = config
