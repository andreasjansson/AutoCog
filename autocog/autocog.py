from pathlib import Path
import sys
import os
import click
from .agents import (
    PathOrderingAgent,
    DocsPullingAgent,
    PackageInfoAgent,
    CogGenerationAgent,
    PredictGenerationAgent,
    ErrorDiagnosisAgent,
    CogFixingAgent,
    PredictFixingAgent,
    CogPredictAgent
)
from . import prompts


def initialize_project(repo_path: Path):
    """
    Initializes the project by removing cog.yaml, predict.py, and clearing the chat history for all agents.

    :param repo_path: Path to the project repository.
    """
    # Define the paths for cog.yaml and predict.py
    cog_yaml_path = repo_path / "cog.yaml"
    predict_py_path = repo_path / "predict.py"
    
    # Remove cog.yaml and predict.py if they exist
    if cog_yaml_path.exists():
        cog_yaml_path.unlink()
        print(f"Removed {cog_yaml_path}")
    
    if predict_py_path.exists():
        predict_py_path.unlink()
        print(f"Removed {predict_py_path}")

    # Define the chat history files for each agent
    chat_history_files = [
        repo_path / "path_ordering.chat",
        repo_path / "package_info.chat",
        repo_path / "cog_generation.chat",
        repo_path / "predict_generation.chat",
        repo_path / "error_diagnosis.chat",
        repo_path / "cog_fixing.chat",
        repo_path / "predict_fixing.chat",
        repo_path / "cog_predict.chat"
    ]

    # Remove the chat history files if they exist
    for history_file in chat_history_files:
        if history_file.exists():
            history_file.unlink()
            print(f"Cleared chat history: {history_file}")


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
    
    # 1. Initialize project if specified
    if initialize:
        initialize_project(repo_path)

    # 2. Instantiate the agents with separate system prompts and chat history paths
    path_ordering_agent = PathOrderingAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "path_ordering.chat"
    )

    package_agent = PackageInfoAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "package_info.chat"
    )

    cog_generation_agent = CogGenerationAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "cog_generation.chat"
    )
    
    predict_generation_agent = PredictGenerationAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "predict_generation.chat"
    )

    error_diagnosis_agent = ErrorDiagnosisAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "error_diagnosis.chat"
    )

    cog_fixing_agent = CogFixingAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "cog_fixing.chat"
    )
    
    predict_fixing_agent = PredictFixingAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "predict_fixing.chat"
    )

    cog_predict_agent = CogPredictAgent(
        ai_provider=ai_provider,
        api_key=api_key,
        chat_history_path=repo_path / "cog_predict.chat"
    )

    # 3. Use DocsPullingAgent (no AI required) to pull documentation
    docs_agent = DocsPullingAgent(prompts_dir=repo_path / "prompts")
    docs_agent.pull_docs()

    if initialize: 
        initialize_project(repo_path)

    # 4. Check for the existence of cog.yaml, predict.py, and chat history
    cog_yaml_exists = (repo_path / "cog.yaml").exists()
    predict_py_exists = (repo_path / "predict.py").exists()

    # Check if project is in a semi-initialized state
    if not cog_yaml_exists or not predict_py_exists:
        if any(ai.chat_history_path.exists() for ai in [
            path_ordering_agent.ai, package_agent.ai, cog_generation_agent.ai, 
            predict_generation_agent.ai, error_diagnosis_agent.ai, 
            cog_fixing_agent.ai, predict_fixing_agent.ai, cog_predict_agent.ai
        ]):
            raise ValueError(
                f"AutoCog is in a semi-initialized state in {repo_path}, because one of cog.yaml or predict.py have been deleted. Run `autocog --initialize` to re-initialize the project"
            )

    # 5. Get package information from PackageInfoAgent
    paths = path_ordering_agent.order_paths(repo_path)
    packages = package_agent.get_imported_packages(paths)
    package_versions = package_agent.get_packages_info(packages, repo_path)
    
    # 6. Generate initial `cog.yaml` and `predict.py` if necessary
    if not predict_py_exists:
        predict_py = predict_generation_agent.generate_predict_py(repo_path, predict_py=None, tell=tell)
        (repo_path / "predict.py").write_text(predict_py)
    
    if not cog_yaml_exists:
        cog_yaml = cog_generation_agent.generate_cog_yaml(repo_path, predict_py=predict_py, cog_yaml=None, package_versions=package_versions, tell=tell)
        (repo_path / "cog.yaml").write_text(cog_yaml)

    # 7. Generate or use the provided predict command
    if not predict_command:
        predict_command = cog_predict_agent.generate_predict_command(predict_py)

    # 8. Attempt to run the prediction command and fix errors if necessary
    for attempt in range(attempts):
        print("Predict command:", predict_command)
        success, stderr = cog_predict_agent.run_cog_predict(repo_path, predict_command)

        if success:
            return

        if attempt == attempts - 1:
            print(f"Failed after {attempts} attempts, giving up :'(")
            sys.exit(1)

        print(f"Attempt {attempt + 1}/{attempts} failed, trying to fix...")

        error = stderr.split("Traceback (most recent call last)")[-1] if "Traceback" in stderr else stderr
        error_source, package_error = error_diagnosis_agent.diagnose_error(predict_command, error)

        print("Error source:", error_source)
        print("Package error:", package_error)

        if package_error:
            package_agent.get_packages_info(repo_path)

        if error_source == "predict.py":
            predict_py = predict_fixing_agent.fix_predict_py()
            (repo_path / "predict.py").write_text(predict_py)
        elif error_source == "cog.yaml":
            cog_yaml = cog_fixing_agent.fix_cog_yaml()
            (repo_path / "cog.yaml").write_text(cog_yaml)
        elif error_source == "cog_predict":
            predict_command = cog_predict_agent.generate_predict_command()


if __name__ == "__main__":
    autocog()

