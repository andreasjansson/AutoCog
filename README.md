# AutoCog

[![PyPI version](https://badge.fury.io/py/autocog.svg)](https://badge.fury.io/py/autocog)

_Generate [predict.py and cog.yaml](https://github.com/replicate/cog) automatically using GPT4_

![Screen recording](https://github.com/andreasjansson/AutoCog/raw/main/assets/screen-recording.gif)

## Install

```
pip install autocog
```

## Usage

First, set your OpenAI API key in an environment variable

```
OPENAI_API_KEY=sk-...
```

In the repo you want to cog-ify, run

```
autocog
```

This will generate a cog.yaml and predict.py based on the files in the current directory. It will then run the model and if it fails to run, it will attempt to fix the error and run it again. By default it has 5 attempts to fix it, which can be changed with the `--attempts` flag.

If your model needs a GPU to run, you need to run AutoCog on a GPU machine.

### Human in the loop

Sometimes AutoCog fails to create a working Cog configuration. In those cases you, the human, have to step in and edit the cog.yaml and predict.py files.

Once you have edited them, let AutoCog continue:

```
autocog --continue
```

By default, AutoCog will guess a `cog predict` command to run the model. If you want to specify your own predict command, use the `--predict-command` flag.
