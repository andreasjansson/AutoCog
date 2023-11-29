import sys
import time

from openai import APIError, OpenAI, RateLimitError

SYSTEM_PROMPT = "You are an expert Python machine learning developer."


class MaxTokensExceeded(BaseException):
    pass


def initialize_client(api_key, base_url=None):
    if base_url:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    else:
        client = OpenAI(api_key=api_key)
    return client


def call_gpt(messages, client, *, temperature=0.5, model="gpt-4"):
    if type(messages) == str:
        messages = [{"role": "user", "content": messages}]

    try:
        response = client.chat.completions.create(
            model=model,  # gpt-4-32k
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
    except RateLimitError as e:
        time.sleep(10)
        print(
            "Exceeded OpenAI rate limit, sleeping for ten seconds and retrying...",
            file=sys.stderr,
        )
        return call_gpt(messages, temperature=temperature)
    # except InvalidRequestError as e:
    #     if "This model's maximum context length is" in str(e):
    #         raise MaxTokensExceeded()
    #     raise
    except APIError as e:
        print("Some other error")
        raise Exception from e

    text = ""
    for chunk in response:
        if not chunk:
            continue
        chunk_text = chunk.choices[0].delta
        if chunk_text == None:
            continue
        text += chunk_text
        sys.stderr.write(chunk_text)
        sys.stderr.flush()

    sys.stderr.write("\n")

    return text
