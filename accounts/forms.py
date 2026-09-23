from datetime import date

from django import forms
from django.contrib.auth import authenticate, password_validation

from core.forms import HtmlDateInput, IsoDateFieldsMixin

from .models import User


class RegisterForm(IsoDateFieldsMixin, forms.ModelForm):
    iso_date_fields = ("birth_date",)

    password1 = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Crie uma senha", "autocomplete": "new-password"}
        ),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Confirmar senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Repita a senha", "autocomplete": "new-password"}
        ),
    )

    class Meta:
        model = User
        fields = ["name", "birth_date", "email"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Como você quer ser chamado", "autocomplete": "name"}
            ),
            "birth_date": HtmlDateInput(),
            "email": forms.EmailInput(
                attrs={"placeholder": "voce@exemplo.com", "autocomplete": "email"}
            ),
        }
        labels = {
            "name": "Nome",
            "birth_date": "Data de nascimento",
            "email": "E-mail",
        }

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if not birth_date:
            return birth_date

        today = date.today()
        if birth_date > today:
            raise forms.ValidationError(
                "Data de nascimento não pode ser no futuro.", code="future_date"
            )

        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
        if age < 16:
            raise forms.ValidationError(
                "Você precisa ter pelo menos 16 anos.", code="too_young"
            )
        if age > 120:
            raise forms.ValidationError(
                "Informe uma data de nascimento válida.", code="invalid_age"
            )
        return birth_date

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Este e-mail já está cadastrado.", code="email_taken"
            )
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                "As senhas não coincidem.", code="password_mismatch"
            )
        return password2

    def _post_clean(self):
        # Aqui self.instance ja tem nome e e-mail preenchidos, entao o
        # UserAttributeSimilarityValidator consegue comparar senha x dados.
        super()._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password1", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    error_messages = {"invalid_login": "E-mail ou senha inválidos."}

    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "voce@exemplo.com",
                "autocomplete": "email",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Sua senha", "autocomplete": "current-password"}
        ),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(
                self.request, username=email.strip().lower(), password=password
            )
            # O ModelBackend ja devolve None pra usuario inativo, entao uma
            # mensagem generica cobre os dois casos sem vazar qual foi.
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"], code="invalid_login"
                )
        return self.cleaned_data

    def get_user(self):
        return self.user_cache
