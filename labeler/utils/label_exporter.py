import json
import os


class LabelExporter:
    def __init__(self, folder, labels, output_path):
        self.folder = folder
        self.labels = labels
        self.output_path = output_path

    def export_to_txt(self):
        with open(self.labels) as f:
            labels = json.load(f)

        with open(os.path.join(self.output_path, f"labels.txt"), "w", encoding="utf-8") as f:
            for key, value in labels.items():
                f.write(f"{key} {value}\n")