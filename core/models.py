from django.db import models


class TimeStampedModel(models.Model):
    """Carimbo de data em toda model concreta. Nao gera tabela propria."""

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
