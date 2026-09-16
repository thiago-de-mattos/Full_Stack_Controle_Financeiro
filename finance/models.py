from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conta(models.Model):
    TIPO_CHOICES = (
        ('CORRENTE', 'Conta Corrente'),
        ('POUPANCA', 'Poupança'),
        ('CARTEIRA', 'Dinheiro / Carteira'),
        ('INVESTIMENTO', 'Investimentos'),
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contas')
    nome = models.CharField(max_length=100)
    saldo_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CORRENTE')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.usuario.username})"


class Categoria(models.Model):
    TIPO_CHOICES = (
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias')
    nome = models.CharField(max_length=50)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class Lancamento(models.Model):
    TIPO_CHOICES = (
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lancamentos')
    conta = models.ForeignKey(Conta, on_delete=models.CASCADE, related_name='lancamentos')
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='lancamentos')
    
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    data = models.DateField()
    pago = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor}"