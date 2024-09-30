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
    return render("order_paths/order_paths", paths=paths, readme_contents=readme_contents)


def generate_cog_yaml(
    files: dict[str, str],
    tell: str | None,
    predict_py: str | None,
    cog_yaml: str | None,
    package_versions: dict[set] | None,
) -> str:
    return render(
        "cog_generation/generate",
        files=files,
        tell=tell,
        predict_py=predict_py,
        cog_yaml=cog_yaml,
        package_versions=package_versions
    )


def generate_predict_py(
    files: dict[str, str],
    tell: str | None,
    predict_py: str | None,
) -> str:
    return render(
        "predict_generation/generate",
        files=files,
        tell=tell,
        predict_py=predict_py
    )


def diagnose_error(predict_command: str, error: str) -> str:
    return render("error_diagnosis/diagnose_error", predict_command=predict_command, error=error)


def package_error(predict_command: str, error: str) -> str:
    return render("error_diagnosis/package_error", predict_command=predict_command, error=error)


def get_packages(packages: list[str] | None, cog_contents: str | None) -> str:
    return render("package_info/get_packages", packages=packages, cog_contents=cog_contents)


def cog_predict(predict_py: str) -> str:
    return render("cog_predict/generate", predict_py=predict_py)


order_paths_system = render("order_paths/system")
package_info_system = render("package_info/system")
cog_generation_system = render("cog_generation/system")
predict_generation_system = render("predict_generation/system")
error_diagnosis_system = render("error_diagnosis/system")
cog_fixing_system = render("cog_fixing/system")
predict_fixing_system = render("predict_fixing/system")
cog_predict_system = render("cog_predict/system")


def file_start(filename):
    return f"-- FILE_START: {filename}"


def file_end(filename):
    return f"-- FILE_END: {filename}"
