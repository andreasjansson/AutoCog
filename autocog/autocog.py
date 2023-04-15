from collections import deque
import sys
from PIL import Image
import wave
import re
import click
import os
import subprocess
import openai
import tempfile
import glob


VERBOSE = True
MAX_ATTEMPTS = 3


def file_start(filename):
    return f"-- FILE_START: {filename}"


def file_end(filename):
    return f"-- FILE_END: {filename}"


COG_YAML_EXAMPLE = """build:
  gpu: true
  system_packages:
    - "libgl1-mesa-glx"
    - "libglib2.0-0"
  python_version: "3.8"
  python_packages:
    - "torch==1.8.1"
predict: "predict.py:Predictor"
"""
PREDICT_PY_EXAMPLE = '''from cog import BasePredictor, Input, Path
import torch

class Predictor(BasePredictor):
    def setup(self):
        """Load the model into memory to make running multiple predictions efficient"""
        self.model = torch.load("./weights.pth")

    # The arguments and types the model takes as input
    def predict(self,
          image: Path = Input(description="Grayscale input image")
    ) -> Path:
        """Run a single prediction on the model"""
        processed_image = preprocess(image)
        output = self.model(processed_image)
        return postprocess(output)
'''

SYSTEM_PROMPT = "You are an expert Python machine learning developer."
COG_PROMPT = f"""
Below is an example of a cog.yaml file and a predict.py file.

{file_start("cog.yaml")}
{COG_YAML_EXAMPLE}
{file_end("cog.yaml")}

{file_start("predict.py")}
{PREDICT_PY_EXAMPLE}
{file_end("predict.py")}
"""


def cog_predict_prompt(predict_contents):
    return f"""
Below is an example of a cog predict command:

cog predict -i @input.jpg

Return a cog predict command for the following predict.py file (and return only the prompt, no other text):

```
{predict_contents}
```
"""


ERROR_COG_PREDICT = "cog_predict"
ERROR_PREDICT_PY = "predict.py"
ERROR_COG_YAML = "cog.yaml"


def diagnose_error_prompt(predict_contents, cog_predict_command, error):
    return f"""
The command `{cog_predict_command}` return the following error:

```
{error}
```

Given the predict.py file below, diagnose whether the error occurred because of an error in predict.py, an error in cog.yaml, or an error in the cog predict command. Only output the string {ERROR_COG_PREDICT} or {ERROR_COG_YAML} or {ERROR_PREDICT_PY}. Don't output anything else.

{file_start("predict.py")}
{predict_contents}
{file_end("predict.py")}
    """


def fix_predict_py_prompt(predict_contents, error):
    return f"""
Below is an example of a predict.py file:

{file_start("example_predict.py")}
{PREDICT_PY_EXAMPLE}
{file_end("example_predict.py")}

Given the following Cog predict.py file and error message, fix the predict.py file so that the error goes away. Return a diff of predict.py that can be applied to predict.py with the patch tool. Only return the diff and no other text (no FILE_START prefix, etc.), neither before or after the diff.

{file_start("predict.py")}
{predict_contents}
{file_end("predict.py")}

-- ERROR_START
{error}
-- ERROR_END
"""


def fix_cog_yaml_prompt(cog_yaml_contents, predict_contents, error):
    return f"""
Below is an example of a cog.yaml file:

{file_start("example_cog.yaml")}
{COG_YAML_EXAMPLE}
{file_end("example_cog.yaml")}

Given the following cog.yaml file, predict.py file, and error message, fix the cog.yaml file so that the error goes away. Ensure that all Python packages must have pinned versions. Only return the cog.yaml contents and no other text (no FILE_START prefix, etc.), neither before or after the diff.

Some common sources of errors include:
* Wrong Python version (sometimes indicated by numpy failing to build)

{file_start("cog.yaml")}
{cog_yaml_contents}
{file_end("cog.yaml")}

{file_start("predict.py")}
{predict_contents}
{file_end("predict.py")}

-- ERROR_START
{error}
-- ERROR_END
"""


