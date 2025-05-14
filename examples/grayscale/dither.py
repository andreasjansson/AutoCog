#!/usr/bin/env python3

import argparse
from pathlib import Path
import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an image to grayscale dithered version")
    parser.add_argument("input", type=str, help="Input image path")
    parser.add_argument("output", type=str, help="Output image path")
    parser.add_argument(
        "--method",
        choices=["floyd-steinberg", "ordered"],
        default="floyd-steinberg",
        help="Dithering method to use"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Threshold for binary output (0-255)"
    )
    parser.add_argument(
        "--levels",
        type=int,
        default=2,
        help="Number of gray levels (2 for binary)"
    )
    return parser.parse_args()


def floyd_steinberg_dithering(img: np.ndarray, levels: int = 2, threshold: int = 128) -> np.ndarray:
    """Apply Floyd-Steinberg dithering to a grayscale image."""
    height, width = img.shape
    output = img.copy().astype(float)

    # Define the quantization function based on levels
    if levels == 2:
        def quantize(val):
            return 255 if val > threshold else 0
    else:
        step = 255 / (levels - 1)
        def quantize(val):
            return round(round(val / step) * step)

    for y in range(height):
        for x in range(width):
            old_pixel = output[y, x]
            new_pixel = quantize(old_pixel)
            output[y, x] = new_pixel

            # Propagate the error
            error = old_pixel - new_pixel

            if x < width - 1:
                output[y, x + 1] += error * 7/16
            if y < height - 1:
                if x > 0:
                    output[y + 1, x - 1] += error * 3/16
                output[y + 1, x] += error * 5/16
                if x < width - 1:
                    output[y + 1, x + 1] += error * 1/16

    return output.astype(np.uint8)


def ordered_dithering(img: np.ndarray, levels: int = 2, threshold: int = 128) -> np.ndarray:
    """Apply ordered dithering using a Bayer matrix."""
    # 4x4 Bayer matrix
    bayer_matrix = np.array([
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ]) / 16 * 255

    height, width = img.shape
    output = img.copy()

    # Define the quantization function based on levels
    if levels == 2:
        def quantize(val, threshold_val):
            return 255 if val > threshold_val else 0
    else:
        step = 255 / (levels - 1)
        def quantize(val, threshold_val):
            # Apply threshold-based adjustment before quantizing
            adjusted_val = val + (val - threshold_val) / 2
            return round(round(adjusted_val / step) * step)

    for y in range(height):
        for x in range(width):
            # Get the threshold from the Bayer matrix
            threshold_val = bayer_matrix[y % 4, x % 4]
            output[y, x] = quantize(img[y, x], threshold_val)

    return output


def dither_image(
    input_path: str,
    output_path: str,
    method: str = "floyd-steinberg",
    levels: int = 2,
    threshold: int = 128
) -> None:
    """Dither an image and save the result."""
    # Open and convert to grayscale
    img = Image.open(input_path).convert("L")
    img_array = np.array(img)

    # Apply dithering
    if method == "floyd-steinberg":
        dithered = floyd_steinberg_dithering(img_array, levels, threshold)
    else:  # ordered
        dithered = ordered_dithering(img_array, levels, threshold)

    # Save the result
    dithered_img = Image.fromarray(dithered)
    dithered_img.save(output_path)
    print(f"Dithered image saved to {output_path}")


def main() -> None:
    args = parse_args()

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dither_image(
        args.input,
        str(output_path),
        args.method,
        args.levels,
        args.threshold
    )


if __name__ == "__main__":
    main()
