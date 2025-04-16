import csv
from datetime import datetime
import os
import gzip
import struct
import tempfile
import shutil
import urllib.parse
import requests
import numpy as np


mnist_info = {
    'train' : { 'labels' : 'train-labels-idx1-ubyte.gz',
                'images' : 'train-images-idx3-ubyte.gz' },
    'test'  : { 'labels' : 't10k-labels-idx1-ubyte.gz',
                'images' : 't10k-images-idx3-ubyte.gz' },
    'fashion' : 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/',
    'digits': 'https://storage.googleapis.com/cvdf-datasets/mnist/'
}


idx_dt = {
    0x08 : 'B', # uint8
    0x09 : 'b', # int8
    0x0b : 'h', # int16
    0x0c : 'i', # int32
    0x0d : 'f', # float32
    0x0e : 'd', # float64
}

def random_sample(data_train: np.array, labels_test : np.array, size: int = 1) -> tuple[list, list]:

    data_train_norm = [[np.around(int(x) / 255, decimals=2) for x in sample.flatten()] for sample in data_train]

    res_train = []
    res_test = []

    for i in range(size):
        index = np.random.randint(0, len(data_train_norm))
        res_train.append(data_train_norm[index])
        res_test.append(labels_test[index])
    return res_train, res_test

def download_mnist_file(fname, target_dir, force=False, kind='digits'):
    target_fname = os.path.join(target_dir, fname)

    if force or not os.path.isfile(target_fname):
        url = urllib.parse.urljoin(mnist_info[kind], fname)
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(target_fname, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    size = f.write(chunk)


def parse_idx(fname, target_dir):
    with gzip.open(os.path.join(target_dir, fname), 'rb') as f:
        zeros, dt, ndims = struct.unpack('>HBB', f.read(4))
        dims = struct.unpack('>' + 'I'*ndims, f.read(4*ndims))
        dt = np.dtype('>' + idx_dt[dt])
        data = np.frombuffer(f.read(), dtype=dt)
        return data.reshape(dims)


class MNIST(object):
    def __init__(self, kind: str, target_dir=None, clean_up=False, force=False):
        if target_dir is None:
            self.target_dir = tempfile.mkdtemp(prefix='mnist')
            self.clean_up = True
        else:
            os.makedirs(target_dir, exist_ok=True)
            self.target_dir = target_dir
            self.clean_up = clean_up

        self.force = force
        self.kind = kind


    def __del__(self):
        if self.clean_up:
            shutil.rmtree(self.target_dir)


    def train_labels(self):
        download_mnist_file(mnist_info['train']['labels'],
                            self.target_dir, force=self.force, kind=self.kind)
        return parse_idx(mnist_info['train']['labels'], self.target_dir)


    def train_images(self):
        download_mnist_file(mnist_info['train']['images'],
                            self.target_dir, force=self.force, kind=self.kind)
        return parse_idx(mnist_info['train']['images'], self.target_dir)


    def test_labels(self):
        download_mnist_file(mnist_info['test']['labels'],
                            self.target_dir, force=self.force, kind=self.kind)
        return parse_idx(mnist_info['test']['labels'], self.target_dir)


    def test_images(self):
        download_mnist_file(mnist_info['test']['images'],
                            self.target_dir, force=self.force, kind=self.kind)
        return parse_idx(mnist_info['test']['images'], self.target_dir)


def load_mnist(outDir: str, kind : str, train_size=60000, test_size=10000):
    mnist = MNIST(kind)

    Xtrain, ytrain = mnist.train_images(), mnist.train_labels()

    Xtest, ytest = mnist.test_images(), mnist.test_labels()

    Xtrain, ytrain = random_sample(Xtrain, ytrain, size=train_size)
    Xtest, ytest = random_sample(Xtest, ytest, size=test_size)

    # print(len(Xtrain), len(ytrain), len(Xtest), len(ytest))
    # print(type(Xtrain), type(ytrain), type(Xtest), type(ytest))
    # print(Xtrain[0])
    # print(ytrain[0])

    header = ["label"] + [str(i) for i in range(784)]

    now = datetime.today().strftime('%Y_%m_%d_%H%M%S')
    train_path = os.path.join(outDir, f"mnist_{kind}_train_{train_size}_{now}.csv")
    test_path = os.path.join(outDir, f"mnist_{kind}_test_{test_size}_{now}.csv")

    with open(train_path, 'w', newline='') as csv_out:
        writer = csv.writer(csv_out)
        writer.writerow(header)
        for i in range(len(Xtrain)):
            writer.writerow([ytrain[i]] + Xtrain[i])

    with open(test_path, 'w', newline='') as csv_out:
        writer = csv.writer(csv_out)
        writer.writerow(header)
        for i in range(len(Xtest)):
            writer.writerow([ytest[i]] + Xtest[i])