def order_paths_prompt(paths, readme_contents):
    paths_list = "\n".join(paths)

    prompt = f"""
Given the file paths and readme below, order them by how relevant they are for inference and in particular for building a Replicate prediction model with Cog. Return the ordered file paths in the following format (and make sure to not include anything else than the list of file paths):

most_relevant.py
second_most_relevant.py
third_most_relevant.py
[...]
least_relevant.py

Here are the paths:

{paths_list}

End of paths. Below is the readme:

{readme_contents}
"""
    return prompt


def order_paths(repo_path, *, attempt=0):
    paths = find_python_files(repo_path)
    if len(paths) == 0:
        raise ValueError(f"{repo_path} has no Python files")

    if VERBOSE:
        print("Ordering files based on importance...", file=sys.stderr)

    readme_contents = ""
    readme_path = os.path.join(repo_path, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path) as f:
            readme_contents = f.read()

    content = call_gpt(order_paths_prompt(paths, readme_contents))
    ordered_paths = content.strip().splitlines()
    if set(paths) != set(ordered_paths):
        if attempt == 5:
            raise ValueError("Failed to order paths")
        return order_paths(repo_path, attempt=attempt + 1)
    return ordered_paths


def files_prompt(repo_path, paths, max_length):
    prompt = f"""
Given the files below, generate a predict.py and cog.yaml file. Ensure that all Python packages must have pinned versions. Wrap the contents of both files in the strings '{file_start("<filename>")}' and '{file_end("<filename>")}'. Don't output any other text before or after the files.

"""
    readme_path = os.path.join(repo_path, "README.md")
    if os.path.exists(readme_path):
        paths.insert(0, readme_path)
    requirements_path = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(requirements_path):
        paths.insert(0, requirements_path)

    for path in paths:
        with open(path, "r") as f:
            filename = os.path.relpath(path, repo_path)
            contents = f.read()
            is_truncated = False
            if len(prompt + contents) > max_length:
                contents = contents[: max_length - len(prompt)]
                is_truncated = True

            prompt += (
                file_start(filename) + "\n" + contents + file_end(filename) + "\n\n"
            )
            if is_truncated:
                return prompt

    return prompt


def generate_files(repo_path, paths, *, attempt=0):
    max_lengths = [25000, 20000, 15000, 10000]

    try:
        content = call_gpt(
            [
                {"role": "user", "content": COG_PROMPT},
                {"role": "assistant", "content": "Okay."},
                {
                    "role": "user",
                    "content": files_prompt(
                        repo_path, paths, max_length=max_lengths[attempt]
                    ),
                },
            ]
        )
    except openai.error.InvalidRequestError as e:
        if "context length" in str(e):
            if attempt == len(max_lengths):
                raise
            return generate_files(repo_path, paths, attempt=attempt + 1)

    if file_end("cog.yaml") not in content or file_end("predict.py") not in content:
        if attempt == len(max_lengths):
            raise ValueError("Failed to generate a predict.py file")
        if VERBOSE:
            print(
                f"Failed to complete the output, trying again (attempt {attempt + 1}/{len(max_lengths)})",
                file=sys.stderr,
            )
        generate_files(repo_path, paths, attempt=attempt + 1)

    files = {
        "cog.yaml": file_from_openai_response(content, "cog.yaml"),
        "predict.py": file_from_openai_response(content, "predict.py"),
    }

    return files


def find_python_files(path):
    python_files = []
    queue = deque([path])

    while queue:
        current_path = queue.popleft()
        entries = os.listdir(current_path)

        for entry in entries:
            full_entry_path = os.path.join(current_path, entry)

            if os.path.isfile(full_entry_path) and full_entry_path.endswith(".py"):
                python_files.append(full_entry_path)
            elif os.path.isdir(full_entry_path):
                queue.append(full_entry_path)

    return python_files


