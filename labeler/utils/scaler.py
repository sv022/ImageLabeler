import os
from tkinter import Label, Button, filedialog, Frame, Entry
import cv2
import json
from numpy import around
from datetime import datetime


class Scaler:
    def __init__(self, outDir = 'out/', name = ""):
        self.resolution = (64, 64)
        self.outDir = os.path.join(outDir, 'output')
        self.outputPath = ""
        self.outputName = name
        self.labelMap = {}
        self.labels = []

        if not os.path.exists(self.outDir):
            os.makedirs(self.outDir)

    
    def set_label_map(self, labelMap):
        self.labelMap = labelMap
        self.labels = list(set([lable for lable in self.labelMap.values()]))

    
    def set_resolution(self, resolution):
        self.resolution = resolution

    
    def process_image_txt(self, image_path : str):
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise FileNotFoundError(f"Unable to load image: {image_path}.")

        resized_image = cv2.resize(image, self.resolution)
        normalized_image = around(resized_image / 255.0, decimals=3)
        image_name = "".join(os.path.splitext(os.path.basename(image_path)))

        try:
            labelName = self.labelMap[image_name]
        except KeyError as e:
            # print(f"Warning: File {e} not labeled.")
            return

        with open(self.outputPath, "a") as output_file:
            flattened_values = normalized_image.flatten()
            output_file.write(" ".join(map(str, flattened_values)) + '\n')
            output_file.write(" ".join(["1" if str(l) == str(labelName) else "0" for l in self.labels]) + '\n')

        # print(f"Значения для {image_name} записаны в {self.outDir}")

    def process_image_csv(self, image_path: str):
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise FileNotFoundError(f"Unable to load image: {image_path}.")

        resized_image = cv2.resize(image, self.resolution)
        normalized_image = around(resized_image / 255.0, decimals=3)
        image_name = "".join(os.path.splitext(os.path.basename(image_path)))

        try:
            labelName = self.labelMap[image_name]
        except KeyError as e:
            # print(f"Warning: File {e} not labeled.")
            return

        flattened_values = normalized_image.flatten()
        csv_line = f"{labelName}," + ",".join(map(str, flattened_values))
        
        with open(self.outputPath, "a") as output_file:
            output_file.write(csv_line + '\n')

        # print(f"Значения для {image_name} записаны в {self.outDir}")


    def process_folder_txt(self, input_folder : str):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

        if os.listdir(input_folder) == []:
            return
        
        now = datetime.today().strftime('%Y_%m_%d_%H%M%S')
        txt_path = os.path.join(self.outDir, f"{self.outputName}_{now}.txt")
        self.outputPath = txt_path
        if not os.path.isfile(txt_path):
            with open(txt_path, "w") as output_file:
                output_file.write("")

        for file_name in os.listdir(input_folder):
            if file_name.lower().endswith(supported_formats):
                image_path = os.path.join(input_folder, file_name)
                self.process_image_txt(image_path)

    def process_folder_csv(self, input_folder: str):
        supported_formats = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

        if not os.path.exists(input_folder) or not os.listdir(input_folder):
            return
        
        now = datetime.today().strftime('%Y_%m_%d_%H%M%S')
        csv_path = os.path.join(self.outDir, f"{self.outputName}_{now}.csv")
        self.outputPath = csv_path
        if not os.path.isfile(csv_path):
            with open(csv_path, "w") as output_file:
                width, height = self.resolution
                header = "label," + ",".join(f"{i}" for i in range(1, width * height + 1))
                output_file.write(header + '\n')

        for file_name in os.listdir(input_folder):
            if file_name.lower().endswith(supported_formats):
                image_path = os.path.join(input_folder, file_name)
                try:
                    self.process_image_csv(image_path)
                except Exception as e:
                    # print(f"Error processing {file_name}: {str(e)}")
                    pass


class ImageScaler:
    def __init__(self, root, exportFormat : str, folderPath = "", labelsPath = "", name = ""):
        self.root = root
        self.name = name
        self.folder_label = Label(root)
        self.folder_label.pack(pady=10)
        self.error_label = Label(root, foreground="red")
        self.error_label.pack(pady=5)

        self.sc = Scaler(outDir=folderPath, name=name)

        self.folder = folderPath
        self.labels = labelsPath

        if exportFormat not in {"txt", "csv"}:
            self.export_format = "txt"
        else:
            self.export_format = exportFormat

        self.initUI()


    def initUI(self):
        try:
            with open(self.labels, 'r', encoding='utf-8') as file:
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
        self.process_button.pack(pady=5)


    def process_folder(self):
        if self.width_entry.get() == "" or self.height_entry.get() == "":
            self.error_label.config(text="Укажите разрешение.")
            self.error_label.config(foreground="red")
            return
        
        self.sc.set_resolution((int(self.width_entry.get()), int(self.height_entry.get())))

        try:
            folder = os.path.join(self.folder, "images")
            if self.export_format == "txt":
                self.sc.process_folder_txt(folder)
            elif self.export_format == "csv":
                self.sc.process_folder_csv(folder)
            else:
                return
        except Exception as e:
            self.error_label.config(text=f"Произошла ошибка: {str(e)}")
            self.error_label.config(foreground="red")
            return

        self.error_label.config(text=f"Папка успешно обработана.\nРезультаты сохранены в /{self.name}.{self.export_format}")
        self.error_label.config(foreground="green")
