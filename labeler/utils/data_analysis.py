import json
from collections import Counter
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_from_labels(labels_path: str):
    try:
        with open(labels_path, 'r') as f:
            labels = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return

    class_counts = Counter(labels.values())
    classes = sorted(class_counts.keys(), key=lambda x: class_counts[x], reverse=True)
    counts = [class_counts[cls] for cls in classes]
    total_samples = sum(counts)
    
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "bar"}, {"type": "pie"}],
               [{"type": "bar"}, {"type": "heatmap"}]],
        subplot_titles=(
            "Распределение классов",
            "Круговая диаграмма распределения классов",
            "Наиболее частые / редкие классы"
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=classes,
            y=counts,
            marker_color=px.colors.qualitative.Plotly,
            text=[f"{c} ({c/total_samples:.1%})" for c in counts],
            textposition='auto',
            name="Count"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Pie(
            labels=classes,
            values=counts,
            hole=0.3,
            marker_colors=px.colors.qualitative.Plotly,
            textinfo='percent+label',
            name="Proportion"
        ),
        row=1, col=2
    )
    
    top_n = 5
    top_classes = classes[:top_n]
    top_counts = counts[:top_n]
    bottom_classes = classes[-top_n:] if len(classes) > top_n else classes
    bottom_counts = counts[-top_n:] if len(counts) > top_n else counts
    
    fig.add_trace(
        go.Bar(
            x=top_counts,
            y=top_classes,
            orientation='h',
            marker_color='green',
            name="Наиболее частые",
            text=top_counts
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=bottom_counts,
            y=bottom_classes,
            orientation='h',
            marker_color='red',
            name="Наиболее редкие",
            text=bottom_counts
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title_text=f"Анализ данных из файла {os.path.basename(labels_path)} (Размер выборки: {total_samples})",
        height=800,
        showlegend=False
    )
    
    fig.show()


def plot_from_file(file_path: str):
    labels = {}
    samples = []
    
    with open(file_path, 'r') as f:
        while True:
            data_line = f.readline().strip()
            label_line = f.readline().strip()
            
            if not data_line or not label_line:
                break
                
            label = [float(x) for x in label_line.split()]
            class_id = np.argmax(label)
            labels[class_id] = labels.get(class_id, 0) + 1
            
            sample = [float(x) for x in data_line.split()]
            samples.append(sample)
    
    classes = sorted(labels.keys())
    counts = [labels[cls] for cls in classes]
    total_samples = sum(counts)
    samples = np.array(samples)
    
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "bar"}, {"type": "pie"}],
               [{"type": "heatmap"}, {"type": "heatmap"}]],
        subplot_titles=(
            "Распределение классов",
            "Круговая диаграмма распределения классов",
            "Пример изображения" if samples.shape[1] == 784 else "Тепловая карта",
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=classes,
            y=counts,
            marker_color=px.colors.qualitative.Plotly,
            text=[f"{c} ({c/total_samples:.1%})" for c in counts],
            name="Классы"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Pie(
            labels=classes,
            values=counts,
            hole=0.3,
            marker_colors=px.colors.qualitative.Plotly
        ),
        row=1, col=2
    )
    
    if samples.shape[1] == 784:
        example = samples[0].reshape(28, 28)
        fig.add_trace(
            go.Heatmap(
                z=example,
                colorscale='gray',
                showscale=False,
            ),
            row=2, col=1
        )
    else:
        fig.add_trace(
            go.Heatmap(
                z=samples[:20],
                colorscale='Viridis'
            ),
            row=2, col=1
        )

    fig.update_layout(
        title_text=f"Анализ датасета (Размер выборки: {total_samples})",
        height=800,
        autosize=True,
        yaxis2_scaleanchor="x2"
    )

    fig.show()


def plot_from_csv(csv_path: str):
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return
    
    labels = df.iloc[:, 0].values
    images = df.iloc[:, 1:].values

    class_counts = dict(zip(*np.unique(labels, return_counts=True)))
    classes = sorted(class_counts.keys())
    counts = [class_counts[cls] for cls in classes]
    total_samples = len(labels)
    
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "bar"}, {"type": "pie"}],
               [{"type": "heatmap"}, {"type": "scatter"}]],
        subplot_titles=(
            "Распределение классов",
            "Круговая диаграмма классов",
            "Пример изображения"
        )
    )

    fig.add_trace(
        go.Bar(
            x=classes,
            y=counts,
            marker_color=px.colors.qualitative.Plotly,
            text=[f"{c} ({c/total_samples:.1%})" for c in counts],
            name="Классы"
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Pie(
            labels=classes,
            values=counts,
            hole=0.3,
            marker_colors=px.colors.qualitative.Plotly
        ),
        row=1, col=2
    )
    
    if images.shape[1] == 784:
        example = images[0].reshape(28, 28)
        fig.add_trace(
            go.Heatmap(
                z=example,
                colorscale='gray',
                showscale=False
            ),
            row=2, col=1
        )
    
    fig.update_layout(
        title_text=f"Анализ датасета (Размер выборки: {total_samples})",
        height=800,
        showlegend=True,
        yaxis2_scaleanchor="x2"
    )
    
    fig.show()