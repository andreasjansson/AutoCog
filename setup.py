from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()
long_description = long_description.replace(
    "![Screen recording](https://github.com/andreasjansson/AutoCog/raw/main/assets/screen-recording.gif)\n",
    "",
)

setup(
    name="autocog",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="0.0.11",
    url="https://github.com/andreasjansson/AutoCog",
    packages=find_packages(),
    install_requires=[
        "click==8.2.0",
        "anthropic==0.51.0",
        "jinja2==3.1.6",
        "tavily-python==0.7.2",
        "humanize==4.12.3",
        "replicate==1.0.6",
        "toololo==0.1.2",
        "PyGithub==2.6.1",
    ],
    entry_points={
        "console_scripts": [
            "autocog = autocog.autocog:autocog",
        ],
    },
    package_data={
        "autocog": [
            "prompts/*.tpl",
            "assets/**/*",
        ],
    },
)
