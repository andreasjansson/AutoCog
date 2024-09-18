from pathlib import Path
import sys
import re
import click
import os
import subprocess
import requests
from packaging import version
from pypi_simple import errors as pypi_errors
from pypi_simple import PyPISimple

from .ai import AI
from . import prompts
from .prompts import (
    COG_DOCS,
    PREDICT_DOCS,
    file_start,
    file_end,
    COMMAND_START,
    COMMAND_END,
    ERROR_COG_PREDICT,
    ERROR_PREDICT_PY,
    ERROR_COG_YAML
)
from .retry import retry
from .testdata import create_empty_file


def truncate_error(error, max_length=10000):
    return error[:max_length]


def order_paths(
    ai: AI, repo_path: Path, readme_contents: str | None = None
) -> list[Path]:
    paths = find_python_files(repo_path)
    if len(paths) == 0:
        raise ValueError(f"{repo_path} has no Python files")

    print("Ordering files based on importance...", file=sys.stderr)

    if readme_contents is None:
        _, readme_contents = load_readme_contents(repo_path)

    content = ai.call(prompts.order_paths(paths=paths, readme_contents=readme_contents))

    ordered_paths = [Path(p) for p in content.strip().splitlines()]
    
    for i, path in enumerate(ordered_paths):
        ordered_paths[i] = repo_path / path

    if set(ordered_paths) - set(paths):
        raise ValueError("Failed to order paths")

    return ordered_paths


def pull_docs():
    base_dir = os.path.dirname(__file__)
    prompts_dir = os.path.join(base_dir, "prompts")

    cog_docs = requests.get(COG_DOCS)
    if cog_docs.status_code == 200:
        print("Successfully pulled down documentation for cog.yaml")
        with open(os.path.join(prompts_dir, "cog_yaml_docs.tpl"), 'wb') as f:
            f.write(cog_docs.content)
    else:
        print("Failed to download cog.yaml documentation")

    predict_docs = requests.get(PREDICT_DOCS)
    if predict_docs.status_code == 200:
        print("Successfully pulled down documentation for predict.py")
        with open(os.path.join(prompts_dir, "cog_python_docs.tpl"), 'wb') as f:
            f.write(predict_docs.content)
    else:
        print("Failed to download predict.py documentation")


def load_readme_contents(repo_path: Path) -> tuple[str, str] | tuple[None, None]:
    readme_filenames = ["README.md", "readme.md", "README.txt", "readme.txt", "README"]
    for filename in readme_filenames:
        readme_path = repo_path / filename
        if readme_path.exists():
            return filename, readme_path.read_text()
    return None, None


def get_packages_info(ai: AI, repo_path: Path):
    cog_yaml_path = repo_path / "cog.yaml"
    if cog_yaml_path.exists():
        cog_yaml = cog_yaml_path.read_text()
    else:
        cog_yaml = None
    content = ai.call(prompts.get_packages(cog_contents=cog_yaml))

    # Initialize PyPI client
    client = PyPISimple()
    # Get package information
    package_info = {}
    for package in content.strip().split('\n'):
        valid = True
        versions = set()
        if '==' not in package:
            # If no version is explicitly given, query PyPi
            try:
                packages_info = client.get_project_page(package).packages
                for p_info in packages_info:
                    versions.add(p_info.version)
            except pypi_errors.NoSuchProjectError:
                valid = False
        else:
            # If version is explicitly given
            package_version = package.split('==')[1]
            versions.add(package_version)
        if valid:
            package_info[package] = sorted(versions, key=version.parse)
    return package_info


