from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from finance.services import create_default_categories

from .forms import LoginForm, RegisterForm


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

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        create_default_categories(user)
        login(request, user)  # rotaciona a sessao: barra session fixation
        messages.success(request, f"Bem-vindo, {user.get_short_name()}.")
        return redirect("finance:dashboard")

    return render(request, "accounts/register.html", {"form": form})


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
