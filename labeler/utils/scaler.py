import os
import cv2
import json
import struct
from tkinter import Label, Button, Frame, Entry, ttk, BooleanVar
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

    def collect_samples(self, input_folder):
        if not os.path.isdir(input_folder):
            raise FileNotFoundError(f"Папка не найдена: {input_folder}")

        samples, skipped = [], []
        for sub in sorted(os.listdir(input_folder)):
            sub_path = os.path.join(input_folder, sub)
            if not os.path.isdir(sub_path):
                continue
            for path in self._images_in(sub_path):
                if not os.path.isfile(path):
                    continue
                label = self._find_label(path)
                if label is None:
                    skipped.append((path, "Метка не найдена"))
                    continue
                try:
                    self._load_raw(path)
                except Exception as exc:
                    skipped.append((path, str(exc)))
                    continue
                samples.append((path, str(label)))

        if not samples:
            raise ValueError("Нет пригодных размеченных изображений для разделения.")
        return samples, skipped

    @staticmethod
    def split_samples(samples, validation_fraction=0.2, seed=42):
        import math
        import random

        if not 0 < validation_fraction < 1:
            raise ValueError("Доля validation должна быть между 0 и 1.")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("Seed должен быть целым числом.")
        if not samples:
            raise ValueError("Список изображений пуст.")

        groups, seen = {}, set()
        for path, label in sorted(samples, key=lambda item: (str(item[1]), item[0])):
            key = os.path.normcase(os.path.realpath(path))
            if key in seen:
                raise ValueError(f"Повторяющийся путь: {path}")
            seen.add(key)
            groups.setdefault(str(label), []).append((path, str(label)))

        rare = [label for label, items in groups.items() if len(items) < 2]
        if rare:
            raise ValueError(
                "Для разделения нужны минимум два изображения в каждом классе. "
                "Недостаточно примеров: " + ", ".join(rare))

        rng = random.Random(seed)
        train, validation = [], []
        for items in groups.values():
            items = items.copy()
            rng.shuffle(items)
            count = math.floor(len(items) * validation_fraction + 0.5)
            count = max(1, min(len(items) - 1, count))
            validation.extend(items[:count])
            train.extend(items[count:])
        rng.shuffle(train)
        rng.shuffle(validation)
        return train, validation

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

    def _export_samples(self, samples, export_format, output_path=None):
        samples = list(samples)
        if not samples:
            raise ValueError("Список для экспорта пуст.")
        for path, label in samples:
            if str(label) not in self.labels:
                raise ValueError(f"Неизвестный класс: {label}")
            current_label = self._find_label(path)
            if current_label is None or str(current_label) != str(label):
                raise ValueError(f"Метка изменилась или отсутствует: {path}")

        path = os.fspath(output_path) if output_path is not None else self._new_path(export_format)
        binary = export_format == "bin"
        options = {} if binary else {"encoding": "utf-8"}
        count = 0
        out = open(path, "xb" if binary else "x", **options)
        try:
            with out:
                if binary:
                    count_pos = self._write_bin_header(out)
                    writer = self.process_image_bin
                else:
                    w, h, c = self.resolution
                    out.write("label," + ",".join(str(i) for i in range(1, w * h * c + 1)) + "\n")
                    writer = self.process_image_csv
                for image_path, label in samples:
                    if not writer(image_path, out):
                        raise ValueError(f"Не удалось экспортировать: {image_path}")
                    count += 1
                if binary:
                    out.seek(count_pos)
                    out.write(struct.pack("<I", count))
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise

        self.outputPath = path
        return {"path": path, "written": count}

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

    def export_samples_csv(self, samples, output_path=None):
        return self._export_samples(samples, "csv", output_path)

    def export_samples_bin(self, samples, output_path=None):
        return self._export_samples(samples, "bin", output_path)

    def process_folder_csv(self, input_folder):
        samples, skipped = self.collect_samples(input_folder)
        result = self.export_samples_csv(samples)
        result["skipped"] = skipped
        for path, reason in skipped:
            print(f"Warning: {path}: {reason}")
        return result

    def process_folder_bin(self, input_folder):
        samples, skipped = self.collect_samples(input_folder)
        result = self.export_samples_bin(samples)
        result["skipped"] = skipped
        for path, reason in skipped:
            print(f"Warning: {path}: {reason}")
        return result


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
        for widget in (self.process_button, self.width_entry, self.height_entry,
                       self.channels_entry, self.split_check):
            widget.config(state=state)
        self._update_split_controls()

    def _update_split_controls(self):
        state = "normal" if self.split_enabled.get() and not self._export_running else "disabled"
        self.validation_entry.config(state=state)
        self.seed_entry.config(state=state)

    def _export_worker(self, split_enabled, fraction, seed):
        completed = []
        try:
            folder = os.path.join(self.folder, "images")
            if not split_enabled:
                handlers = {"csv": self.sc.process_folder_csv,
                            "bin": self.sc.process_folder_bin}
                result = handlers[self.export_format](folder)
                completed.append(("Датасет", result))
                skipped = result["skipped"]
            else:
                samples, skipped = self.sc.collect_samples(folder)
                train, validation = self.sc.split_samples(samples, fraction, seed)
                base = os.path.splitext(self.sc._new_path(self.export_format))[0]
                export = {"csv": self.sc.export_samples_csv,
                          "bin": self.sc.export_samples_bin}[self.export_format]
                for title, suffix, part in (("Train", "train", train),
                                            ("Validation", "validation", validation)):
                    path = f"{base}_{suffix}.{self.export_format}"
                    completed.append((title, export(part, path)))
            self._export_queue.put(("done", {
                "results": completed, "skipped": skipped,
                "split": split_enabled,
            }))
        except Exception as exc:
            self._export_queue.put(("error", {
                "message": str(exc), "results": completed,
            }))

    def _show_result_paths(self, results):
        for child in self.results_frame.winfo_children():
            child.destroy()
        for row, (title, result) in enumerate(results):
            ttk.Label(self.results_frame, text=f"{title}:").grid(
                row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            entry = ttk.Entry(self.results_frame)
            entry.insert(0, result["path"])
            entry.config(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=2)

    def _poll_export(self):
        try:
            event, payload = self._export_queue.get_nowait()
        except Empty:
            self.root.after(100, self._poll_export)
            return

        self._export_running = False
        self._set_export_controls("normal")
        self._show_result_paths(payload["results"])
        if event == "error":
            text = f"Ошибка экспорта: {payload['message']}"
            if payload["results"]:
                text += "\nЧасть файлов уже создана и сохранена; пути указаны ниже."
            self._set_status(text, "red")
            return

        results, skipped = payload["results"], payload["skipped"]
        summary = " · ".join(f"{title}: {result['written']}" for title, result in results)
        if payload["split"]:
            total = sum(result["written"] for _, result in results)
            actual = results[1][1]["written"] / total * 100
            summary += f"\nФактическая доля validation: {actual:.1f}%"
        text = f"Экспорт завершён.\n{summary}\nПропущено: {len(skipped)}"
        if skipped:
            path, reason = skipped[0]
            text += f"\nПервый пропуск: {path} — {reason}"
        self._set_status(text, "darkorange" if skipped else "green")

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

        self.split_enabled = BooleanVar(master=self.root, value=False)
        self.split_frame = ttk.LabelFrame(
            self.main_frame, text="Разделение датасета", padding=10)
        self.split_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.split_check = ttk.Checkbutton(
            self.split_frame, text="Разделять на train / validation",
            variable=self.split_enabled, command=self._update_split_controls)
        self.split_check.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self.split_frame, text="Проверочная выборка:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.validation_entry = ttk.Entry(self.split_frame, width=8)
        self.validation_entry.insert(0, "20")
        self.validation_entry.grid(row=1, column=1, pady=(8, 0))
        ttk.Label(self.split_frame, text="%").grid(
            row=1, column=2, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Label(self.split_frame, text="Seed:").grid(
            row=2, column=0, sticky="w", pady=(8, 0))
        self.seed_entry = ttk.Entry(self.split_frame, width=8)
        self.seed_entry.insert(0, "42")
        self.seed_entry.grid(row=2, column=1, pady=(8, 0))
        self._update_split_controls()

        self.process_button = ttk.Button(self.main_frame, text="Экспортировать", command=self.process_folder)
        self.process_button.grid(row=5, column=0, pady=(14, 8))
        self.error_label = ttk.Label(self.main_frame, anchor="center", justify="center", wraplength=480)
        self.error_label.grid(row=6, column=0, sticky="ew", pady=(0, 2))
        self.results_frame = ttk.Frame(self.main_frame)
        self.results_frame.grid(row=7, column=0, sticky="ew", pady=(6, 0))
        self.results_frame.columnconfigure(1, weight=1)


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
            split_enabled = self.split_enabled.get()
            fraction, seed = None, None
            if split_enabled:
                fraction = float(self.validation_entry.get().strip().replace(",", ".")) / 100
                if not 0 < fraction < 1:
                    raise ValueError("Доля validation должна быть больше 0 и меньше 100%.")
                seed = int(self.seed_entry.get().strip())
        except ValueError as exc:
            self._set_status(f"Некорректные параметры: {exc}", "red")
            return

        self._export_running = True
        self._set_export_controls("disabled")
        self._set_status("Выполняется экспорт...", "blue")

        self._show_result_paths([])
        Thread(
            target=self._export_worker,
            args=(split_enabled, fraction, seed),
            daemon=True,
        ).start()
        self.root.after(100, self._poll_export)
