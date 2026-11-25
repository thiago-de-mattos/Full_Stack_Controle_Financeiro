# Controle financeiro

Mini-SaaS Django de controle financeiro por organização: contas, categorias,
lançamentos, transferências, orçamentos, dashboard e API REST com DRF.

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
python manage.py test             # suíte completa
```

## Os apps

| App | O que guarda |
|---|---|
| `core` | Organização, permissões compartilhadas, mixins, validações e utilitários. |
| `accounts` | Usuário por e-mail, perfil com organização e papel, cadastro e autenticação. |
| `finance` | `Account`, `Category`, `Transaction` e as regras de saldo e transferência. |
| `budget` | `Budget`: limite de gasto por categoria e mês. |

As regras financeiras ficam em `finance` e `budget`. O `core` concentra o que
é compartilhado; suas permissões consultam o perfil definido em `accounts`.

## Organização de templates e CSS

```
templates/
├── base.html                   esqueleto: <head>, sidebar, bloco de conteúdo
├── partials/                   fragmentos incluídos com {% include %}
│   ├── _sidebar.html
│   ├── _mensagens.html
│   ├── _nav_mes.html           setas de mês (painel, lançamentos, orçamentos)
│   ├── _campos_form.html       renderiza qualquer form com o mesmo HTML
│   └── _barra_orcamento.html   barra de progresso (painel e orçamentos)
├── layouts/                    templates-mãe que outras telas estendem
│   ├── form_page.html
│   └── confirm_delete.html
├── accounts/
├── finance/
└── budget/
```

`partials/` é o que você **inclui**; `layouts/` é o que você **estende**. O
underscore no começo do nome não significa nada pro Django — é só um aviso
pra quem lê: "isto não é uma página, não tente abrir por URL".

### A regra de nome que evita 90% do "minha tela não carrega"

As class-based views procuram o template sozinhas, num caminho fixo:

| View | Template que ela procura |
|---|---|
| `ListView` | `finance/account_list.html` |
| `CreateView` / `UpdateView` | `finance/account_form.html` |
| `DeleteView` | `finance/account_confirm_delete.html` |
| `DetailView` | `finance/account_detail.html` |

O padrão é `<app>/<model em minúsculo>_<sufixo>.html`. Um arquivo chamado
`list.html` nunca vai ser encontrado. Seguindo a convenção, nenhuma view
precisa de `template_name` — hoje a palavra não aparece uma vez sequer no
projeto. `ConvencaoDeTemplateTests` trava isso: renomeou arquivo, o teste
quebra antes da tela.

### CSS por arquivo

```
static/css/
├── base.css          tokens, reset, tipografia, esqueleto da página
├── components.css    botões, painéis, tabelas, mensagens, navegação de mês
├── forms.css         campos, labels, erros, filtros
├── dashboard.css     o saldo grande do painel
└── budget.css        barra de progresso do orçamento
```

`base.css` e `components.css` carregam em toda tela. O resto entra por página,
pelo bloco do `base.html`:

```django
{% block extra_css %}
  <link rel="stylesheet" href="{% static 'css/dashboard.css' %}">
  <link rel="stylesheet" href="{% static 'css/budget.css' %}">
{% endblock %}
```

Como decidir onde uma regra mora: **se mais de uma tela usa, é componente.**
Se só uma usa, vai no arquivo daquela tela. Quando um estilo de tela começar a
ser copiado pra outra, aí sim ele sobe pra `components.css` — não antes.

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
- Telas, API e relatórios filtram pela organização do perfil. Os relacionamentos
  também ficam limitados à mesma organização. O campo `user` registra o criador.
- Operadores consultam, criam e editam; administradores da organização também
  excluem. Nenhum desses papéis concede acesso ao Django Admin.
- No Django Admin, contas, categorias, lançamentos e orçamentos são apenas
  consultados. Escritas passam pelas telas ou API para respeitar as validações.
- Conflitos de gravação voltam ao formulário sem salvar dados parcialmente.
- Respostas autenticadas recebem `Cache-Control: private, no-store`.
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
variável de ambiente. Em produção, chave fraca/padrão ou hosts ausentes/com
asterisco impedem a inicialização. O arquivo `.env.example` é uma referência: o
projeto não carrega `.env` automaticamente.

Consulte [SEGURANCA.md](SEGURANCA.md) antes da implantação; inclui HTTPS/proxy
e as pendências que ainda precisam ser resolvidas para uso público.

## Documentação da P2

- [API_REST.md](API_REST.md): endpoints, JSON, validações e permissões.
- [DASHBOARD_RELATORIOS.md](DASHBOARD_RELATORIOS.md): métricas e exportação CSV.
- [SEGURANCA.md](SEGURANCA.md): revisão dos fluxos e configuração de produção.
