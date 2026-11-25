from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
import logging
from django.db import IntegrityError, transaction
from core.models import Organization
from .models import Profile

from finance.services import create_default_categories
from .forms import LoginForm, RegisterForm

logger = logging.getLogger(__name__)

def _safe_redirect_target(request):
    """So aceita destino interno. Sem isso, ?next=http://site-falso vira
    redirect aberto, que e base de phishing."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return None


def register_view(request):
    if request.user.is_authenticated:
        return redirect("finance:dashboard")

    form = RegisterForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()

                organization = Organization.objects.create(
                    name=form.cleaned_data["organization_name"]
                )

                Profile.objects.create(
                    user=user,
                    organization=organization,
                    role=Profile.Role.ADMIN,
                )

                create_default_categories(user)

        except IntegrityError:
            logger.exception("Falha de integridade ao concluir o cadastro.")
            form.add_error(
                None,
                "Não foi possível concluir o cadastro. "
                "Atualize a página e tente novamente.",
            )

        else:
            login(request, user)
            messages.success(
                request,
                f"Bem-vindo, {user.get_short_name()}.",
            )
            return redirect("finance:dashboard")

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("finance:dashboard")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(_safe_redirect_target(request) or "finance:dashboard")

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@login_required
@require_POST
def logout_view(request):
    # So POST. Se aceitasse GET, um <img src="/sair/"> deslogaria o usuario.
    logout(request)
    messages.info(request, "Você saiu da sua conta.")
    return redirect("accounts:login")
