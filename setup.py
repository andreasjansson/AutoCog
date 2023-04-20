from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()
long_description = long_description.replace("![Screen recording](https://github.com/andreasjansson/AutoCog/raw/main/assets/screen-recording.gif)\n", "")

setup(
    name="autocog",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="0.0.4",
    url="https://github.com/andreasjansson/AutoCog",
    packages=find_packages(),
    install_requires=[
        "openai",
        "click",
        "Pillow",
    ],
    entry_points={
        "console_scripts": [
            "autocog = autocog.autocog:autocog",
        ],
    },
)
