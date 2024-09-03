Below are the contents of the relevant files in the repository:

{% for filename, contents in files.items() %}
{% file_start filename %}
{{ contents }}
{% file_end filename %}
{% endfor %}

{% if predict_py %}
{% file_start "predict.py" %}
{{ predict_py }}
{% file_end "predict.py" %}
{% endif %}

{% if cog_yaml %}
{% file_start "cog.yaml" %}
{{ cog_yaml }}
{% file_end "cog.yaml" %}
{% endif %}

{% if package_versions %}
Here is a list of packages and valid versions: 
{% for package, versions in package_versions.items() %}
{{ package }}: {{ versions | join(',') }}
{% endfor %}
{% endif %}

Given the files above, {% if predict_py %}update predict.py{% else %}generate a predict.py file{% endif %} and {% if cog_yaml %}update cog.yaml{% else %}generate a cog.yaml file{% endif %}.

In cog.yaml, ensure that all Python packages must have pinned versions. Also in cog.yaml, add short comments to describe what parts of the code made you decide on the different parts of cog.yaml. Wrap the contents of both files in the strings '{% file_start "filename" %}' and '{% file_end "filename" %}'. Don't output any other text before or after the files since I intend to execute the output that you generate in a Python programming environment.

{% if tell %}
Also make sure to follow these additional instructions: {{ tell }}
{% endif %}
