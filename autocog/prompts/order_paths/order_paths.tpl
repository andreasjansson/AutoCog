Here are the paths:

{% for path in paths %}
{{ path }}
{% endfor %}

End of paths.
{% if readme_contents %}
Below is the readme:

{{ readme_contents }}
{% endif %}
