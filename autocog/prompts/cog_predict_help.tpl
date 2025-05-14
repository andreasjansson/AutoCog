Run a prediction.

If 'image' is passed, it will run the prediction on that Docker image.
It must be an image that has been built by Cog.

Otherwise, it will build the model in the current directory and run
the prediction on that.

Usage:
  cog predict [image] [flags]

Flags:
  -e, --env stringArray              Environment variables, in the form name=value
      --f string                     The name of the config file. (default "cog.yaml")
      --gpus docker run --gpus       GPU devices to add to the container, in the same format as docker run --gpus.
  -h, --help                         help for predict
  -i, --input stringArray            Inputs, in the form name=value. if value is prefixed with @, then it is read from a file on disk. E.g. -i path=@image.jpg
  -o, --output string                Output path
      --progress string              Set type of build progress output, 'auto' (default), 'tty' or 'plain' (default "plain")
      --setup-timeout uint32         The timeout for a container to setup (in seconds). (default 300)
      --use-cog-base-image           Use pre-built Cog base image for faster cold boots (default true)
      --use-cuda-base-image string   Use Nvidia CUDA base image, 'true' (default) or 'false' (use python base image). False results in a smaller image but may cause problems for non-torch projects (default "auto")

Global Flags:
      --debug     Show debugging output
      --version   Show version of Cog
