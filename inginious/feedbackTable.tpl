{% set title = _("Test details") %}
{{ title }}
{{ "-" * title|length }}

{{ comment }}

{% if tests_data %}
.. raw:: html

   <table style="width:100%; border-collapse: collapse; margin: 20px 0;">
     <thead>
       <tr style="background-color: #f2f2f2;">
         <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ _("Test") }}</th>
         <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ _("Status") }}</th>
         <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ _("Weight") }}</th>
         <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ _("Comment") }}</th>
       </tr>
     </thead>
     <tbody>
   {% set lines = tests_data.split('\\n') %}
   {% for line in lines %}
   {% if line|trim|length > 0 %}
   {% set parts = line.split('|') %}
       <tr>
         <td style="border: 1px solid #ddd; padding: 8px;">{{ _(parts[0]) }}</td>
         <td style="border: 1px solid #ddd; padding: 8px;">{{ _(parts[1]) }}</td>
         <td style="border: 1px solid #ddd; padding: 8px;">{{ parts[2] }}</td>
         <td style="border: 1px solid #ddd; padding: 8px;">{{ _(parts[3]) if parts[3]|trim else "" }}</td>       </tr>
   {% endif %}
   {% endfor %}
     </tbody>
     <tfoot>
       <tr style="font-weight: bold;">
         <td colspan="4" style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ _("TOTAL") }}: {{ passed }}/{{ total_tests }}</td>
       </tr>
     </tfoot>
   </table>
{% else %}
*{{ _("No test details available.") }}*
{% endif %}

