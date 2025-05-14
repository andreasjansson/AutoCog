from cog import BasePredictor, Input, Path
import numpy as np
from PIL import Image
import os
from dither import dither_image

class Predictor(BasePredictor):
    def setup(self):
        """
        This model doesn't require any setup as it's a lightweight image processing tool
        that applies dithering techniques to convert images to grayscale with reduced color palettes.
        """
        # No setup needed - dithering algorithms don't require pre-loaded models

    def predict(
        self,
        image: Path = Input(
            description="Input image to apply dithering to. Most common image formats are supported."
        ),
        method: str = Input(
            description="Dithering method to use. Floyd-Steinberg produces smoother results with error diffusion, while Ordered uses a fixed pattern.",
            choices=["floyd-steinberg", "ordered"],
            default="floyd-steinberg"
        ),
        levels: int = Input(
            description="Number of gray levels to use. 2 creates a binary black and white image, higher values allow more shades of gray.",
            default=2,
            ge=2,
            le=16
        ),
        threshold: int = Input(
            description="Threshold value for quantization (0-255). Only relevant for binary (2-level) output. Lower values produce darker images.",
            default=128,
            ge=0,
            le=255
        )
    ) -> Path:
        """
        Apply dithering to the input image.
        Dithering creates the illusion of more colors by using patterns of dots,
        which can create interesting visual effects or reduce file sizes.
        """
        try:
            input_path = str(image)
            output_path = "/tmp/output.jpg"
            
            dither_image(
                input_path=input_path,
                output_path=output_path,
                method=method,
                levels=levels,
                threshold=threshold
            )
            
            # Ensure the output file was created
            if not os.path.exists(output_path):
                raise Exception("Failed to generate dithered image")
                
            return Path(output_path)
        except Exception as e:
            raise Exception(f"Error during image dithering: {str(e)}")