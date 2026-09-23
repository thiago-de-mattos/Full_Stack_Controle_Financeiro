# Controle financeiro

App Django de finanças pessoais: contas, categorias, lançamentos,
transferências e orçamento mensal por categoria.

## Rodando

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # pede e-mail, não username
python manage.py runserver
```

Abra `http://127.0.0.1:8000`. Crie uma conta pela tela de cadastro — as 12
categorias padrão já vêm junto.

```bash
python manage.py test             # 61 testes
```

## Os apps

| App | O que guarda |
|---|---|
| `core` | Só coisa abstrata: `TimeStampedModel`, mixins de view, validadores, utilitários de mês. Não gera tabela. |
| `accounts` | `User` customizado (login por e-mail), forms e views de cadastro/login/logout. |
| `finance` | `Account`, `Category`, `Transaction` e as regras de saldo e transferência. |
| `budget` | `Budget`: limite de gasto por categoria e mês. |

Regra que mantém isso organizado: **`core` nunca importa dos outros apps, só o
contrário.** Se der vontade de escrever `from finance.models import ...` dentro
do `core`, aquilo não é core.

## Decisões de modelagem

**Dinheiro é `DecimalField`, nunca `FloatField`.** Float com dinheiro acumula
erro de arredondamento silencioso.

**`amount` é sempre positivo, e o campo `kind` diz a direção.** Dá pra garantir
isso no banco com `CheckConstraint`, o que elimina a classe de bug em que uma
despesa entra positiva por engano. O sinal é aplicado na hora de agregar.

**Transferência são dois lançamentos irmãos**, ligados pelo mesmo
`transfer_group` (UUID): uma saída na conta de origem, uma entrada na de destino.
Assim todo movimento de dinheiro vive na mesma tabela e o cálculo de saldo não
precisa de caso especial. Em relatório de gasto, filtra com
`.without_transfers()` — transferência não é despesa.

**Saldo não é campo, é `annotate`.** `Account.objects.with_balance()` calcula
saldo inicial + movimento liquidado. Guardar um `current_balance` denormalizado
é otimização pra quando doer, e aí com muito cuidado de manter consistente.

**`on_delete=PROTECT`** em conta e categoria: apagar uma categoria não pode
levar junto o histórico de lançamentos.

## Segurança — o que está implementado

- Senha com hash (`set_password`), nunca em texto puro.
- Validadores do Django + dois próprios: lista de senhas comuns **em português**
  (a do Django é só em inglês, então `Senha@123` passava batido) com tradução de
  leetspeak, e limite máximo de tamanho.
- `login()` rotaciona a sessão: bloqueia *session fixation*.
- `?next=` passa por `url_has_allowed_host_and_scheme`: sem isso vira redirect
  aberto, base de phishing.
- Logout só por POST. Se aceitasse GET, um `<img src="/sair/">` deslogaria o
  usuário.
- Toda view filtra por `user=request.user` via `OwnerQuerysetMixin`, e os forms
  limitam o queryset das FKs — senão dá pra forjar um POST com o ID da conta de
  outra pessoa. Tem teste cobrindo exatamente isso (`IsolamentoEntreUsuariosTests`).
- Em produção (`DJANGO_DEBUG=False`): cookies secure, HSTS, SSL redirect.

## O que ficou de fora de propósito

**Brute force no login.** Nada limita tentativas. Um script testa 10 mil senhas
sem obstáculo. Solução prática: `django-axes`.

**Enumeração de e-mail no cadastro.** A mensagem "este e-mail já está
cadastrado" confirma pra um estranho quem tem conta. O jeito rigoroso é aceitar
em silêncio e mandar um e-mail. Pra projeto pessoal o ganho de UX compensa, mas
é escolha consciente.

**Fatura de cartão de crédito.** É a parte realmente difícil: compra parcelada
em N vezes, data de fechamento e de vencimento, fatura como entidade própria.
É onde a maioria desses projetos empaca.

Outras coisas para depois: lançamentos recorrentes, metas, importação de OFX/CSV,
multi-moeda, anexo de comprovante, relatórios com gráfico.

## Antes de publicar

```bash
python manage.py check --deploy
```

Defina `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False` e `DJANGO_ALLOWED_HOSTS` por
variável de ambiente (veja `.env.example`). Troque SQLite por PostgreSQL.
