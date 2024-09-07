from django import forms

class UploadFileForm(forms.Form):
    standard_pdf = forms.FileField(label="Security Standard PDF")
    target_pdf = forms.FileField(label="Target Document PDF")
