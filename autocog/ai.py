import os
import sys
import time
from typing import List, Dict, Union, Optional
from pathlib import Path

from openai import OpenAI, APIStatusError, RateLimitError
from anthropic import Anthropic


class AI:
    def __init__(
        self,
        system_prompt: str,
        chat_history_path: Path,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.system_prompt = system_prompt
        self.provider = provider.lower()
        self.api_key = api_key or os.environ.get(f"{self.provider.upper()}_API_KEY")
        self.model = model or self._get_default_model()
        self.history: List[Dict[str, str]] = []
        self.client = self._initialize_client()
        self.chat_history_path = chat_history_path

    def _initialize_client(self):
        if self.provider == "openai":
            return OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            return Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _get_default_model(self):
        if self.provider == "openai":
            return "gpt-4o-2024-08-06"
        elif self.provider == "anthropic":
            return "claude-3-5-sonnet-20240620"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def call(
        self, messages: Union[str, List[Dict[str, str]]], temperature: float = 0.5
    ) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        full_messages = self.history + messages

        try:
            if self.provider == "openai":
                response = self._call_openai(full_messages, temperature)
            elif self.provider == "anthropic":
                response = self._call_anthropic(full_messages, temperature)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            self.history.extend(messages)
            self.history.append({"role": "assistant", "content": response})

            self.save_chat_history()

            return response

        except (RateLimitError, APIStatusError) as e:
            if "rate limit" in str(e).lower():
                time.sleep(10)
                print(
                    "Exceeded rate limit, sleeping for ten seconds and retrying...",
                    file=sys.stderr,
                )
                return self.call(messages, temperature)
            raise

    def _call_openai(self, messages: List[Dict[str, str]], temperature: float) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            stream=True,
        )

        text = ""
        for chunk in response:
            chunk_text = chunk.choices[0].delta.content
            if chunk_text:
                text += chunk_text
                sys.stderr.write(chunk_text)
                sys.stderr.flush()

        sys.stderr.write("\n")
        return text

    def _call_anthropic(
        self, messages: List[Dict[str, str]], temperature: float
    ) -> str:
        # Use Anthropic's beta prompt caching
        response = self.client.beta.prompt_caching.messages.create(
            model=self.model,
            messages=messages,
            system=[{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
            temperature=temperature,
            max_tokens=8192,
            stream=True,
        )

        text = ""
        for event in response:
            if event.type == "content_block_delta":
                chunk_text = event.delta.text
                text += chunk_text
                sys.stderr.write(chunk_text)
                sys.stderr.flush()

        sys.stderr.write("\n")
        return text

    def clear_history(self):
        self.history = []
        if self.chat_history_path.exists():
            self.chat_history_path.unlink()

    def save_chat_history(self):
        with self.chat_history_path.open("w") as f:
            f.write(f"## SYSTEM:\n\n{self.system_prompt}\n\n")
            for message in self.history:
                role = message["role"].upper()
                content = message["content"]
                f.write(f"## {role}:\n\n{content}\n\n")

    def load_chat_history(self):
        self.history = []
        current_role = None
        current_content = []

        with self.chat_history_path.open("r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line.startswith("## ") and line.endswith(":"):
                if current_role and current_content:
                    content = "\n".join(current_content).strip()
                    if current_role == "SYSTEM":
                        self.system_prompt = content
                    else:
                        self.history.append(
                            {"role": current_role.lower(), "content": content}
                        )
                    current_content = []
                current_role = line[3:-1]
            elif line:
                current_content.append(line)

        # Add the last message if there is one
        if current_role and current_content:
            content = "\n".join(current_content).strip()
            if current_role == "SYSTEM":
                self.system_prompt = content
            else:
                self.history.append({"role": current_role.lower(), "content": content})
