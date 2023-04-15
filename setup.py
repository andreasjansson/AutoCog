from setuptools import setup, find_packages

setup(
    name="autocog",
    version="0.0.1",
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
