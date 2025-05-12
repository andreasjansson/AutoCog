The command {{ predict_command }} returned the following error:

{{ error }}

Given the predict.py and cog.yaml files above, diagnose whether the error occurred because of an error in predict.py, an error in the python_dependencies of cog.yaml (e.g. there is no matching distribution found or resolution impossible), an error in cog.yaml outside of python_dependencies, or an error in the cog predict command.

Only output the string {{ ERROR_PREDICT_PY }} or {{ ERROR_PYTHON_DEPENDENCIES }} or {{ ERROR_COG_YAML }} or {{ ERROR_COG_PREDICT }}. Don't output anything else since I intend to parse the output and use it in a programmatic pipeline.
