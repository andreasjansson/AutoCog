import sys
import functools


def retry(attempts=3):
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Exception occurred: {e}", file=sys.stderr)
                    if attempt < attempts:
                        print(f"Retrying attempt {attempt}/{attempts}", file=sys.stderr)
                    else:
                        print(f"Giving up after {attempts} attempts", file=sys.stderr)
                        raise

        return wrapper_retry

    return decorator_retry
