import traceback
from pathlib import Path
import click
import os
import anthropic
import toololo
from toololo import log
from toololo.types import ToolResult

from . import prompts
from . import fs, cog, pypi, tavily, media
from .replicate_model import ReplicateModel
from .webhook import WebhookSender
from . import git


def initialize_project(repo_path: Path):
    for path in [
        repo_path / "cog.yaml",
        repo_path / "predict.py",
        repo_path / "cog_requirements.txt",
    ]:
        if path.exists():
            path.unlink()


class RepoPath(click.ParamType):
    name = "repo_path"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        # Check if it's a URL
        if value.startswith(("http://", "https://", "git://")):
            try:
                return git.clone(value)
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
@click.option("--github-app-id", type=int, help="GitHub App ID.")
@click.option(
    "--github-app-key-path", type=Path, help="Path to GitHub App private key file."
)
@click.option("--github-app-key", help="GitHub App private key content.")
@click.option("--github-installation-id", type=int, help="GitHub App installation ID.")
@click.option(
    "--push-repo",
    help="Name for the GitHub repository to create in the format <owner>/<name>. If omitted, no github repo is created",
)
@click.option(
    "--model",
    "model_name",
    help="Name for the Replicate model to create in the format <owner>/<name>. If omitted, no Replicate model is pushed",
)
@click.option(
    "--model-hardware",
    help="Hardware for the Replicate model. Required if --model is specified",
)
@click.option("--replicate-cog-token", help="Token to push Cog models to Replicate")
@click.option("--webhook-uri", help="URI where webhook notifications will be sent.")
def autocog(
    repo: Path | None,
    max_iterations: int,
    predict_command: str | None,
    tell: str | None,
    initialize: bool,
    verbose: int,
    github_app_id: int | None,
    github_app_key_path: Path | None,
    github_app_key: str | None,
    github_installation_id: int | None,
    push_repo: str | None,
    model_name: str | None,
    model_hardware: str | None,
    replicate_cog_token: str | None,
    webhook_uri: str | None,
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

    if model_name:
        assert model_hardware, "--model-hardware is required if --model is specified"
        replicate_model = ReplicateModel(
            model_name, model_hardware, replicate_cog_token
        )
    else:
        replicate_model = None

    cog.install_cog()

    if initialize:
        initialize_project(repo_path)

    if push_repo and git.is_dirty():
        git.commit("Before AutoCog")

    log.info(f"Running autocog in {repo_path}")

    # Initialize webhook sender if URI is provided
    webhook_sender = None
    if webhook_uri:
        webhook_sender = WebhookSender(webhook_uri=webhook_uri)
        webhook_sender.send("starting")

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
    if replicate_model:
        tools += [replicate_model.cog_push, replicate_model.predict]

    prompt = "Convert the repo in the current working directory to Cog by writing a predict.py and cog.yaml file and iterating until it works."

    if (repo_path / "cog.yaml").exists() or (repo_path / "predict.py").exists():
        prompt += "\nNote that there is an existing cog.yaml/predict.py already."

    if tell:
        prompt += f"\n[IMPORTANT] You must follow these additional overriding instructions: {tell}"

    if predict_command:
        prompt += f"When running `cog predict` to test the Cog model, use this cog predict command: `{predict_command}`"

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    final_error = None

    try:
        for output in toololo.run(
            client=client,
            messages=messages,
            model="claude-3-7-sonnet-latest",
            tools=tools,
            system_prompt=prompts.make_system_prompt(
                push_to_replicate=replicate_model is not None
            ),
            max_iterations=max_iterations,
        ):
            if webhook_sender:
                webhook_sender.send("output", output)

            if isinstance(output, ToolResult):
                log.v(str(output) + "\n\n")
            else:
                log.info(truncate_string(str(output), 250) + "\n\n")

    except Exception as e:
        final_error = str(e)
        log.error(f"Error during autocog execution: {final_error}")
        if webhook_sender:
            webhook_sender.send("error", traceback.format_exc())
        return

    if push_repo:
        log.info("Prediction was successful! Pushing to GitHub...")
        git.add(
            [
                "predict.py",
                "cog.yaml",
                "cog_requirements.txt",
                ".gitignore",
                ".dockerignore",
            ]
        )
        if git.is_dirty():
            git.commit("AutoCog added predict.py and cog.yaml")
        repo_url = git.push(
            repo_name=push_repo,
            auth=git.GitHubAuth(
                app_id=github_app_id,
                app_key=github_app_key,
                app_key_path=github_app_key_path,
                installation_id=github_installation_id,
            ),
        )
        log.info(f"Successfully pushed to GitHub: {repo_url}")

    if webhook_sender:
        webhook_sender.send("complete")


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)
    return text[:truncate_at] + suffix


if __name__ == "__main__":
    autocog()
