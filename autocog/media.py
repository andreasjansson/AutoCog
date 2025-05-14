import subprocess
from pathlib import Path
import tempfile
import os
from pathlib import Path
import replicate


def describe_image(image_path: str) -> str:
    output = replicate.run(
        "anthropic/claude-3.5-sonnet",
        input={
            "prompt": "Describe this image in detail",
            "image": Path(image_path),
        },
    )
    return "".join(output)


def transcribe_speech(audio_path: str) -> str:
    output = replicate.run(
        "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
        input={"audio": Path(audio_path)},
    )
    return output["text"]


def imagemagick_create_image(convert_args: list[str]) -> Path:
    """
    Run the Imagemagic convert convert command with the provided arguments
    and return the resulting file Path.
    """
    # Create a temporary file with .png extension for output
    output_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    output_file.close()
    output_path = Path(output_file.name)

    # Construct the convert command
    cmd = ["convert"] + convert_args + [str(output_path)]

    # Run the command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        # Clean up the temporary file if the command fails
        if output_path.exists():
            os.unlink(output_path)
        raise

    return output_path


def describe_audio(audio_path: str) -> str:
    """
    Caption sounds, music, etc.
    """
    output = replicate.run(
        "zsxkib/kimi-audio-7b-instruct:7500b32387695e89da3d09271850319ba027969f0c714dfc226361609ff29f2b",
        input={
            "audio": Path(audio_path),
            "prompt": "Describe this audio file in detail.",
            "output_type": "text",
            "return_json": True,
        },
    )
    return output["json_str"]
