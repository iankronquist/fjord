from django import forms


class OccurrencesComparisonForm(forms.Form):
    """Form for denoting parameters for the Occurrences Comparison report"""
    product = forms.CharField()

    first_version = forms.CharField(required=False)
    first_search_term = forms.CharField(required=False)
    first_start_date = forms.DateField(help_text='yyyy-mm-dd', required=False)
    first_end_date = forms.DateField(help_text='yyyy-mm-dd', required=False)

    second_version = forms.CharField(required=False)
    second_search_term = forms.CharField(required=False)
    second_start_date = forms.DateField(required=False, help_text='yyyy-mm-dd')
    second_end_date = forms.DateField(required=False, help_text='yyyy-mm-dd')

    def clean(self):
        cleaned_data = super(OccurrencesComparisonForm, self).clean()

        # User must specify at least one of version, search term or
        # start date for the first set otherwise the form is invalid.
        required_values = [
            cleaned_data.get(key, '') for key in
            ('first_version', 'first_search_term', 'first_start_date')]

        if not any(required_values):
            raise forms.ValidationError(
                'Must specify at least one of version, search term or start '
                'date for first set.')

        return cleaned_data

class ProductsUpdateForm(forms.Form):
    display_name = forms.CharField(max_length=20)
    slug = forms.CharField(max_length=20)
    enabled_choices = (('1', 'Enable',), ('0', 'Disable',))
    enabled = forms.ChoiceField(widget=forms.RadioSelect, choices=enabled_choices)
    show_choices = (('1', 'Show',), ('0', 'Hide',))
    on_dashboard = forms.ChoiceField(widget=forms.RadioSelect, choices=show_choices)
