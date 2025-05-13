from dataclasses import dataclass
import os
import subprocess
from pathlib import Path
import requests
import json
import time
import jwt
from toololo import log


def is_git_repo() -> bool:
    """Check if the current directory is a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def is_dirty() -> bool:
    """Check if the git repository has uncommitted changes."""
    if not is_git_repo():
        return False

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return bool(result.stdout.strip())


def add(files: list[str]) -> None:
    """Add files to git staging area."""
    if not is_git_repo():
        log.error("Not a git repository")
        return

    subprocess.run(
        ["git", "add"] + files,
        check=True,
    )


def commit(message: str) -> None:
    """Commit changes to git repository."""
    if not is_git_repo():
        log.error("Not a git repository")
        return

    if not is_dirty():
        log.info("No changes to commit")
        return

    subprocess.run(
        ["git", "commit", "-m", message],
        check=True,
    )


def clone(repo_url: str) -> Path:
    """Clone a git repository to a temporary directory."""
    # Extract repo name from URL to use as directory name
    repo_name = repo_url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # Clone to a directory in the current working directory
    clone_path = Path(os.getcwd()) / repo_name

    if clone_path.exists():
        # If directory exists, generate a unique name
        base_name = repo_name
        counter = 1
        while clone_path.exists():
            repo_name = f"{base_name}_{counter}"
            clone_path = Path(os.getcwd()) / repo_name
            counter += 1

    log.info(f"Cloning {repo_url} to {clone_path}")

    subprocess.run(
        ["git", "clone", repo_url, str(clone_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return clone_path


def _get_github_token_from_app(app_id, private_key, installation_id):
    """Generate a GitHub App installation token."""
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 600,  # JWT expiration time (10 minutes)
        "iss": app_id,
    }

    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")

    # Get the installation token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers=headers,
    )
    response.raise_for_status()

    return response.json()["token"]


@dataclass
class GitHubAuth:
    github_token: str | None = None
    github_app_id: str | None = None
    github_app_key: str | None = None
    github_app_key_path: str | None = None
    github_installation_id: str | None = None

    def headers(self):
        if self.github_token:
            access_token = self.github_token
        elif (
            self.github_app_id
            and self.github_installation_id
            and (self.github_app_key or self.github_app_key_path)
        ):
            if self.github_app_key_path:
                with open(self.github_app_key_path, "r") as key_file:
                    private_key = key_file.read()
            else:
                private_key = self.github_app_key

            access_token = _get_github_token_from_app(
                self.github_app_id, private_key, self.github_installation_id
            )
        else:
            raise ValueError(
                "Either github_token or (github_app_id, github_app_key/github_app_key_path, "
                "and github_installation_id) must be provided"
            )

        # Check if repository already exists
        return {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }


def push(
    repo_name: str,
    auth: GitHubAuth,
) -> str:
    """
    Push the local repository to GitHub.

    Args:
        repo_name: Name of the GitHub repository in the format owner/name
        github_token: Personal access token for GitHub
        github_app_id: GitHub App ID
        github_app_key: GitHub App private key content
        github_app_key_path: Path to GitHub App private key file
        github_installation_id: GitHub App installation ID

    Returns:
        URL of the created repository
    """
    if not is_git_repo():
        raise ValueError("Not a git repository")

    # Determine authentication method
    access_token = None

    # Check if repo exists
    resp = requests.get(
        f"https://api.github.com/repos/{repo_name}",
        headers=auth.headers(),
    )

    repo_exists = resp.status_code == 200

    # Create repository if it doesn't exist
    if not repo_exists:
        create_repo(repo_name, auth)

    # Set the remote URL
    remote_url = f"https://x-access-token:{access_token}@github.com/{repo_name}.git"

    # Check if remote exists
    remote_exists = False
    try:
        subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        remote_exists = True
    except subprocess.CalledProcessError:
        pass

    if remote_exists:
        # Set remote URL if it exists
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url],
            check=True,
        )
    else:
        # Add remote if it doesn't exist
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            check=True,
        )

    # Push to GitHub
    subprocess.run(
        ["git", "push", "-u", "origin", "master"],
        check=True,
        stderr=subprocess.PIPE,
    )

    return f"https://github.com/{repo_name}"


def create_repo(
    repo_name: str,
    auth: GitHubAuth,
):
    owner, name = repo_name.split("/")
    data = {
        "name": name,
        "private": True,
        "description": "Repository created by AutoCog",
    }

    create_url = f"https://api.github.com/orgs/{owner}/repos"
    try:
        # Try to create in organization first
        resp = requests.post(
            create_url,
            headers=auth.headers(),
            data=json.dumps(data),
        )
        resp.raise_for_status()
    except requests.HTTPError:
        # If org creation fails, try user account
        create_url = "https://api.github.com/user/repos"
        resp = requests.post(
            create_url,
            headers=auth.headers(),
            data=json.dumps(data),
        )
        resp.raise_for_status()
