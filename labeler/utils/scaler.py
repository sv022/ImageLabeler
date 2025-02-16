import os
from tkinter import Label, Button, filedialog, Frame, Entry
import cv2
import json
from numpy import around


class Scaler:
    def __init__(self, outDir = 'out/'):
        self.resolution = (64, 64)
        self.outDir = outDir
        self.labelMap = {}
        self.labels = []

        if not os.path.exists(outDir):
            os.makedirs(outDir)

    
    def set_label_map(self, labelMap):
        self.labelMap = labelMap
        self.labels = list(set([lable for lable in self.labelMap.values()]))

    
    def set_resolution(self, resolution):
        self.resolution = resolution

    
    def process_image(self, image_path : str):
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise FileNotFoundError(f"Unable to load image: {image_path}.")

        resized_image = cv2.resize(image, self.resolution)
        normalized_image = around(resized_image / 255.0, decimals=3)
        image_name = "".join(os.path.splitext(os.path.basename(image_path)))

        try:
            labelName = self.labelMap[image_name]
        except KeyError as e:
            print(f"Warning: File {e} not labeled.")
            return

        with open(f"{self.outDir}output.txt", "a") as output_file:
            flattened_values = normalized_image.flatten()
            output_file.write(" ".join(map(str, flattened_values)) + '\n')
            output_file.write(" ".join(["1" if str(l) == str(labelName) else "0" for l in self.labels]) + '\n')

        # print(f"Значения для {image_name} записаны в {self.outDir}")


    def process_folder(self, input_folder : str):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

        if os.listdir(input_folder) == []:
            return
        
        if not os.path.isfile(os.path.join(self.outDir, "output.txt")):
            with open(f"{self.outDir}output.txt", "w") as output_file:
                output_file.write("")

        for file_name in os.listdir(input_folder):
            if file_name.lower().endswith(supported_formats):
                image_path = os.path.join(input_folder, file_name)
                self.process_image(image_path)


class ImageScaler:
    def __init__(self, root, folderPath = ""):
        self.root = root
        self.folder_label = Label(root)
        self.folder_label.pack(pady=10)
        self.error_label = Label(root, foreground="red")
        self.error_label.pack(pady=10)

        self.sc = Scaler()

        self.folder = folderPath

        if folderPath == "":
            select_folder_button = Button(root, text="Select Folder", command=self.select_folder)
            select_folder_button.pack(pady=10)
        else:
            self.initUI()


    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        if not os.path.isdir(folder_path):
            self.error_label.config(text="Selected path is not a folder.")
            return
        if not os.path.isfile(os.path.join(folder_path, "labels.json")):
            self.error_label.config(text="Selected folder does not contain labels.json.")
            return
        self.folder_label.config(text=folder_path)
        self.folder = folder_path

        self.initUI()

    def initUI(self):
        try:
            with open(f"{self.folder}/labels.json", 'r', encoding='utf-8') as file:
                self.sc.set_label_map(json.load(file))
        except Exception as e:
            self.error_label.config(text=f"Выбранная папка не содержит файл labels.json")
            self.error_label.config(foreground="red")
            return
        
        self.error_label.config(text=f"Выбрана папка:\n{self.folder}")
        self.error_label.config(foreground="green")

        self.dimensions_frame = Frame(self.root)
        self.dimensions_frame.pack(pady=10)

        self.width_label = Label(self.dimensions_frame, text="Разрешение:")
        self.width_label.grid(row=0, column=0)

        self.width_entry = Entry(self.dimensions_frame, width=10)
        self.width_entry.insert(0, "64")
        self.width_entry.grid(row=1, column=0)

        self.height_label = Label(self.dimensions_frame, text="x")
        self.height_label.grid(row=1, column=1)

        self.height_entry = Entry(self.dimensions_frame, width=10)
        self.height_entry.insert(0, "64")
        self.height_entry.grid(row=1, column=2)

        self.dimensions_frame.pack(pady=10)

        self.process_button = Button(self.root, text="Экспорт", command=self.process_folder)
        self.process_button.pack(pady=10)



    def process_folder(self):
        if self.width_entry.get() == "" or self.height_entry.get() == "":
            self.error_label.config(text="Укажите разрешение.")
            self.error_label.config(foreground="red")
            return
        
        self.sc.set_resolution((int(self.width_entry.get()), int(self.height_entry.get())))
        self.sc.process_folder(self.folder)

        self.error_label.config(text="Папка успешно обработана.\nРезультаты сохранены в out/output.txt")
        self.error_label.config(foreground="green")