def call_gpt(messages, *, temperature=0.5):
    if type(messages) == str:
        messages = [{"role": "user", "content": messages}]

    response = openai.ChatCompletion.create(
        model="gpt-4",  # gpt-4-32k
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
        ]
        + messages,
        n=1,
        stop=None,
        temperature=temperature,
        stream=True,
    )
    text = ""
    for chunk in response:
        if not chunk:
            continue
        chunk_text = chunk["choices"][0]["delta"].get("content", None)
        if chunk_text == None:
            continue
        text += chunk_text
        if VERBOSE:
            sys.stderr.write(chunk_text)
            sys.stderr.flush()

    if VERBOSE:
        sys.stderr.write("\n")

    return text


def generate_cog_predict_command(predict_contents):
    return call_gpt(cog_predict_prompt(predict_contents))


def file_from_openai_response(content, filename):
    pattern = re.compile(
        rf"(?<={file_start(filename)})(?:\n```[a-z]*\n)?(.*?)(?:\n```\n)?(?={file_end(filename)})",
        re.MULTILINE | re.DOTALL,
    )
    return pattern.search(content)[1].strip()


def write_files(repo_path, files):
    for filename, content in files.items():
        file_path = os.path.join(repo_path, filename)
        with open(file_path, "w") as f:
            f.write(content)


def run_cog_predict(cog_predict_command, repo_path):
    if VERBOSE:
        print(cog_predict_command, file=sys.stderr)

    proc = subprocess.Popen(
        cog_predict_command, cwd=repo_path, stderr=subprocess.PIPE, shell=True
    )
    stderr = ""
    for line in proc.stderr:
        line = line.decode()
        if VERBOSE:
            sys.stderr.write(line)
        stderr += line

    proc.wait()
    if proc.returncode == 0:
        if not VERBOSE:
            print(stderr.split("Running prediction...")[1].strip())
        return True, stderr

    return False, stderr


def create_files_for_cog_predict_command(cog_predict_command, repo_path):
    file_inputs = re.findall(r"@([\w.]+)", cog_predict_command)

    for filename in file_inputs:
        tmp_path = os.path.join("/tmp", filename)
        cog_predict_command = cog_predict_command.replace(
            "@" + filename, "@" + tmp_path
        )
        create_empty_file(tmp_path, repo_path)

    return cog_predict_command


def create_empty_file(filename, repo_path):
    file_type = filename.split(".")[-1]
    filename = os.path.join(repo_path, filename)
    if file_type == "jpg":
        img = Image.new("RGB", (256, 256), color="white")
        img.save(filename, format="JPEG")
    elif file_type == "png":
        img = Image.new("RGBA", (256, 256), color=(0, 0, 0, 0))
        img.save(filename, format="PNG")
    elif file_type == "wav":
        with wave.open(filename, "wb") as wav_file:
            wav_file.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            data = np.zeros((44100, 2))
            wav_file.writeframes(data.astype(np.int16).tobytes())
    elif file_type == "mp3":
        with open(filename, "wb") as mp3_file:
            pass
    elif file_type == "txt":
        with open(filename, "w") as txt_file:
            pass
    elif file_type == "mp4":
        with open(filename, "wb") as mp4_file:
            pass
    elif file_type == "avi":
        with open(filename, "wb") as avi_file:
            pass
    else:
        raise ValueError("Unsupported file type")


def parse_cog_predict_error(stderr, *, max_length=20000):
    if "Running prediction...\n" in stderr:
        error = stderr.split("Running prediction...\n")[1].split("panic: ")[0]
    else:
        error = stderr.split("panic: ")[0]

    return error[-max_length:]


