from djoser import email
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings

class ActivationEmail(email.ActivationEmail):
    template_name = "email/activation.html"

class ConfirmationEmail(email.ConfirmationEmail):
    template_name = "email/confirmation.html"

class PasswordResetEmail(email.PasswordResetEmail):
    template_name = "email/password_reset.html"

class PasswordChangedConfirmationEmail(email.PasswordChangedConfirmationEmail):
    template_name = "email/password_changed_confirmation.html" 