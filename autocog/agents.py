from pathlib import Path
import sys
import os
import ast
import subprocess
import requests
import importlib
import re
from packaging import version
from pypi_simple import errors as pypi_errors
from pypi_simple import PyPISimple

from .ai import AI
from .retry import retry
from .testdata import create_empty_file
from . import prompts


class BaseAgent:
    def __init__(self, ai_provider: str, api_key: str, system_prompt: str, chat_history_path: Path):
        """
        Base class for all agents that interact with an AI system.

        :param ai_provider: The provider (e.g., 'openai', 'anthropic')
        :param api_key: The API key for the AI provider
        :param system_prompt: The system prompt for this agent
        :param chat_history_path: The path where this agent's chat history is stored
        """
        self.ai = AI(system_prompt=system_prompt, provider=ai_provider, api_key=api_key, chat_history_path=chat_history_path)
        self.system_prompt = system_prompt
        self.chat_history_path = chat_history_path


class PathOrderingAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for ordering paths of Python files based on importance.
        """
        super().__init__(ai_provider, api_key, prompts.order_paths_system, chat_history_path)

    def order_paths(self, repo_path: Path, readme_contents: str = None) -> list[Path]:
        paths = self._find_python_files(repo_path)
        if len(paths) == 0:
            raise ValueError(f"{repo_path} has no Python files")

        if readme_contents is None:
            _, readme_contents = self._load_readme_contents(repo_path)

        content = self.ai.call(prompts.order_paths(paths=paths, readme_contents=readme_contents))
        ordered_paths = [repo_path / Path(p) for p in content.strip().splitlines()]

        if set(ordered_paths) - set(paths):
            raise ValueError("Failed to order paths")

        return ordered_paths

    def _find_python_files(self, repo_path: Path) -> list[Path]:
        return [path for path in repo_path.rglob("*.py")]

    def _load_readme_contents(self, repo_path: Path) -> tuple[str, str] | tuple[None, None]:
        readme_filenames = ["README.md", "readme.md", "README.txt", "readme.txt", "README"]
        for filename in readme_filenames:
            readme_path = repo_path / filename
            if readme_path.exists():
                return filename, readme_path.read_text()
        return None, None


class DocsPullingAgent:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir

    def pull_docs(self):
        print("Pulling documentation...")
        base_dir = os.path.dirname(__file__)
        prompts_dir = os.path.join(base_dir, "prompts")

        self._fetch_and_save(prompts.COG_DOCS, os.path.join(prompts_dir, "cog_yaml_docs.tpl"))
        self._fetch_and_save(prompts.PREDICT_DOCS, os.path.join(prompts_dir, "cog_python_docs.tpl"))

    def _fetch_and_save(self, url, save_path):
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Successfully pulled down documentation from {url}")
        else:
            print(f"Failed to download documentation from {url}")


class PackageInfoAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for gathering information about required packages from PyPI.
        """
        super().__init__(ai_provider, api_key, prompts.package_info_system, chat_history_path)

    def get_packages_info(self, packages: list[str], repo_path: Path):
        print("Getting package info...")
        cog_yaml_path = repo_path / "cog.yaml"
        cog_yaml = cog_yaml_path.read_text() if cog_yaml_path.exists() else None
        content = self.ai.call(prompts.get_packages(packages=packages, cog_contents=cog_yaml))

        package_info = {}
        client = PyPISimple()
        for package in content.strip().split('\n'):
            versions = self._get_package_versions(client, package)
            if versions:
                package_info[package] = sorted(versions, key=version.parse)

        return package_info

    def _get_package_versions(self, client, package):
        versions = set()
        if '==' not in package:
            try:
                packages_info = client.get_project_page(package).packages
                for p_info in packages_info:
                    versions.add(p_info.version)
            except pypi_errors.NoSuchProjectError:
                return None
        else:
            versions.add(package.split('==')[1])
        return versions

    def get_imported_packages(self, ordered_paths: list[Path]) -> list[str]:
        """
        Reads the import statements from the most important Python files and returns a list of non-standard library packages.

        :param ordered_paths: List of ordered paths to the most important Python files.
        :return: List of non-standard Python packages used in the project.
        """
        imported_packages = set()

        # Iterate over each important file and extract the imports
        for file_path in ordered_paths:
            if file_path.suffix == '.py':  # Ensure it's a Python file
                imports = self._extract_imports_from_file(file_path)
                imported_packages.update(imports)

        # Filter out standard library packages
        non_standard_packages = self._filter_standard_libraries(imported_packages)

        return sorted(non_standard_packages)

    def _extract_imports_from_file(self, file_path: Path) -> set[str]:
        """
        Extracts import statements from a Python file.

        :param file_path: Path to the Python file.
        :return: Set of imported modules/packages.
        """
        with file_path.open('r', encoding='utf-8') as file:
            tree = ast.parse(file.read(), filename=str(file_path))

        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])  # Get the root module/package
            elif isinstance(node, ast.ImportFrom):
                if node.module:  # Handle "from <module> import <name>"
                    imports.add(node.module.split('.')[0])

        return imports

    def _filter_standard_libraries(self, packages: set[str]) -> list[str]:
        """
        Filters out the standard library packages from the set of imported packages.

        :param packages: Set of package names.
        :return: List of non-standard library package names.
        """
        non_standard_packages = []

        for package in packages:
            if not self._is_standard_library(package):
                non_standard_packages.append(package)

        return non_standard_packages

    def _is_standard_library(self, package: str) -> bool:
        """
        Checks if a given package is part of the Python standard library.

        :param package: Package name to check.
        :return: True if the package is a standard library package, False otherwise.
        """
        # Try to locate the package using importlib to see if it's part of the standard library
        spec = importlib.util.find_spec(package)
        if spec is None:
            return False
        # If the package exists, check if it's a built-in module
        return package in sys.builtin_module_names


class CogGenerationAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for generating the cog.yaml file.
        """
        super().__init__(ai_provider, api_key, prompts.cog_generation_system, chat_history_path)

    def generate_cog_yaml(self, repo_path: Path, predict_py: str | None, cog_yaml: str | None, package_versions: dict | None, tell: str | None = None) -> str:
        """
        Generates cog.yaml file based on the current project setup.
        
        :param repo_path: Path to the project repository.
        :param tell: Optional additional information for generating the file.
        :return: The cog.yaml content.
        """
        print("Generating cog.yaml...")
        files = self._gather_project_files(repo_path)
        # Call the AI to generate the cog.yaml file
        content = self.ai.call(prompts.generate_cog_yaml(files=files, predict_py=predict_py, cog_yaml=cog_yaml, package_versions=package_versions, tell=tell))

        # Extract the cog.yaml from the response
        cog_yaml = self._extract_file_from_gpt_response(content, "cog.yaml")
        return cog_yaml

    def _gather_project_files(self, repo_path: Path) -> dict[str, str]:
        """
        Gathers all relevant project files (e.g., README, requirements) that might help generate cog.yaml.
        
        :param repo_path: Path to the repository.
        :return: Dictionary of file names and their contents.
        """
        files = {}
        # Gather README, requirements.txt, pyproject.toml if they exist
        for filename in ["README.md", "requirements.txt", "pyproject.toml"]:
            file_path = repo_path / filename
            if file_path.exists():
                files[filename] = file_path.read_text()
        return files

    def _extract_file_from_gpt_response(self, content: str, filename: str) -> str:
        """
        Extracts the content of a specific file from the AI's response.
        
        :param content: The full response from the AI.
        :param filename: The name of the file to extract (e.g., cog.yaml).
        :return: The extracted content of the file.
        """
        pattern = re.compile(rf"(?<=-- FILE_START: {filename})(.*?)(?=-- FILE_END: {filename})", re.DOTALL)
        match = pattern.search(content)
        if not match:
            raise ValueError(f"Failed to generate {filename}")
        return match.group(1).strip()


class PredictGenerationAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for generating the predict.py file.
        """
        super().__init__(ai_provider, api_key, prompts.predict_generation_system, chat_history_path)

    def generate_predict_py(self, repo_path: Path, predict_py: str | None, tell: str | None = None) -> str:
        """
        Generates predict.py file based on the current project setup.
        
        :param repo_path: Path to the project repository.
        :param tell: Optional additional information for generating the file.
        :return: The predict.py content.
        """
        print("Generating predict.py...")
        files = self._gather_project_files(repo_path)
        # Call the AI to generate the predict.py file
        content = self.ai.call(prompts.generate_predict_py(files=files, predict_py=predict_py, tell=tell))

        # Extract the predict.py from the response
        predict_py = self._extract_file_from_gpt_response(content, "predict.py")
        return predict_py

    def _gather_project_files(self, repo_path: Path) -> dict[str, str]:
        """
        Gathers all relevant project files (e.g., README, requirements) that might help generate predict.py.
        
        :param repo_path: Path to the repository.
        :return: Dictionary of file names and their contents.
        """
        files = {}
        # Gather README, requirements.txt, pyproject.toml if they exist
        for filename in ["README.md", "requirements.txt", "pyproject.toml"]:
            file_path = repo_path / filename
            if file_path.exists():
                files[filename] = file_path.read_text()
        return files

    def _extract_file_from_gpt_response(self, content: str, filename: str) -> str:
        """
        Extracts the content of a specific file from the AI's response.
        
        :param content: The full response from the AI.
        :param filename: The name of the file to extract (e.g., predict.py).
        :return: The extracted content of the file.
        """
        pattern = re.compile(rf"(?<=-- FILE_START: {filename})(.*?)(?=-- FILE_END: {filename})", re.DOTALL)
        match = pattern.search(content)
        if not match:
            raise ValueError(f"Failed to generate {filename}")
        return match.group(1).strip()


class ErrorDiagnosisAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for diagnosing errors in the project.
        """
        super().__init__(ai_provider, api_key, prompts.error_diagnosis_system, chat_history_path)

    @retry(5)
    def diagnose_error(self, predict_command: str, error: str) -> tuple[str, bool]:
        diagnosis = self.ai.call(prompts.diagnose_error(predict_command=predict_command, error=self._truncate_error(error)))
        package_error = self.ai.call(prompts.package_error(predict_command=predict_command, error=self._truncate_error(error)))
        return diagnosis, package_error == "True"

    def _truncate_error(self, error, max_length=10000):
        return error[:max_length]



class CogFixingAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for fixing issues in configuration files.
        """
        super().__init__(ai_provider, api_key, prompts.cog_fixing_system, chat_history_path)

    @retry(5)
    def fix_cog_yaml(self) -> str:
        response = self.ai.call(prompts.fix_cog_yaml)
        return self._file_from_gpt_response(response, "cog.yaml")

    def _file_from_gpt_response(self, content: str, filename: str) -> str:
        pattern = re.compile(rf"(?<={file_start(filename)})(.*?)(?={file_end(filename)})", re.MULTILINE | re.DOTALL)
        match = pattern.search(content)
        if not match:
            raise ValueError(f"Failed to generate {filename}")
        return match[1].strip()


class PredictFixingAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for fixing issues in configuration files.
        """
        super().__init__(ai_provider, api_key, prompts.predict_fixing_system, chat_history_path)

    @retry(5)
    def fix_predict_py(self) -> str:
        response = self.ai.call(prompts.fix_predict_py)
        return self._file_from_gpt_response(response, "predict.py")

    def _file_from_gpt_response(self, content: str, filename: str) -> str:
        pattern = re.compile(rf"(?<={file_start(filename)})(.*?)(?={file_end(filename)})", re.MULTILINE | re.DOTALL)
        match = pattern.search(content)
        if not match:
            raise ValueError(f"Failed to generate {filename}")
        return match[1].strip()


class CogPredictAgent(BaseAgent):
    def __init__(self, ai_provider: str, api_key: str, chat_history_path: Path):
        """
        Agent responsible for generating and executing the cog predict command.
        """
        super().__init__(ai_provider, api_key, prompts.cog_predict_system, chat_history_path)

    def generate_predict_command(self, predict_py: str) -> str:
        return self.ai.call(prompts.cog_predict(predict_py))

    def run_cog_predict(self, repo_path: Path, predict_command: str) -> tuple[bool, str]:
        proc = subprocess.Popen(predict_command, cwd=repo_path, stderr=subprocess.PIPE, shell=True)
        stderr = self._collect_stderr(proc)
        if proc.returncode == 0 and "Traceback (most recent call last)" not in stderr:
            return True, stderr
        return False, stderr

    def _collect_stderr(self, proc):
        stderr = ""
        for line in proc.stderr:
            line = line.decode()
            sys.stderr.write(line)
            stderr += line
        return stderr

