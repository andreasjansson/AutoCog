## cog.yaml

* You usually don't need to add the working repository to the list of python packages. If you're doing that you're probably doing something wrong. This also includes adding `-e .` to `python_packages` in cog.yaml. Don't do that, since Cog doesn't have access to the working directory at build-time. Instead add directories to sys.modules if you need to.
* Some of the cog documentation claims that you should write requirements.txt instead of python_packages. Ignore that and use the old-style python_packages instead.
* Don't forget to indent cog.yaml properly!
* Don't include the 'image' field in cog.yaml

### Python dependencies

* In general, limit dependencies to the minimum required to run inference on the model.
* IMPORTANT: If there is an existing requirements.txt or setup.py with pinned versions, use those pinned versions as far as possible in cog.yaml. Definitely don't use an earlier version of any package than the ones specified in the repository.
* You may have outdated information on newer python package version, so don't be afraid to search pypi for package versions or search the web with error messages
* IMPORTANT: Prefer to use later versions of things, e.g. use Python 3.12 instead of 3.10 unless there's code in the repository that specifies 3.10. Same with package versions. Use torch 2.7.0 if no torch version has been specified.
* You don't need to include transitive Python dependencies, pip handles that itself
* The 'dac' python import usually refers to the 'descript-audio-codec==1.0.0' package on Pypi
* Many audio python packages require ffmpeg as a system package.
* Avoid installing fastapi since the Pydantic version in fastapi is incompatible with Cog.

## predict.py

* Don't use Gradio
* Be careful with jargon in input descriptions, etc. The audience are software engineers, and they may not be aware of domain-specific jargon.