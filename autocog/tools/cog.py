from pathlib import Path
import sys
import subprocess

from toololo import log


def predict(predict_command: str) -> tuple[bool, str]:
    log.info(predict_command)

    proc = subprocess.Popen(
        predict_command, stderr=subprocess.PIPE, shell=True
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


def write_files(cog_yaml_contents: str, predict_py_contents: str):
    log.info(f"# cog.yaml:\n{cog_yaml_contents}")
    log.info(f"\n\n# predict.py:\n{predict_py_contents}")

    Path("cog.yaml").write_text(cog_yaml_contents)
    Path("predict.py").write_text(predict_py_contents)
