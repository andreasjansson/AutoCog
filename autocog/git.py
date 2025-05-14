from pathlib import Path
import subprocess
from dataclasses import dataclass
import os
from github import Github, GithubIntegration
from github import Github

from toololo import log


@dataclass
class GitHubAuth:
    app_id: int | None = None
    app_key: str | None = None
    app_key_path: Path | None = None
    installation_id: int | None = None


def is_dirty() -> bool:
    staged_changes = (
        subprocess.run(
            ["git", "diff-index", "--quiet", "HEAD", "--"],
            check=False,
        ).returncode
        != 0
    )
    return staged_changes


def add(files: list[str]) -> None:
    """Add files to git staging area"""
    subprocess.run(["git", "add"] + files, check=True)


def commit(message: str) -> None:
    """Commit changes with the specified message"""
    subprocess.run(["git", "commit", "-a", "-m", message], check=True)


def clone(repo_url: str) -> str:
    """
    Clone a git repository

    Args:
        repo_url: URL of the repository to clone

    Returns:
        Path to the cloned repository
    """
    # Extract repo name from URL for the target directory
    repo_name = repo_url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # Clone the repository
    subprocess.run(["git", "clone", repo_url, repo_name], check=True)

    return os.path.abspath(repo_name)


def push(repo_name: str, auth: GitHubAuth) -> str:
    """
    Push the repository to GitHub, creating a private
    repo if it doesn't already exist.

    Args:
        repo_name: The name of the repository in the format 'owner/name'
        auth: GitHub authentication details

    Returns:
        URL of the created repository
    """
    # Validate the GitHub App authentication parameters
    if not (auth.app_id and auth.installation_id and
           (auth.app_key or auth.app_key_path)):
        raise ValueError("GitHub App credentials are required for pushing to GitHub")

    # Get private key content
    if auth.app_key:
        private_key = auth.app_key
    elif auth.app_key_path:
        with open(auth.app_key_path, "r") as key_file:
            private_key = key_file.read()
    else:
        raise ValueError("Either app_key or app_key_path must be provided")

    # Create GitHub integration instance
    integration = GithubIntegration(auth.app_id, private_key)

    # Get an access token for the installation
    access_token = integration.get_access_token(auth.installation_id).token

    # Create GitHub instance with the access token
    gh = Github(access_token)

    # Parse owner and repo name
    owner, name = repo_name.split("/")

    # Check if repo exists or create it
    try:
        principal = gh.get_organization(owner)
    except:
        principal = gh.get_user()
    try:
        principal.get_repo(name)
    except:
        principal.create_repo(name, private=True)

    repo_url = f"https://github.com/{repo_name}"

    # Configure Git to use the token for authentication
    remote_url = f"https://x-access-token:{access_token}@github.com/{repo_name}.git"

    # Check if remote exists
    remote_exists = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        check=False
    ).returncode == 0

    if remote_exists:
        # Update the existing remote
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
    else:
        # Add a new remote
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)

    # Push to GitHub
    subprocess.run(["git", "push", "--set-upstream", "origin", "main"], check=True)

    return repo_url
