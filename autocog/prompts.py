import os
from pathlib import Path
from jinja2 import nodes, Environment, FileSystemLoader
from jinja2.ext import Extension

COG_DOCS = "https://raw.githubusercontent.com/replicate/cog/main/docs/yaml.md"
PREDICT_DOCS = "https://raw.githubusercontent.com/replicate/cog/main/docs/python.md"
FILE_START = "-- FILE_START: "
FILE_END = "-- FILE_END: "
COMMAND_START = "-- COMMAND_START"
COMMAND_END = "-- COMMAND_END"
ERROR_COG_PREDICT = "cog_predict"
ERROR_PREDICT_PY = "predict.py"
ERROR_COG_YAML = "cog.yaml"


class FileStartExtension(Extension):
    tags = {"file_start"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        filename = parser.parse_expression()
        return nodes.Output([nodes.TemplateData(FILE_START), filename]).set_lineno(
            lineno
        )


class FileEndExtension(Extension):
    tags = {"file_end"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        filename = parser.parse_expression()
        return nodes.Output([nodes.TemplateData(FILE_END), filename]).set_lineno(lineno)


def render(template_name, **kwargs):
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    prompts_dir = current_dir / "prompts"
    env = Environment(
        loader=FileSystemLoader(prompts_dir),
        extensions=[FileStartExtension, FileEndExtension],
    )
    template = env.get_template(template_name + ".tpl")

    kwargs["command_end"] = COMMAND_END
    kwargs["command_start"] = COMMAND_START
    kwargs["ERROR_COG_PREDICT"] = ERROR_COG_PREDICT
    kwargs["ERROR_COG_YAML"] = ERROR_COG_YAML
    kwargs["ERROR_PREDICT_PY"] = ERROR_PREDICT_PY

    return template.render(**kwargs)


def order_paths(paths: list[Path], readme_contents: str | None) -> str:
    return render("order_paths", paths=paths, readme_contents=readme_contents)


def generate_initial(
    files: dict[str, str],
    tell: str | None,
    predict_py: str | None,
    cog_yaml: str | None,
) -> str:
    return render(
        "generate_initial",
        files=files,
        tell=tell,
        predict_py=predict_py,
        cog_yaml=cog_yaml,
    )


def diagnose_error(predict_command: str, error: str) -> str:
    return render("diagnose_error", predict_command=predict_command, error=error)


system = render("system")
cog_predict = render("cog_predict")
fix_predict_py = render("fix_predict_py")
fix_cog_yaml = render("fix_cog_yaml")


def file_start(filename):
    return f"-- FILE_START: {filename}"


def file_end(filename):
    return f"-- FILE_END: {filename}"
