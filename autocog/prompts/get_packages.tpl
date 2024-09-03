You now need to extract the necessary packages to run the model. Include the version only if explicitly listed. Return the packages in the following format (and make sure to not include anything else than the packages, no backticks, no "```plaintext", etc.):

package1==v1.v1.v1
package2
package3==v3.v3.v3
[...]
packagen

{% if cog_content %}
Here are the contents of cog.yaml: 
{{ cog_contents }}
{% endif %}

Don't output anything else since I intend to parse the output and use it in a programmatic pipeline.
