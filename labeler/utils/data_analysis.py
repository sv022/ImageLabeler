import json
from collections import Counter
import os
import struct
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_bin(path):
    with open(path, "rb") as f:
        assert f.read(4) == b"IMGS", "Неверная сигнатура"
        version, w, h, c = struct.unpack("<BHHB", f.read(6))
        (n_labels,) = struct.unpack("<H", f.read(2))
        labels = []
        for _ in range(n_labels):
            (ln,) = struct.unpack("<H", f.read(2))
            labels.append(f.read(ln).decode("utf-8"))
        (n,) = struct.unpack("<I", f.read(4))
        size = w * h * c
        dtype = np.dtype([("label", "<u2"), ("pixels", "u1", (size,))])
        data = np.frombuffer(f.read(n * dtype.itemsize), dtype=dtype)
    X = data["pixels"].reshape(n, c, h, w)
    y = data["label"].astype("int64")
    return X, y, labels


def _infer_chw(size: int):
    s = int(round(size ** 0.5))
    if s * s == size:
        return 1, s, s
    s = int(round((size / 3) ** 0.5))
    if 3 * s * s == size:
        return 3, s, s
    raise ValueError(
        f"Не удалось определить размер изображения по длине {size}. Передайте shape=(c, h, w)."
    )


def _plot_dataset(X, y, class_names, title="Анализ датасета", top_n=5):
    n = len(y)
    if n == 0:
        print("Нет данных для отображения.")
        return

    class_ids, counts = np.unique(y, return_counts=True)
    classes = [str(class_names[i]) for i in class_ids]
    palette = px.colors.qualitative.Plotly
    colors = [palette[i % len(palette)] for i in range(len(classes))]

    has_images = X is not None
    if has_images:
        _, c, h, w = X.shape
        if X.dtype.kind == "f" and X.max() <= 1.0:
            X = X * 255.0
        titles = (
            "Распределение классов",
            "Круговая диаграмма классов",
            f"Пример изображения ({w}x{h}x{c}), класс: {class_names[y[0]]}",
            "Распределение яркости пикселей",
        )
    else:
        titles = (
            "Распределение классов",
            "Круговая диаграмма классов",
            "Наиболее частые классы",
            "Наиболее редкие классы",
        )

    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "bar"}, {"type": "pie"}],
               [{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=titles,
    )

    fig.add_trace(
        go.Bar(x=classes, y=counts.tolist(), marker_color=colors,
               text=[f"{k} ({k / n:.1%})" for k in counts], textposition="auto",
               name="Классы"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Pie(labels=classes, values=counts.tolist(), hole=0.3,
               marker_colors=colors, textinfo="percent+label"),
        row=1, col=2,
    )

    if has_images:
        example = X[0]
        if c == 1:
            fig.add_trace(
                go.Heatmap(z=example[0], colorscale="gray", zmin=0, zmax=255, showscale=False),
                row=2, col=1,
            )
        else:
            rgb = np.moveaxis(example, 0, -1).astype("uint8")  # CHW -> HWC, каналы уже RGB
            fig.add_trace(go.Image(z=rgb), row=2, col=1)

        rng = np.random.default_rng(0)
        flat = X.reshape(-1)
        sample = flat[rng.integers(0, flat.size, size=min(flat.size, 200_000))]
        fig.add_trace(
            go.Histogram(x=sample, xbins=dict(start=0, end=256, size=8),
                         marker_color=palette[0], name="Яркость"),
            row=2, col=2,
        )
        fig.update_yaxes(autorange="reversed", scaleanchor="x2", constrain="domain",
                         row=2, col=1)
    else:
        k = min(top_n, len(classes))
        order = np.argsort(-counts, kind="stable")
        top = order[:k]
        bottom = order[::-1][:k]
        for idx, color, col in ((top, "green", 1), (bottom, "red", 2)):
            fig.add_trace(
                go.Bar(x=counts[idx].tolist(), y=[classes[i] for i in idx],
                       orientation="h", marker_color=color,
                       text=counts[idx].tolist(), textposition="auto"),
                row=2, col=col,
            )
            fig.update_yaxes(type="category", autorange="reversed", row=2, col=col)

    fig.update_layout(
        title_text=f"{title} (Размер выборки: {n})",
        height=800,
        showlegend=False,
    )
    fig.show()

def plot_from_labels(labels_path: str):
    try:
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return
    names, y = np.unique([str(v) for v in labels.values()], return_inverse=True)
    _plot_dataset(None, y, list(names), title=f"Анализ данных из файла {os.path.basename(labels_path)}")

def plot_from_bin(bin_path: str):
    try:
        X, y, label_names = load_bin(bin_path)
    except Exception as e:
        print(f"Error loading BIN: {e}")
        return
    _plot_dataset(X, y, label_names)


def plot_from_file(file_path: str, shape=None, class_names=None):
    samples, ids = [], []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if len(lines) % 2:
            raise ValueError("Нечётное число строк: пропущена пара «данные + метка».")
        for data_line, label_line in zip(lines[0::2], lines[1::2]):
            ids.append(int(np.argmax(np.array(label_line.split(), dtype=np.float32))))
            samples.append(np.array(data_line.split(), dtype=np.float32))
        X = np.stack(samples)
    except Exception as e:
        print(f"Error loading TXT: {e}")
        return

    y = np.array(ids)
    c, h, w = shape or _infer_chw(X.shape[1])
    X = X.reshape(-1, c, h, w)
    names = class_names or [str(i) for i in range(int(y.max()) + 1)]
    _plot_dataset(X, y, names)


def plot_from_csv(csv_path: str, shape=None):
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    names, y = np.unique(df.iloc[:, 0].astype(str).values, return_inverse=True)
    X = df.iloc[:, 1:].to_numpy(dtype=np.float32)
    try:
        c, h, w = shape or _infer_chw(X.shape[1])
    except ValueError as e:
        print(e)
        return
    _plot_dataset(X.reshape(-1, c, h, w), y, list(names))
