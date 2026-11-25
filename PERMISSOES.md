# Permissões financeiras

Cada usuário precisa de um perfil com organização e papel válido.
Todas as operações abaixo são limitadas à organização desse perfil.

| Operação | Administrador | Operador |
| --- | --- | --- |
| Consultar registros e dashboard | Sim | Sim |
| Cadastrar contas, categorias, lançamentos e orçamentos | Sim | Sim |
| Editar registros comuns | Sim | Sim |
| Registrar transferências | Sim | Sim |
| Excluir registros e transferências | Sim | Não |
| Acessar outra organização | Não | Não |

As mesmas regras valem nas páginas HTML e nos endpoints financeiros.
Esconder o botão não substitui a autorização no servidor: URLs e requisições
diretas também são verificadas. A API devolve 403 para operações proibidas.
Usuários autorizados recebem 404 ao tentar acessar objetos de outra organização.

Contas e categorias com lançamentos não podem ser excluídas. Transferências
são excluídas como um par; editar apenas uma movimentação continua bloqueado.

O papel Administrador pertence à organização. Ele não concede `is_staff`,
`is_superuser` nem acesso automático ao Django Admin. O Django Admin continua
sendo uma ferramenta interna de manutenção, com suas próprias permissões.
Por enquanto, a atribuição de papéis é feita nele por quem administra o sistema.

Regras compartilhadas: `core/permissions.py`.
Permissão dos endpoints financeiros: `finance/permissions.py`.
Botões nas páginas: `core/context_processors.py` e templates.
Testes das permissões: `finance/test_permissions.py`.
