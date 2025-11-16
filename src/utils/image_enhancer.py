"""Utility helpers for pre-processing frames before vehicle detection."""

from __future__ import annotations

import cv2
import numpy as np
from typing import Dict, Tuple


def _apply_gray_world_white_balance(image: np.ndarray) -> np.ndarray:
    """Normalize channels so that white cars retain definition."""
    result = image.astype('float32')
    avg_per_channel = np.mean(result, axis=(0, 1))
    gray_value = np.mean(avg_per_channel)
    scale = gray_value / (avg_per_channel + 1e-6)
    result *= scale
    return np.clip(result, 0, 255).astype('uint8')


def _apply_clahe(image: np.ndarray, clip_limit: float, tile_grid_size: Tuple[int, int]) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _apply_gamma(image: np.ndarray, gamma: float) -> np.ndarray:
    if gamma <= 0 or abs(gamma - 1.0) < 1e-3:
        return image
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)], dtype='uint8')
    return cv2.LUT(image, table)


def enhance_for_vehicle_detection(frame: np.ndarray, settings: Dict | None = None) -> np.ndarray:
    """Apply light-weight enhancement tailored to reflective/white vehicles."""
    if frame is None:
        return frame

    config = settings or {}
    working = frame.copy()

    if config.get('apply_white_balance', True):
        working = _apply_gray_world_white_balance(working)

    if config.get('apply_clahe', True):
        clip_limit = float(config.get('clahe_clip_limit', 2.5))
        grid = config.get('clahe_tile_grid_size', (8, 8))
        if isinstance(grid, (list, tuple)):
            if len(grid) == 2:
                tile_grid = (int(grid[0]), int(grid[1]))
            else:
                tile_grid = (8, 8)
        else:
            tile_grid = (8, 8)
        working = _apply_clahe(working, clip_limit=clip_limit, tile_grid_size=tile_grid)

    if config.get('apply_gamma', True):
        gamma_value = float(config.get('gamma', 1.1))
        working = _apply_gamma(working, gamma_value)

    if config.get('smooth_noise', True):
        diameter = int(config.get('bilateral_filter_diameter', 5))
        sigma_color = int(config.get('bilateral_filter_sigma_color', 75))
        sigma_space = int(config.get('bilateral_filter_sigma_space', 75))
        working = cv2.bilateralFilter(working, d=diameter, sigmaColor=sigma_color, sigmaSpace=sigma_space)

    return working