@retry(3)
def generate_initial(
    ai: AI, repo_path: Path, paths: list[Path], tell: str | None
) -> tuple[str, str]:
    files = {}
    readme_filename, readme_contents = load_readme_contents(repo_path)
    if readme_filename:
        files[readme_filename] = readme_contents

    requirements_file = repo_path / "requirements.txt"
    if requirements_file.exists():
        files["requirements.txt"] = requirements_file.read_text()
        package_versions = None
    else:
        print("Getting package information...")
        package_versions = get_packages_info(ai, repo_path)

    poetry_file = repo_path / "pyproject.toml"
    if poetry_file.exists():
        files["pyproject.toml"] = poetry_file.read_text()

    for path in paths:
        files[path.name] = path.read_text()

    predict_py_path = repo_path / "predict.py"
    if predict_py_path.exists():
        predict_py = predict_py_path.read_text()
    else:
        predict_py = None
    cog_yaml_path = repo_path / "cog.yaml"
    if cog_yaml_path.exists():
        cog_yaml = cog_yaml_path.read_text()
    else:
        cog_yaml = None

    content = ai.call(
        prompts.generate_initial(
            files=files, tell=tell, predict_py=predict_py, cog_yaml=cog_yaml, package_versions=package_versions
        )
    )
    cog_yaml = file_from_gpt_response(content, "cog.yaml")
    predict_py = file_from_gpt_response(content, "predict.py")

    return cog_yaml, predict_py


def find_python_files(repo_path: Path) -> list[Path]:
    python_files = [path for path in repo_path.rglob("*.py")]
    return python_files


def file_from_gpt_response(content: str, filename: str) -> str:
    pattern = re.compile(
        rf"(?<={file_start(filename)})(?:\n```[a-z]*\n)?(.*?)(?:\n```\n)?(?={file_end(filename)})",
        re.MULTILINE | re.DOTALL,
    )
    matches = pattern.search(content)
    if not matches:
        raise ValueError(f"Failed to generate {filename}")
    return matches[1].strip()


def write_files(repo_path: Path, files: dict):
    for filename, content in files.items():
        file_path = repo_path / filename
        file_path.write_text(content)


def run_cog_predict(repo_path: Path, predict_command: str) -> tuple[bool, str]:
    print(predict_command, file=sys.stderr)

    proc = subprocess.Popen(
        predict_command, cwd=repo_path, stderr=subprocess.PIPE, shell=True
    )
    stderr = ""
    assert proc.stderr
    for line in proc.stderr:
        line = line.decode()
        sys.stderr.write(line)
        stderr += line

        if "Model setup failed" in line:
            proc.kill()
            break

    proc.wait()
    # cog predict will return 0 if the model fails internally
    if proc.returncode == 0 and "Traceback (most recent call last)" not in stderr:
        return True, stderr

    return False, stderr


def cog_predict_from_gpt_response(content: str) -> str:
    pattern = re.compile(
        rf"(?<={re.escape(COMMAND_START)}\n)([\s\S]*?)(?=\n{re.escape(COMMAND_END)})",
        re.MULTILINE | re.DOTALL,
    )
    matches = pattern.search(content)
    if not matches:
        raise ValueError(f"Failed to generate cog predict")
    return matches[1].strip()


def create_files_for_predict_command(repo_path: Path, predict_command: str) -> str:
    print("Parsing predict command...")
    predict_command = cog_predict_from_gpt_response(predict_command)
    file_inputs = re.findall(r"@([\w.]+)", predict_command)

    for filename in file_inputs:
        if not os.path.exists(filename):
            tmp_path = os.path.join("/tmp", os.path.basename(filename))
            predict_command = predict_command.replace("@" + filename, "@" + tmp_path)
            create_empty_file(repo_path, tmp_path)

    return predict_command


def parse_cog_predict_error(stderr: str, *, max_length=20000) -> str:
    if "Running prediction...\n" in stderr:
        error = stderr.split("Running prediction...\n")[1].split("panic: ")[0]
    else:
        error = stderr.split("panic: ")[0]

    return error[-max_length:]


@retry(5)
def diagnose_error(ai: AI, predict_command: str, error: str) -> str:
    print("Diagnosing source of error: ", file=sys.stderr)

    diagnose_text = ai.call(prompts.diagnose_error(predict_command=predict_command, error=truncate_error(error)))
    package_error = ai.call(prompts.package_error(predict_command=predict_command, error=truncate_error(error)))
    package_error = package_error == "True"

    if diagnose_text not in [ERROR_PREDICT_PY, ERROR_COG_PREDICT, ERROR_COG_YAML]:
        raise ValueError("Failed to diagnose error")
    return diagnose_text, package_error


