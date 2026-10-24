import os
import cv2
import json
import struct
from tkinter import Label, Button, Frame, Entry
from numpy import ascontiguousarray, around
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime


SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".bmp")


def _natural_key(s):
    return (0, int(s), s) if s.lstrip("-").isdigit() else (1, 0, s)


BIN_MAGIC = b"IMGS"
BIN_VERSION = 2 # CHW RGB


def _resize_like_loader(image, width, height):
    sh, sw = image.shape[:2]
    if sw != width:
        image = cv2.resize(image, (width, sh), interpolation=cv2.INTER_AREA if sw > width else cv2.INTER_LINEAR)
    if sh != height:
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA if sh > height else cv2.INTER_LINEAR)
    return image


def load_chw_uint8(image_path, width, height, channels):
    flag = cv2.IMREAD_GRAYSCALE if channels == 1 else cv2.IMREAD_COLOR
    image = cv2.imread(image_path, flag)
    if image is None:
        raise FileNotFoundError(f"Unable to load image: {image_path}.")
    if channels == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = _resize_like_loader(image, width, height)
    if image.ndim == 2:
        image = image[:, :, None]
    return ascontiguousarray(image.transpose(2, 0, 1))

class Scaler:
    def __init__(self, outDir = 'out/', name = ""):
        self.resolution = (64, 64, 1)
        self.outDir = os.path.join(outDir, 'output')
        self.outputPath = ""
        self.outputName = name
        self.labelMap = {}
        self.labels = []
        os.makedirs(self.outDir, exist_ok=True)

        if not os.path.exists(self.outDir):
            os.makedirs(self.outDir)

    
    def set_label_map(self, labelMap):
        self.labelMap = labelMap
        self.labels = sorted({str(v) for v in labelMap.values()}, key=_natural_key)

    
    def set_resolution(self, resolution):
        width, height, channels = resolution
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive.")
        if channels not in (1, 3):
            raise ValueError("Expected channels to be 1 or 3.")
        self.resolution = (width, height, channels)

    def _load_raw(self, image_path):
        width, height, channels = self.resolution
        return load_chw_uint8(image_path, width, height, channels)

    def _load_flat(self, image_path):
        return around(self._load_raw(image_path) / 255.0, decimals=3).flatten()

    def _write_bin_header(self, f):
        w, h, c = self.resolution
        f.write(BIN_MAGIC)
        f.write(struct.pack("<BHHB", BIN_VERSION, w, h, c))
        f.write(struct.pack("<H", len(self.labels)))
        for label in self.labels:
            data = label.encode("utf-8")
            f.write(struct.pack("<H", len(data)))
            f.write(data)
        count_pos = f.tell()
        f.write(struct.pack("<I", 0))
        return count_pos

    def _find_label(self, image_path):
        name = os.path.basename(image_path)
        parent = os.path.basename(os.path.dirname(image_path))
        for key in (f"{parent}/{name}", os.path.join(parent, name), name):
            if key in self.labelMap:
                return self.labelMap[key]
        return None

    def _new_path(self, ext):
        now = datetime.today().strftime('%Y_%m_%d_%H%M%S')
        return os.path.join(self.outDir, f"{self.outputName}_{now}.{ext}")

    @staticmethod
    def _images_in(folder):
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(SUPPORTED_FORMATS):
                yield os.path.join(folder, f)
    
    def process_image_txt(self, image_path, output_file):
        label = self._find_label(image_path)
        if label is None:
            print(f"Warning: {image_path} not labeled.")
            return False
        values = self._load_flat(image_path)
        output_file.write(" ".join(map(str, values)) + '\n')
        output_file.write(" ".join("1" if l == str(label) else "0" for l in self.labels) + '\n')
        return True

    def process_image_csv(self, image_path, output_file):
        label = self._find_label(image_path)
        if label is None:
            print(f"Warning: {image_path} not labeled.")
            return False
        values = self._load_flat(image_path)
        output_file.write(f"{self.labels.index(str(label))}," + ",".join(map(str, values)) + '\n')
        return True

    def process_image_bin(self, image_path, f):
        label = self._find_label(image_path)
        if label is None:
            print(f"Warning: {image_path} not labeled.")
            return False
        raw = self._load_raw(image_path)
        f.write(struct.pack("<H", self.labels.index(str(label))))
        f.write(raw.tobytes())
        return True

    def process_folder_txt(self, input_folder):
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
            raise FileNotFoundError(f"Папка пуста или не найдена: {input_folder}")
        self.outputPath = self._new_path("txt")
        with open(self.outputPath, "w", encoding="utf-8") as out:
            for path in self._images_in(input_folder):
                try:
                    self.process_image_txt(path, out)
                except Exception as e:
                    print(f"Error processing {path}: {e}")

    def process_folder_csv(self, input_folder):
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
            raise FileNotFoundError(f"Папка пуста или не найдена: {input_folder}")
        w, h, c = self.resolution
        self.outputPath = self._new_path("csv")
        with open(self.outputPath, "w", encoding="utf-8") as out:
            out.write("label," + ",".join(str(i) for i in range(1, w * h * c + 1)) + '\n')
            for sub in sorted(os.listdir(input_folder)):
                sub_path = os.path.join(input_folder, sub)
                if not os.path.isdir(sub_path):
                    continue
                for path in self._images_in(sub_path):
                    try:
                        self.process_image_csv(path, out)
                    except Exception as e:
                        print(f"Error processing {path}: {e}")

    def process_folder_bin(self, input_folder):
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
            raise FileNotFoundError(f"Папка пуста или не найдена: {input_folder}")
        self.outputPath = self._new_path("bin")
        count = 0
        with open(self.outputPath, "wb") as f:
            count_pos = self._write_bin_header(f)
            for sub in sorted(os.listdir(input_folder)):
                sub_path = os.path.join(input_folder, sub)
                if not os.path.isdir(sub_path):
                    continue
                for path in self._images_in(sub_path):
                    try:
                        if self.process_image_bin(path, f):
                            count += 1
                    except Exception as e:
                        print(f"Error processing {path}: {e}")
            f.seek(count_pos)
            f.write(struct.pack("<I", count))


