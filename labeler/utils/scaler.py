import os
import cv2
import json
import struct
from tkinter import Label, Button, Frame, Entry, ttk
from numpy import ascontiguousarray, around
from datetime import datetime
from threading import Thread
from queue import Queue, Empty


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

    def _export_images(self, input_folder, output_file, processor):
        stats = {
            "found": 0,
            "written": 0,
            "unlabeled": 0,
            "errors": 0,
            "first_error": None,
        }

        for sub in sorted(os.listdir(input_folder)):
            sub_path = os.path.join(input_folder, sub)
            if not os.path.isdir(sub_path):
                continue

            for path in self._images_in(sub_path):
                stats["found"] += 1

                try:
                    if processor(path, output_file):
                        stats["written"] += 1
                    else:
                        stats["unlabeled"] += 1
                except Exception as exc:
                    stats["errors"] += 1
                    if stats["first_error"] is None:
                        stats["first_error"] = f"{path}: {exc}"
                    print(f"Error processing {path}: {exc}")

        return stats

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

    def process_folder_csv(self, input_folder):
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
            raise FileNotFoundError(
                f"Папка пуста или не найдена: {input_folder}"
            )

        w, h, c = self.resolution
        self.outputPath = self._new_path("csv")

        with open(self.outputPath, "w", encoding="utf-8") as out:
            out.write(
                "label,"
                + ",".join(str(i) for i in range(1, w * h * c + 1))
                + "\n"
            )
            stats = self._export_images(
                input_folder, out, self.process_image_csv
            )

        return stats


    def process_folder_bin(self, input_folder):
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
            raise FileNotFoundError(
                f"Папка пуста или не найдена: {input_folder}"
            )

        self.outputPath = self._new_path("bin")

        with open(self.outputPath, "wb") as out:
            count_pos = self._write_bin_header(out)
            stats = self._export_images(
                input_folder, out, self.process_image_bin
            )
            out.seek(count_pos)
            out.write(struct.pack("<I", stats["written"]))

        return stats


class ImageScaler:
    def __init__(self, root, exportFormat: str, folderPath="", labelsPath="", name=""):
        self.root = root
        self.name = name

        self.sc = Scaler(outDir=folderPath, name=name)

        self.folder = folderPath
        self.labels = labelsPath
        self.export_format = exportFormat if exportFormat in {"csv", "bin"} else "csv"
        self._export_queue = Queue()
        self._export_running = False
        self.initUI()

    def _set_export_controls(self, state):
        for widget in (self.process_button, self.width_entry, self.height_entry,self.channels_entry): widget.config(state=state)


    def _export_worker(self):
        try:
            folder = os.path.join(self.folder, "images")
            handlers = {
                "csv": self.sc.process_folder_csv,
                "bin": self.sc.process_folder_bin,
            }

            stats = handlers[self.export_format](folder)
            self._export_queue.put(("done", stats))
        except Exception as exc:
            self._export_queue.put(("error", str(exc)))


    def _poll_export(self):
        try:
            event, payload = self._export_queue.get_nowait()
        except Empty:
            self.root.after(100, self._poll_export)
            return

        self._export_running = False
        self._set_export_controls("normal")

        if event == "error":
            self._set_status(f"Ошибка экспорта: {payload}", "red")
            return

        stats = payload

        summary = (
            f"Найдено: {stats['found']}; "
            f"записано: {stats['written']}; "
            f"без меток: {stats['unlabeled']}; "
            f"ошибок: {stats['errors']}."
        )

        if stats["written"] == 0:
            title = "Экспорт завершён без записанных изображений."
            color = "red"
        elif stats["unlabeled"] or stats["errors"]:
            title = "Экспорт завершён с пропусками или ошибками."
            color = "darkorange"
        else:
            title = "Экспорт успешно завершён."
            color = "green"

        text = (
            f"{title}\n{summary}\n"
            f"Файл результата: {self.sc.outputPath}"
        )

        if stats["first_error"]:
            text += f"\nПервая ошибка: {stats['first_error']}"

        self._set_status(text, color)

    def _set_status(self, text, color):
        self.error_label.config(text=text, foreground=color)

    def initUI(self):
        self.main_frame = ttk.Frame(self.root, padding=12)
        self.main_frame.pack(side="top", fill="x", anchor="nw")
        self.main_frame.columnconfigure(0, weight=1)

        self.folder_label = ttk.Label(
            self.main_frame,
            text=f"Источник: {os.path.join(self.folder, 'images')}",
            wraplength=480)
        self.folder_label.grid(row=1, column=0, sticky="w")
        ttk.Label(
            self.main_frame, text=f"Результаты: {self.sc.outDir}",
            wraplength=480).grid(row=2, column=0, sticky="w", pady=(4, 0))

        self.dimensions_frame = ttk.LabelFrame(
            self.main_frame, text="Параметры", padding=10)
        self.dimensions_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(self.dimensions_frame, text="Размер:").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.width_entry = ttk.Entry(self.dimensions_frame, width=8)
        self.width_entry.insert(0, "64")
        self.width_entry.grid(row=0, column=1)
        ttk.Label(self.dimensions_frame, text="x").grid(
            row=0, column=2, padx=6)
        self.height_entry = ttk.Entry(self.dimensions_frame, width=8)
        self.height_entry.insert(0, "64")
        self.height_entry.grid(row=0, column=3)
        ttk.Label(self.dimensions_frame, text="пикселей").grid(
            row=0, column=4, padx=(8, 0))

        ttk.Label(self.dimensions_frame, text="Каналы:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.channels_entry = ttk.Entry(self.dimensions_frame, width=8)
        self.channels_entry.insert(0, "1")
        self.channels_entry.grid(row=1, column=1, pady=(8, 0))
        ttk.Label(self.dimensions_frame, text="1 — grayscale, 3 — RGB").grid(row=1, column=2, columnspan=3, sticky="w", padx=(6, 0), pady=(8, 0))

        ttk.Label(self.dimensions_frame, text=f"Формат: {self.export_format}").grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))

        self.process_button = ttk.Button(self.main_frame, text="Экспортировать", command=self.process_folder)
        self.process_button.grid(row=5, column=0, pady=(14, 8))
        self.error_label = ttk.Label(self.main_frame, anchor="center", justify="center", wraplength=480)
        self.error_label.grid(row=6, column=0, sticky="ew", pady=(0, 2))

        try:
            with open(self.labels, 'r', encoding='utf-8') as file:
                self.sc.set_label_map(json.load(file))
        except Exception as e:
            self.process_button.config(state="disabled")
            self._set_status(f"Не удалось загрузить файл меток:\n{self.labels}\n({e})", "red")
            return

        self._set_status("Готов к экспорту.", "green")


    def process_folder(self):
        if self._export_running:
            return

        try:
            w = self.width_entry.get().strip()
            h = self.height_entry.get().strip()

            if not w or not h:
                self._set_status("Укажите разрешение.", "red")
                return

            self.sc.set_resolution((
                int(w),
                int(h),
                int(self.channels_entry.get()),
            ))
        except ValueError as exc:
            self._set_status(f"Некорректные параметры: {exc}", "red")
            return

        self._export_running = True
        self._set_export_controls("disabled")
        self._set_status("Выполняется экспорт...", "blue")

        Thread(target=self._export_worker, daemon=True).start()
        self.root.after(100, self._poll_export)
