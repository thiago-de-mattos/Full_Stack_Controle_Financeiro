from datetime import date, datetime

from django.utils import timezone


def current_month():
    return timezone.localdate().replace(day=1)


def month_from_request(request, param="mes"):
    """Le ?mes=YYYY-MM da querystring. Cai no mes atual se vier lixo."""
    raw = request.GET.get(param)
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m").date()
        except ValueError:
            pass
    return current_month()


def shift_month(ref: date, delta: int) -> date:
    total = ref.year * 12 + (ref.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


def month_label(ref: date) -> str:
    nomes = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    return f"{nomes[ref.month - 1]} de {ref.year}"
