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

Given the files above, {% if predict_py %}update predict.py{% else %}generate a predict.py file{% endif %}.

Wrap the contents of both files in the strings '{% file_start "filename" %}' and '{% file_end "filename" %}'. Don't output any other text before or after the files since I intend to execute the output that you generate in a Python programming environment.

{% if tell %}
Also make sure to follow these additional instructions: {{ tell }}
{% endif %}
