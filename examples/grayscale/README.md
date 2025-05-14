# Image Dithering Tool

A simple Python tool to convert images to grayscale dithered versions.

## Description

This tool applies dithering techniques to images, converting them to grayscale with reduced color palettes. Dithering creates the illusion of more colors by using patterns of dots, which can create interesting visual effects or reduce file sizes while maintaining visual quality.

## Features

- Convert any image to grayscale
- Apply Floyd-Steinberg dithering (error diffusion)
- Apply Ordered dithering (Bayer matrix)
- Adjust number of gray levels
- Set custom threshold for binary output

## Requirements

- Python 3.6+
- Pillow (PIL fork)
- NumPy

## Installation

```bash
pip install pillow numpy
```

## Usage

Basic usage:

```bash
python dither.py input.jpg output.jpg
```

Advanced options:

```bash
python dither.py input.jpg output.jpg --method floyd-steinberg --levels 2 --threshold 128
```

### Arguments

- `input`: Path to the input image
- `output`: Path where the dithered image will be saved
- `--method`: Dithering method to use (options: "floyd-steinberg", "ordered")
- `--levels`: Number of gray levels (2 for binary black and white)
- `--threshold`: Threshold value for quantization (0-255)

## Examples

### Binary Floyd-Steinberg Dithering
```bash
python dither.py photo.jpg dithered_fs.jpg --method floyd-steinberg --levels 2
```

### Ordered Dithering with 4 Gray Levels
```bash
python dither.py photo.jpg dithered_ordered.jpg --method ordered --levels 4
```

## License

MIT
