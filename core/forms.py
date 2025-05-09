from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class LifetimeUserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254,
        help_text='Required. Enter a valid email address.'
    )
    reason = forms.CharField(
        widget=forms.Textarea,
        help_text='Please explain why you are registering for a lifetime account (e.g., tester, influencer).'
    )
    company = forms.CharField(
        max_length=100,
        required=False,
        help_text='Optional. Enter your company name if applicable.'
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'reason', 'company', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # The profile will be created in the view
        return user 