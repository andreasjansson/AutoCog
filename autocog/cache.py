import os
import pickle
import functools
import shutil


class Cache:
    def __init__(self, repo_path, cache_name):
        self.cache_dir = os.path.join(repo_path, ".autocog", "cache")
        self.cache_file = os.path.join(self.cache_dir, cache_name)
        os.makedirs(self.cache_dir, exist_ok=True)

    def exists(self):
        return os.path.exists(self.cache_file)

    def read(self):
        with open(self.cache_file, 'rb') as f:
            return pickle.load(f)

    def write(self, data):
        with open(self.cache_file, 'wb') as f:
            pickle.dump(data, f)

def cached(cache_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(repo_path, *args, **kwargs):
            cache = Cache(repo_path, cache_name)
            if cache.exists():
                return cache.read()
            result = func(repo_path, *args, **kwargs)
            cache.write(result)
            return result
        return wrapper
    return decorator


def purge_cache(repo_path):
    cache_dir = os.path.join(repo_path, ".autocog", "cache")
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)