class ImageScaler:
    def __init__(self, root, exportFormat: str, folderPath="", labelsPath="", name=""):
        self.root = root
        self.name = name
        self.folder_label = Label(root)
        self.folder_label.pack(pady=10)
        self.error_label = Label(root, foreground="red")
        self.error_label.pack(pady=5)

        self.sc = Scaler(outDir=folderPath, name=name)

        self.folder = folderPath
        self.labels = labelsPath
        self.export_format = exportFormat if exportFormat in {"txt", "csv", "bin"} else "txt"
        self.initUI()

    def _set_status(self, text, color):
        self.error_label.config(text=text, foreground=color)

    def initUI(self):
        self.dimensions_frame = Frame(self.root)
        self.dimensions_frame.pack(pady=10)

        Label(self.dimensions_frame, text="Разрешение:").grid(row=0, column=0)
        self.width_entry = Entry(self.dimensions_frame, width=10)
        self.width_entry.insert(0, "64")
        self.width_entry.grid(row=1, column=0)
        Label(self.dimensions_frame, text="x").grid(row=1, column=1)
        self.height_entry = Entry(self.dimensions_frame, width=10)
        self.height_entry.insert(0, "64")
        self.height_entry.grid(row=1, column=2)
        Label(self.dimensions_frame, text="Каналы (1 или 3):", width=16).grid(row=2, column=0)
        self.channels_entry = Entry(self.dimensions_frame, width=10)
        self.channels_entry.insert(0, "1")
        self.channels_entry.grid(row=3, column=0)

        self.process_button = Button(self.root, text="Экспорт", command=self.process_folder)
        self.process_button.pack(pady=5)

        try:
            with open(self.labels, 'r', encoding='utf-8') as file:
                self.sc.set_label_map(json.load(file))
        except Exception as e:
            self.process_button.config(state="disabled")
            self._set_status(f"Не удалось загрузить файл меток:\n{self.labels}\n({e})", "red")
            return

        self._set_status(f"Выбрана папка:\n{self.folder}", "green")


    def process_folder(self):
        try:
            w, h = self.width_entry.get().strip(), self.height_entry.get().strip()
            if not w or not h:
                self._set_status("Укажите разрешение.", "red")
                return
            self.sc.set_resolution((int(w), int(h), int(self.channels_entry.get())))

            folder = os.path.join(self.folder, "images")

            handlers = {
                "txt": self.sc.process_folder_txt,
                "csv": self.sc.process_folder_csv,
                "bin": self.sc.process_folder_bin,
            }
            handlers[self.export_format](folder)

        except ValueError as e:
            self._set_status(f"Некорректные параметры: {e}", "red")
            return
        except Exception as e:
            self._set_status(f"Произошла ошибка: {e}", "red")
            return

        self._set_status(f"Папка успешно обработана.\nРезультат: {self.sc.outputPath}", "green")
