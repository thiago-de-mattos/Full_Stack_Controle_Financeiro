from django import forms

DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y"]


class HtmlDateInput(forms.DateInput):
    
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class IsoDateFieldsMixin:
    iso_date_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.iso_date_fields:
            if name in self.fields:
                self.fields[name].input_formats = DATE_INPUT_FORMATS
