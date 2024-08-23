from pathlib import Path

import wave
import array
from PIL import Image
from pydub import AudioSegment
import cv2
import numpy as np


def create_empty_file(repo_path: Path, filename: str):
    file_type = filename.split(".")[-1]
    path = repo_path / filename
    if file_type == "jpg":
        img = Image.new("RGB", (256, 256), color="white")
        img.save(path, format="JPEG")
    elif file_type == "png":
        img = Image.new("RGBA", (256, 256), color=(0, 0, 0, 0))
        img.save(path, format="PNG")
    elif file_type == "wav":
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            data = array.array("h", [0] * 44100 * 2)  # 'h' is for signed short integers
            wav_file.writeframes(data.tobytes())
    elif file_type == "mp3":
        silence = AudioSegment.silent(duration=1000)  # duration in milliseconds
        silence.export(path, format="mp3")
    elif file_type == "txt":
        with open(path, "w") as txt_file:
            txt_file.write("   ")
    elif file_type == "mp4":
        height, width = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video = cv2.VideoWriter(str(path), fourcc, 1, (width, height))
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for _ in range(30):
            video.write(frame)
        video.release()
    elif file_type == "avi":
        height, width = 640, 480
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        video = cv2.VideoWriter(str(path), fourcc, 1, (width, height))
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for _ in range(30):
            video.write(frame)
        video.release()
    else:
        raise ValueError("Unsupported file type")
