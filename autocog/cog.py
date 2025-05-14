import yaml
from pathlib import Path
import sys
import subprocess

from toololo import log


def predict(predict_command: str) -> tuple[bool, str]:
    log.info(predict_command)

    proc = subprocess.Popen(predict_command, stderr=subprocess.PIPE, shell=True)
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


def write_files(
    predict_py_contents: str,
    gpu: bool,
    python_requirements: list[str],
    system_packages: list[str],
    predictor_class_name: str = "Predictor",
    python_version: str = "3.10",
    cuda: str | None = None,
):
    """
    Write Cog files to the filesystem based on provided parameters.

    Args:
        predict_py_contents: Contents of the predict.py file
        gpu: Whether the model requires GPU
        python_requirements: List of Python package requirements
        system_packages: List of system packages to install
        predictor_class_name: Name of the predictor class in predict.py
        python_version: Python version to use (e.g. "3.10")
        cuda: CUDA version to use (e.g. "11.8.0"), or None for CPU-only
    """
    log.info(f"# predict.py:\n{predict_py_contents}")

    # Write predict.py
    Path("predict.py").write_text(predict_py_contents)

    # Write requirements to cog_requirements.txt
    requirements_content = "\n".join(python_requirements)
    Path("cog_requirements.txt").write_text(requirements_content)
    log.info(f"# cog_requirements.txt:\n{requirements_content}")

    # Build cog.yaml content using the yaml package
    cog_config = {
        "build": {
            "gpu": gpu,
            "python_version": python_version,
            "python_requirements": "cog_requirements.txt",
        },
        "predict": f"predict.py:{predictor_class_name}",
    }

    # Add CUDA version if provided
    if cuda is not None:
        cog_config["build"]["cuda"] = cuda

    # Add system packages if any
    if system_packages:
        cog_config["build"]["system_packages"] = system_packages

    # Write cog.yaml
    with open("cog.yaml", "w") as f:
        yaml.dump(cog_config, f, default_flow_style=False, sort_keys=False)

    # Read the file back to log its contents
    cog_yaml_content = Path("cog.yaml").read_text()
    log.info(f"# cog.yaml:\n{cog_yaml_content}")


def login(replicate_token: str) -> None:
    log.info("Logging in to Replicate...")
    login_process = subprocess.run(
        ["cog", "login", "--token-stdin"],
        input=replicate_token,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if login_process.returncode != 0:
        raise RuntimeError(f"Failed to login to Replicate: {login_process.stderr}")


def push(model_name: str) -> None:
    log.info(f"Pushing model to r8.im/{model_name}...")
    result = subprocess.run(["cog", "push", f"r8.im/{model_name}"])

    if result.returncode != 0:
        raise RuntimeError(f"Failed to push model to Replicate")

    log.info(f"Successfully pushed model to Replicate as r8.im/{model_name}")
