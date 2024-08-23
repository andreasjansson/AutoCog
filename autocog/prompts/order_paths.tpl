Given the file paths and readme below, order them by how relevant they are for inference and in particular for building a Replicate prediction model with Cog. After we've done this I will ask you to generate a predict.py and cog.yaml based on the contents of the most relevant files. I want to limit the number of files I have to send to you to not waste time and energy on irrelevant content.

Return the ordered file paths (a maximum of 25 paths) in the following format (and make sure to not include anything else than the list of file paths, no backticks, no "```plaintext", etc.):

most_relevant.py
second_most_relevant.py
third_most_relevant.py
[...]
least_relevant.py

Here are the paths:

{% for path in paths %}
{{ path }}
{% endfor %}

End of paths.
{% if readme_contents %}
Below is the readme:

{{ readme_contents }}
{% endif %}