@retry(5)
def fix_predict_py(ai: AI) -> str:
    text = ai.call(prompts.fix_predict_py)
    return file_from_gpt_response(text, "predict.py")


@retry(5)
def fix_cog_yaml(ai: AI) -> str:
    text = ai.call(prompts.fix_cog_yaml)
    return file_from_gpt_response(text, "cog.yaml")


def initialize_project(ai: AI, repo_path: Path):
    cog_yaml_path = repo_path / "cog.yaml"
    predict_py_path = repo_path / "predict.py"
    if cog_yaml_path.exists():
        cog_yaml_path.unlink()
    if predict_py_path.exists():
        predict_py_path.unlink()
    ai.clear_history()


@click.command()
@click.option(
    "-r",
    "--repo",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the ML repository (default is current directory)",
)
@click.option(
    "-a",
    "--ai-provider",
    default="openai",
    type=click.Choice(["anthropic", "openai"], case_sensitive=False),
    help="AI provider",
)
@click.option(
    "-k",
    "--api-key",
    default=None,
    help="API key for Anthropic/OpenAI (optional, defaults to the environment variable OPENAI_API_KEY or ANTHROPIC_API_KEY depending on --ai-provider)",
)
@click.option(
    "-n",
    "--attempts",
    default=5,
    type=int,
    help="Number of attempts to try to fix issues before giving up",
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
def autocog(
    repo: Path | None,
    ai_provider: str,
    api_key: str | None,
    attempts: int,
    predict_command: str | None,
    tell: str | None,
    initialize: bool,
):
    repo_path = repo or Path(os.getcwd())
    pull_docs()
    ai = AI(
        system_prompt=prompts.system,
        provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "autocog.chat",
    )

    if initialize:
        initialize_project(ai, repo_path)

    cog_yaml_exists = (repo_path / "cog.yaml").exists()
    predict_py_exists = (repo_path / "predict.py").exists()
    chat_history_exists = ai.chat_history_path.exists()

    if chat_history_exists and (not cog_yaml_exists or not predict_py_exists):
        raise ValueError(
            f"AutoCog is in a semi-initialized state in {repo_path}, because one of cog.yaml or predict.py have been deleted. Run `autocog --initialize` to re-initialize the project"
        )

    if chat_history_exists:
        ai.load_chat_history()
    else:
        paths = order_paths(ai, repo_path)
        cog_yaml, predict_py = generate_initial(ai, repo_path, paths=paths, tell=tell)
        (repo_path / "cog.yaml").write_text(cog_yaml)
        (repo_path / "predict.py").write_text(predict_py)

    if not predict_command:
        predict_command = ai.call(prompts.cog_predict)

    predict_command = create_files_for_predict_command(repo_path, predict_command)
    for attempt in range(attempts):
        print("Predict command")
        print(predict_command)
        success, stderr = run_cog_predict(repo_path, predict_command)
        if success:
            return

        if attempt == attempts - 1:
            print(f"Failed after {attempts} attempts, giving up :'(")
            sys.exit(1)

        print(
            f"Attempt {attempt + 1}/{attempts} failed, trying to fix...",
            file=sys.stderr,
        )

        error = parse_cog_predict_error(stderr)
        error_source, package_error = diagnose_error(ai, predict_command, error)
        print("Error source")
        print(error_source)
        print("Package error")
        print(package_error)
        if package_error:
            get_packages_info(ai, repo_path)

        if error_source == ERROR_PREDICT_PY:
            predict_py = fix_predict_py(ai)
            (repo_path / "predict.py").write_text(predict_py)
        elif error_source == ERROR_COG_YAML:
            cog_yaml = fix_cog_yaml(ai)
            (repo_path / "cog.yaml").write_text(cog_yaml)
        elif error_source == ERROR_COG_PREDICT:
            predict_command = ai.call(prompts.cog_predict)
            predict_command = create_files_for_predict_command(
                repo_path, predict_command
            )


if __name__ == "__main__":
    autocog()
