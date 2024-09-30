{% if packages %}
Here are all of the imported packages:
{% for package in packages %}
- {{ package }}
{% endfor %}
{% else %}
No packages were found.
{% endif %}

{% if cog_content %}
Here are the contents of cog.yaml: 
{{ cog_contents }}
{% endif %}
