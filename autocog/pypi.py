import requests
from datetime import datetime
import sys


def package_versions(package_name: str) -> list[dict[str, str]]:
    """
    Get available versions of a PyPI package along with release dates.

    Args:
        package_name: Name of the PyPI package

    Returns:
        List of dictionaries containing version and upload date information
    """
    try:
        # Fetch package information from PyPI JSON API
        response = requests.get(
            f"https://pypi.org/pypi/{package_name}/json", timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # Extract version information
        versions = []
        for version, release_info in data["releases"].items():
            # Skip versions with no release files
            if not release_info:
                continue

            # Get upload date of the first file (usually there's just one)
            upload_time = release_info[0].get("upload_time")

            if upload_time:
                # Convert to more readable format
                try:
                    dt = datetime.fromisoformat(upload_time)
                    formatted_date = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    formatted_date = upload_time
            else:
                formatted_date = "Unknown"

            versions.append({"version": version, "release_date": formatted_date})

        # Sort versions by release date (most recent first)
        versions.sort(key=lambda x: x["release_date"], reverse=True)

        return versions

    except requests.exceptions.RequestException as e:
        print(
            f"Error fetching package information for {package_name}: {e}",
            file=sys.stderr,
        )
        return []
    except (KeyError, ValueError, TypeError) as e:
        print(
            f"Error parsing package information for {package_name}: {e}",
            file=sys.stderr,
        )
        return []
