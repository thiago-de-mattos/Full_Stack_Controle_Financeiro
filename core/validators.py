import re
import unicodedata

from django.core.exceptions import ValidationError

# O CommonPasswordValidator do Django usa uma lista de 20 mil senhas em ingles.
# "Senha@123" e "mudar123" passam direto por ela. Esta lista cobre o basico
# do que brasileiro costuma usar como senha.
PALAVRAS_FRACAS_PT = {
    "senha", "senhas", "minhasenha", "novasenha", "mudar", "mudarsenha",
    "usuario", "administrador", "acesso", "entrar", "segredo", "teste",
    "amor", "amordaminhavida", "teamo", "amoreterno", "paixao", "saudade",
    "coracao", "carinho", "princesa", "princesinha", "gatinha", "gatinho",
    "familia", "mamae", "papai", "filha", "filho", "bebe", "anjo",
    "deus", "deusefiel", "deusnocomando", "jesus", "jesuscristo", "fe", "paz",
    "brasil", "brasileiro", "saopaulo", "riodejaneiro", "flamengo", "vasco",
    "corinthians", "palmeiras", "santos", "botafogo", "gremio", "cruzeiro",
    "internacional", "fluminense", "atletico", "bahia", "sport",
    "felicidade", "sucesso", "vitoria", "liberdade", "esperanca", "sonho",
    "trabalho", "escola", "faculdade", "computador", "celular", "casa",
}


# Troca de letra por simbolo nao esconde nada: 's3nha' e 'senha'.
LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
     "@": "a", "$": "s", "!": "i"}
)


class CommonPortuguesePasswordValidator:
    """Rejeita palavra comum em portugues, mesmo disfarçada com números e
    símbolos: 'Senha@123', 's3nha' e '@mor1' caem todas aqui."""

    def _raizes(self, password):
        """Gera as formas possiveis da senha e devolve todas pra comparacao."""
        texto = unicodedata.normalize("NFKD", password.lower())
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        sem_cauda = re.sub(r"[\W\d_]+$", "", texto)

        raizes = set()
        for forma in {texto, sem_cauda}:
            raizes.add(re.sub(r"[^a-z]", "", forma))
            raizes.add(re.sub(r"[^a-z]", "", forma.translate(LEET)))
        return raizes

    def validate(self, password, user=None):
        if self._raizes(password) & PALAVRAS_FRACAS_PT:
            raise ValidationError(
                "Essa senha é previsível demais. Trocar letra por símbolo ou "
                "colocar números no fim não ajuda: use uma frase.",
                code="password_too_common_pt",
            )

    def get_help_text(self):
        return (
            "Sua senha não pode ser uma palavra comum com números ou símbolos "
            "nas pontas."
        )


class MaximumLengthValidator:
    """Django faz hash de tudo, mas senha gigante vira ataque de CPU."""

    def __init__(self, max_length=128):
        self.max_length = max_length

    def validate(self, password, user=None):
        if len(password) > self.max_length:
            raise ValidationError(
                f"A senha pode ter no máximo {self.max_length} caracteres.",
                code="password_too_long",
            )

    def get_help_text(self):
        return f"Sua senha pode ter no máximo {self.max_length} caracteres."
