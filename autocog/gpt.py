import sys
import openai


SYSTEM_PROMPT = "You are an expert Python machine learning developer."


class MaxTokensExceeded(BaseException):
    pass


def set_openai_api_key(api_key):
    openai.api_key = api_key


def call_gpt(messages, *, temperature=0.5):
    if type(messages) == str:
        messages = [{"role": "user", "content": messages}]

    try:
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
    except openai.error.RateLimitError as e:
        time.sleep(10)
        print(
            "Exceeded OpenAI rate limit, sleeping for ten seconds and retrying...",
            file=sys.stderr,
        )
        return call_gpt(messages, temperature=temperature)
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length is" in str(e):
            raise MaxTokensExceeded()
        raise

    text = ""
    for chunk in response:
        if not chunk:
            continue
        chunk_text = chunk["choices"][0]["delta"].get("content", None)
        if chunk_text == None:
            continue
        text += chunk_text
        sys.stderr.write(chunk_text)
        sys.stderr.flush()

    sys.stderr.write("\n")

    return text
