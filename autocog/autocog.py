from urllib.parse import urlparse
from pathlib import Path
import click
import os
import subprocess
import anthropic
import toololo
from toololo import log
from toololo.types import ToolResult

from . import prompts
from .tools import fs, cog, pypi, tavily, media


def initialize_project(repo_path: Path):
    cog_yaml_path = repo_path / "cog.yaml"
    predict_py_path = repo_path / "predict.py"
    if cog_yaml_path.exists():
        cog_yaml_path.unlink()
    if predict_py_path.exists():
        predict_py_path.unlink()


def clone_github_repo(repo_url: str) -> Path:
    """Clone a GitHub repository and return the path to the cloned directory."""
    parsed_url = urlparse(repo_url)
    repo_name = parsed_url.path.strip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    repo_dir = Path.cwd() / repo_name

    if not repo_dir.exists():
        subprocess.run(["git", "clone", repo_url, str(repo_dir)], check=True)

    return repo_dir


class RepoPath(click.ParamType):
    name = "repo_path"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        # Check if it's a URL
        if value.startswith(("http://", "https://", "git://")):
            try:
                return clone_github_repo(value)
            except Exception as e:
                self.fail(f"Failed to clone repository: {str(e)}", param, ctx)

        # If it's a local path
        path = Path(value)
        if not path.exists():
            self.fail(f"Directory {value} does not exist", param, ctx)
        if not path.is_dir():
            self.fail(f"{value} is not a directory", param, ctx)

        return path


@click.command()
@click.option(
    "-r",
    "--repo",
    default=None,
    type=RepoPath(),
    help="Path to the ML repository (default is current directory). If --repo is a URL to a github repository, that repository will be cloned to a subdirectory of the current directory.",
)
@click.option(
    "-n",
    "--max-iterations",
    default=50,
    type=int,
    help="Number of agentic iterations to run before giving up",
)
@click.option(
    "-p",
    "--predict-command",
    help="Initial predict command. If not specified, AutoCog will generate one",
)
@click.option(
    "-t",
    "--tell",
    help="Tell AutoCog to ",
)
@click.option(
    "-i",
    "--initialize",
    help="Initialize project by removing any existing predict.py and cog.yaml files. If omitted, AutoCog will continue from the current state of the repository",
    is_flag=True,
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (can be used multiple times: -v, -vv, -vvv)",
)
def autocog(
    repo: Path | None,
    max_iterations: int,
    predict_command: str | None,
    tell: str | None,
    initialize: bool,
    verbose: int,
):
    if verbose == 0:
        log_level = log.INFO
    elif verbose == 1:
        log_level = log.VERBOSE1
    elif verbose == 2:
        log_level = log.VERBOSE2
    else:  # verbose >= 3
        log_level = log.VERBOSE3

    log.set_verbosity(log_level)

    if repo:
        repo_path = repo
        os.chdir(repo_path)
    else:
        repo_path = Path.cwd()

    if initialize:
        initialize_project(repo_path)

    log.info(f"Running autocog in {repo_path}")

    client = anthropic.Client()

    tools = [
        fs.list_files_recursively,
        fs.read_file,
        fs.read_files,
        cog.write_files,
        cog.predict,
        pypi.package_versions,
        tavily.web_search,
        tavily.web_extract,
        media.describe_image,
        media.transcribe_speech,
        media.describe_audio,
    ]

    prompt = "Convert the repo in the current working directory to Cog by writing a predict.py and cog.yaml file and iterating until it works."

    if (repo_path / "cog.yaml").exists() or (repo_path / "predict.py").exists():
        prompt += "\nNote that there is an existing cog.yaml/predict.py already."

    if tell:
        prompt += f"\n[Important] Follow these additional instructions: {tell}"

    if predict_command:
        prompt += f"When running `cog predict` to test the Cog model, use this cog predict command: `{predict_command}`"

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    for output in toololo.run(
        client=client,
        messages=messages,
        model="claude-3-7-sonnet-latest",
        tools=tools,
        system_prompt=prompts.make_system_prompt(),
        max_iterations=max_iterations,
        # history_file=Path("autocog-history.jsonlines"),
    ):
        if isinstance(output, ToolResult):
            log.v(str(output) + "\n\n")
        else:
            log.info(truncate_string(str(output), 250) + "\n\n")


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)
    return text[:truncate_at] + suffix


if __name__ == "__main__":
    autocog()
