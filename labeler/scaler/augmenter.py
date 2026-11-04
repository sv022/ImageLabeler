# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Offline AugMix adapted from Google Research's NumPy reference.

Changes: uint8 HxW/HxWx3 API, arbitrary dimensions, local RNG,
no dataset-specific normalization, optional extended operators.
Dependencies: numpy, Pillow. RGB channel order is required for color input.
No JSD loss or label manipulation is performed here.
"""
from numbers import Integral, Real
import numpy as np
from PIL import Image, ImageOps, ImageEnhance


class AugMixAugmenter:
    BASE_OPS = (
        "autocontrast", "equalize", "posterize", "rotate", "solarize",
        "shear_x", "shear_y", "translate_x", "translate_y",
    )
    EXTRA_OPS = ("color", "contrast", "brightness", "sharpness")

    def __init__(self, severity=2, mixture_width=3, chain_depth=-1,
                 alpha=1.0, seed=None, all_ops=False):
        self._check_integer("severity", severity, 1, 10)
        self._check_integer("mixture_width", mixture_width, 1)
        if (isinstance(chain_depth, bool)
                or not isinstance(chain_depth, Integral)
                or (chain_depth != -1 and chain_depth < 1)):
            raise ValueError("chain_depth must be -1 or a positive integer")
        if (isinstance(alpha, bool) or not isinstance(alpha, Real)
                or not np.isfinite(alpha) or alpha <= 0):
            raise ValueError("alpha must be finite and positive")
        if seed is not None:
            self._check_integer("seed", seed, 0)
        if not isinstance(all_ops, bool):
            raise ValueError("all_ops must be bool")
        self.severity = int(severity)
        self.mixture_width = int(mixture_width)
        self.chain_depth = int(chain_depth)
        self.alpha = float(alpha)
        self.rng = np.random.default_rng(seed)
        self._ops = self.BASE_OPS + (self.EXTRA_OPS if all_ops else ())

    @staticmethod
    def _check_integer(name, value, minimum, maximum=None):
        if (isinstance(value, bool) or not isinstance(value, Integral)
                or value < minimum
                or (maximum is not None and value > maximum)):
            raise ValueError(f"Invalid {name}: {value!r}")

    def apply(self, image):
        if not isinstance(image, np.ndarray):
            raise TypeError("image must be a numpy array")
        if image.dtype != np.uint8:
            raise TypeError("image dtype must be uint8")
        if not (image.ndim == 2 or
                (image.ndim == 3 and image.shape[2] == 3)):
            raise ValueError("Expected HxW grayscale or HxWx3 RGB")
        if image.shape[0] == 0 or image.shape[1] == 0:
            raise ValueError("Image dimensions must be positive")

        original = Image.fromarray(image)
        weights = self.rng.dirichlet([self.alpha] * self.mixture_width).astype(np.float32)
        m = np.float32(self.rng.beta(self.alpha, self.alpha))
        mix = np.zeros(image.shape, dtype=np.float32)
        for weight in weights:
            augmented = original.copy()
            depth = (self.chain_depth if self.chain_depth > 0
                     else int(self.rng.integers(1, 4)))
            for _ in range(depth):
                name = self._ops[int(self.rng.integers(len(self._ops)))]
                augmented = self._apply_op(augmented, name)
            mix += weight * np.asarray(augmented, dtype=np.float32)
        result = (1.0 - m) * image.astype(np.float32) + m * mix
        return np.ascontiguousarray(np.clip(np.rint(result), 0, 255).astype(np.uint8))

    def _level(self, maximum, integer=False):
        value = self.rng.uniform(0.1, self.severity) * maximum / 10.0
        return int(value) if integer else float(value)

    def _signed(self, value):
        return -value if self.rng.random() > 0.5 else value

    def _apply_op(self, image, name):
        if name == "autocontrast":
            return ImageOps.autocontrast(image)
        if name == "equalize":
            return ImageOps.equalize(image)
        if name == "posterize":
            return ImageOps.posterize(image, 4 - self._level(4, integer=True))
        if name == "solarize":
            return ImageOps.solarize(image, 256 - self._level(256, integer=True))
        if name == "rotate":
            angle = self._signed(self._level(30, integer=True))
            return image.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=0)
        if name in ("shear_x", "shear_y", "translate_x", "translate_y"):
            w, h = image.size
            if name == "shear_x":
                matrix = (1, self._signed(self._level(0.3)), 0, 0, 1, 0)
            elif name == "shear_y":
                matrix = (1, 0, 0, self._signed(self._level(0.3)), 1, 0)
            elif name == "translate_x":
                matrix = (1, 0, self._signed(self._level(w / 3, True)), 0, 1, 0)
            else:
                matrix = (1, 0, 0, 0, 1, self._signed(self._level(h / 3, True)))
            return image.transform(image.size, Image.Transform.AFFINE, matrix,
                                   resample=Image.Resampling.BILINEAR, fillcolor=0)
        enhancers = {
            "color": ImageEnhance.Color, "contrast": ImageEnhance.Contrast,
            "brightness": ImageEnhance.Brightness, "sharpness": ImageEnhance.Sharpness,
        }
        return enhancers[name](image).enhance(self._level(1.8) + 0.1)
