import os

from django import forms

ALLOWED_EXTENSIONS = ('.txt', '.md')
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB


class UploadForm(forms.Form):
    title = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={
            'class': 'input', 'placeholder': 'Title (optional, defaults to file name)'}),
    )
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'input', 'accept': '.txt,.md'}),
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Only .txt and .md files are supported for now.')
        if f.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError('File is too large (max 2 MB).')
        if f.size == 0:
            raise forms.ValidationError('That file is empty.')
        return f
