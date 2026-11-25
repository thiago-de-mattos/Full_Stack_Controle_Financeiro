# Visual GEFY

Tema adaptado da referência visual enviada pelo autor: fundo em degradê verde,
cartões escuros, cantos arredondados, ícones e destaque verde na navegação.
A adaptação usa as funções e os dados reais do controle financeiro.

## Telas

- Entrada, login e cadastro com a identidade GEFY.
- Painel com resumo, ranking, histórico, contas, orçamentos e últimos lançamentos.
- Contas em cartões com nome, tipo e saldos reais.
- Listas e formulários com cores e controles consistentes.
- Menu lateral no computador e navegação inferior em telas de até 900 px.
- Histórico e lançamentos em blocos no celular para manter os valores legíveis.

Os SVGs são locais, em `templates/partials/_icon.html`; a marca fica em
`templates/partials/_brand.html`. Não há biblioteca de ícones ou fontes externas.

## Onde alterar

| Arquivo | Responsabilidade |
| --- | --- |
| `static/css/base.css` | Cores, fundo, tipografia e navegação |
| `static/css/components.css` | Botões, painéis, cartões e tabelas responsivas |
| `static/css/forms.css` | Campos, login, cadastro e erros de formulário |
| `static/css/dashboard.css` | Organização dos blocos do painel |
| `static/css/budget.css` | Barras de orçamento |
| `templates/partials/_sidebar.html` | Links do menu e saída da sessão |

As barras usam o elemento HTML `progress`, com valores calculados pelo sistema.
Não é necessário CSS inline para definir sua largura.

A revisão também removeu um comentário de template que aparecia na navegação do
mês e corrigiu o filtro `brl`, que aplicava agrupamento duas vezes. O valor
`1234.50` agora aparece como `R$ 1.234,50`, inclusive se o idioma ativo for inglês.

## Conferência

Execute `python manage.py check`, `python manage.py test` e abra o sistema com
`python manage.py runserver`. Se o navegador mostrar estilos antigos, use Ctrl+F5.

Confira o painel, a troca de mês, as contas, os lançamentos e os formulários.
Use a visualização responsiva do navegador para conferir a barra inferior e os
blocos em telas estreitas. Ela contém as cinco áreas do sistema; o botão Sair
continua no topo do celular e no rodapé do menu do computador.

Validação realizada em banco de testes e dados fictícios:

- 169 testes automatizados passaram.
- Conferência de 49 combinações de página e largura (320, 390, 900 e 1440 px),
  sem rolagem horizontal da página nem comentários de template visíveis.
- Login, filtro mensal, criação/edição/exclusão de conta, navegação móvel e logout
  executados no navegador.

Não há migrações ou dependências novas neste bloco.
