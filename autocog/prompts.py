import subprocess
import requests
import os
from pathlib import Path
import humanize
from jinja2 import Environment, FileSystemLoader

COG_GETTING_STARTED_DOCS_URL = "https://raw.githubusercontent.com/replicate/cog/refs/heads/main/docs/getting-started-own-model.md"
COG_DOCS_URL = "https://raw.githubusercontent.com/replicate/cog/main/docs/yaml.md"
PREDICT_DOCS_URL = "https://raw.githubusercontent.com/replicate/cog/main/docs/python.md"
TORCH_COMPATIBILITY_URL = "https://raw.githubusercontent.com/replicate/cog/refs/heads/main/pkg/config/torch_compatibility_matrix.json"
#TORCH_COMPATIBILITY_URL = "https://raw.githubusercontent.com/replicate/cog/refs/heads/torch-2.7.0/pkg/config/torch_compatibility_matrix.json"


def prompts_dir() -> Path:
    base_dir = Path(__file__).parent
    return base_dir / "prompts"


def assets_dir() -> Path:
    base_dir = Path(__file__).parent
    return base_dir / "assets"


def download(url, template_path):
    resp = requests.get(url)
    resp.raise_for_status()
    (prompts_dir() / template_path).write_bytes(resp.content)


def cog_predict_help() -> str:
    result = subprocess.run(
        ["cog", "predict", "--help"], capture_output=True, text=True, check=True
    )
    return result.stdout


def generate_docs():
    download(COG_GETTING_STARTED_DOCS_URL, "cog_getting_started_docs.tpl")
    download(COG_DOCS_URL, "cog_yaml_docs.tpl")
    download(PREDICT_DOCS_URL, "cog_python_docs.tpl")
    download(TORCH_COMPATIBILITY_URL, "torch_compatibility.tpl")
    (prompts_dir() / "cog_predict_help.tpl").write_text(cog_predict_help())


def list_assets() -> list[tuple[str, str]]:
    """
    Recursively iterate over the files in assets_dir() and return a list of file names
    and human-readable file sizes (e.g. "11MB"), sorted by file name alphabetically.
    """
    result = []
    assets_path = assets_dir()

    # Check if assets directory exists
    if not assets_path.exists():
        return []

    # Recursively iterate through all files
    for path in sorted(assets_path.glob("**/*")):
        if path.is_file():
            # Get file size in bytes and convert to human-readable format
            size_bytes = path.stat().st_size
            size_str = humanize.naturalsize(size_bytes)

            result.append((str(path), size_str))

    return result


def render(template_name, **kwargs):
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    prompts_dir = current_dir / "prompts"
    env = Environment(
        loader=FileSystemLoader(prompts_dir),
    )
    template = env.get_template(template_name + ".tpl")

    kwargs["assets"] = list_assets()

    return template.render(**kwargs)


def make_system_prompt():
    generate_docs()
    return render("system")
