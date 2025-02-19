import json
import plotly.express as px
from collections import Counter

def plot_from_labels(labelsPath: str):
    try:
        with open(f'{labelsPath}/labels.json', 'r') as f:
            labels = json.load(f)
    except Exception:
        return

    class_counts = Counter(labels.values())

    classes = list(class_counts.keys())
    counts = list(class_counts.values())

    total_samples = sum(counts)

    fig = px.pie(values=counts, names=classes, title='Соотношение классов в датасете', hole=0.4)

    fig.update_layout(
        annotations=[
            {
                "text": f"Выборка: {total_samples}",
                "x": 0.5,
                "y": 0.5,
                "font_size": 20,
                "showarrow": False
            }
        ]
    )

    fig.show()


def plot_from_file(filePath : str):
    labels = {}
    with open(filePath, 'r') as f:
        f.readline()
        line = f.readline().strip()
        while line:
            line = line.replace(' ', '')
            try:
                labels[line.find('1')] += 1
            except Exception:
                labels[line.find('1')] = 1
            f.readline()
            line = f.readline().strip()

    classes = list(labels.keys())
    counts = list(labels.values())

    total_samples = sum(counts)

    fig = px.pie(values=counts, names=classes, title='Соотношение классов в датасете', hole=0.4)

    fig.update_layout(
        annotations=[
            {
                "text": f"Выборка: {total_samples}",
                "x": 0.5,
                "y": 0.5,
                "font_size": 20,
                "showarrow": False
            }
        ]
    )

    fig.show()
