Below is an example cog.yaml:

```
build:
  gpu: true
  system_packages:
    - "libgl1-mesa-glx"
    - "libglib2.0-0"
  python_version: "3.8"
  python_requirements: "cog_requirements.txt"
predict: "predict.py:Predictor"
```

And the associated cog_requirements.txt:

```
torch==1.8.1
```

And an example predict.py:

from cog import BasePredictor, Input, Path
import torch
from model_utils import preprocess, post_process

class Predictor(BasePredictor):
    def setup(self):
        """Load the model into memory to make running multiple predictions efficient"""
        self.model = torch.load("./weights.pth")

    # The arguments and types the model takes as input
    def predict(self,
          image: Path = Input(description="Grayscale input image")
    ) -> Path:
        """Run a single prediction on the model"""
        processed_image = preprocess(image)
        output = self.model(processed_image)
        return postprocess(output)