def diagnose_error(predict_contents, cog_predict_command, error, *, attempt=0):
    if VERBOSE:
        print("Diagnosing source of error: ", file=sys.stderr)

    text = call_gpt(diagnose_error_prompt(predict_contents, cog_predict_command, error))
    if text not in [ERROR_PREDICT_PY, ERROR_COG_PREDICT, ERROR_COG_YAML]:
        if attempt == 3:
            raise ValueError("Failed to diagnose error")
        return diagnose_error(predict_contents, cog_predict_command, error, attempt=attempt + 1)
    return text


def fix_predict_py(predict_contents, error, *, attempt=0):
    text = call_gpt(fix_predict_py_prompt(predict_contents, error))
    pattern = re.compile(
        rf"(?:\n```[a-z]*\n)?(.*)(?:\n```)?",
        re.MULTILINE | re.DOTALL,
    )
    diff = pattern.search(text)[1]
    try:
        return patch(predict_contents, diff)
    except:
        if attempt == 3:
            raise ValueError("Failed to generate patch")
        return fix_predict_py(predict_contents, error, attempt=attempt + 1)


def fix_cog_yaml(cog_yaml_contents, predict_contents, error, *, attempt=0):
    text = call_gpt(fix_cog_yaml_prompt(cog_yaml_contents, predict_contents, error), temperature=0.5 + attempt/5)
    pattern = re.compile(
        rf"(?:\n```[a-z]*\n)?(.*)(?:\n```)?",
        re.MULTILINE | re.DOTALL,
    )
    return pattern.search(text)[1]


def patch(contents, diff):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_original:
        tmp_original.write(contents.encode())
        tmp_original.flush()

    # Write the patch_str to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_patch:
        tmp_patch.write(diff.encode())
        tmp_patch.flush()

    # Call the patch command using subprocess.run()
    subprocess.run(["patch", tmp_original.name, tmp_patch.name], check=True)

    # Read the patched contents from the temporary file
    with open(tmp_original.name, "r") as patched_file:
        patched_contents = patched_file.read()

    # Clean up the temporary files
    os.unlink(tmp_original.name)
    os.unlink(tmp_patch.name)

    return patched_contents


@click.command()
@click.option(
    "-r",
    "--repo",
    default="",
    help="Path to the ML repository (default is current directory)",
)
@click.option("-t", "--token", required=True, help="OpenAI API token (required)")
@click.option("-q", "--quiet", is_flag=True, help="Suppress output")
def autocog(repo, token, quiet):
    global VERBOSE

    if quiet:
        VERBOSE = False

    openai.api_key = token

    repo_path = repo or os.getcwd()

    paths = order_paths(repo_path)
    files = generate_files(repo_path, paths)
    write_files(repo_path, files)
    cog_predict_command = generate_cog_predict_command(files["predict.py"])
    for attempt in range(MAX_ATTEMPTS):
        cog_predict_command = create_files_for_cog_predict_command(
            cog_predict_command, repo_path
        )
        success, stderr = run_cog_predict(cog_predict_command, repo_path)
        if success:
            return

        if attempt == MAX_ATTEMPTS - 1:
            print(f"Failed after {MAX_ATTEMPTS} attempts, giving up :'(")
            sys.exit(1)

        if VERBOSE:
            print(
                f"Attempt {attempt + 1}/{MAX_ATTEMPTS} failed, trying to fix...",
                file=sys.stderr,
            )

        error = parse_cog_predict_error(stderr)
        error_source = diagnose_error(files["predict.py"], cog_predict_command, error)
        if error_source == ERROR_PREDICT_PY:
            files["predict.py"] = fix_predict_py(files["predict.py"], error)
            write_files(repo_path, files)
        elif error_source == ERROR_COG_YAML:
            files["cog.yaml"] = fix_cog_yaml(files["cog.yaml"], files["predict.py"], error, attempt=attempt)
        elif error_source == ERROR_COG_PREDICT:
            cog_predict_command = generate_cog_predict_command(files["predict.py"])
            write_files(repo_path, files)


if __name__ == "__main__":
    autocog()
