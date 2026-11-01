# Bravo Finance

Painel para acompanhar as faturas do cartão de crédito no seu computador. Você abre o PDF da fatura e o Bravo Finance mostra gastos por categoria, evolução mês a mês, parcelas que ainda vão vencer, assinaturas e os maiores estabelecimentos.

**Fechado no seu computador.** Depois de instalado, o Bravo Finance não usa a internet para nada: não tem conta, nuvem, telemetria, anúncios nem atualização automática, e não pede permissão para acessar outras pastas ou aplicativos. Suas faturas nunca saem da sua máquina.

## Recursos

- Lê faturas em PDF de vários bancos: leitor dedicado para o Santander e um leitor genérico testado com layouts no estilo Nubank, Itaú e Banco do Brasil (veja [Bancos](#bancos)).
- Confere a leitura: compara a soma dos lançamentos com o total da fatura e avisa quando não bate.
- PDF com senha: pergunta a senha na hora e não a guarda.
- Vários cartões e bancos no mesmo mês, somados no painel.
- Cards e painéis personalizáveis, filtros por período, categoria, banco, cartão e tipo, e busca.
- Categorias automáticas, com correção manual que vale para todas as faturas.
- Tema claro e escuro.

## Baixar e instalar

| Seu computador | Baixe | Instale |
|---|---|---|
| **Windows 10 ou 11** (64 bits) | [BravoFinance-Instalador-Windows.exe](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/BravoFinance-Instalador-Windows.exe) | Dê dois cliques e siga o assistente. Não pede senha de administrador. |
| **Mac com chip Apple** (M1, M2, M3...) | [BravoFinance-macOS-AppleSilicon.dmg](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/BravoFinance-macOS-AppleSilicon.dmg) | Abra o arquivo e arraste o Bravo Finance para Aplicativos. |
| **Mac com Intel** | [BravoFinance-macOS-Intel.dmg](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/BravoFinance-macOS-Intel.dmg) | Abra o arquivo e arraste o Bravo Finance para Aplicativos. |
| **Ubuntu, Debian, Mint** (64 bits) | [BravoFinance-Linux-amd64.deb](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/BravoFinance-Linux-amd64.deb) | Dê dois cliques para abrir na central de programas, ou rode `sudo apt install ./BravoFinance-Linux-amd64.deb`. |
| **Outras distribuições Linux** (64 bits) | [BravoFinance-Linux-x86_64.tar.gz](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/BravoFinance-Linux-x86_64.tar.gz) | Extraia e rode `sh instalar.sh` na pasta. Instala só para o seu usuário, sem root. |

Não sabe qual é o seu Mac? Menu Apple > Sobre Este Mac: "Chip Apple" ou "Processador Intel".

Cada instalador já traz tudo o que o app precisa, inclusive o Python: a instalação também funciona sem internet. Depois, abra o **Bravo Finance** pelo menu Iniciar ou pelo atalho na Área de Trabalho (Windows), pelo Launchpad (Mac) ou pelo menu de aplicativos (Linux). Ele não inicia sozinho com o computador.

**Avisos normais na primeira vez.** Os instaladores ainda não têm assinatura digital paga (Microsoft e Apple cobram por ela), então o sistema avisa:
- Windows: em "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**.
- Mac: ao abrir, o macOS diz que não pôde verificar o app. Vá em **Ajustes do Sistema > Privacidade e Segurança**, role até o aviso do Bravo Finance e clique em **Abrir Mesmo Assim**. É uma vez só.

Confira os arquivos baixados com o `SHA256SUMS.txt` de cada [versão](https://github.com/pedrobravorosin/bravo-finance/releases).

### Desinstalar

- Windows: Configurações > Aplicativos > Bravo Finance > Desinstalar. Ele pergunta se você quer apagar também as faturas.
- Mac: arraste o app para o Lixo. As faturas ficam em `~/Library/Application Support/Bravo Finance`; apague a pasta se quiser.
- Linux: `sudo apt remove bravo-finance` (pacote .deb) ou `sh ~/.local/share/bravo-finance-app/desinstalar.sh` (versão portátil).

## Bancos

O leitor genérico procura linhas que começam com uma data (`12/10`, `12 OUT`, `12/10/2026`) e terminam com um valor em reais, e lê total, vencimento, mínimo e limite pelo texto. Ele tenta a página inteira e em colunas e fica com a leitura cuja soma mais se aproxima do total da fatura.

Se a fatura do seu banco não bater, abra uma *issue* descrevendo o layout. **Nunca anexe sua fatura real.** Prefira recriar algumas linhas com valores inventados, como em `tests/gerar_exemplos.py`.

Fatura escaneada ou foto não funciona: use o PDF baixado do app ou do site do banco.

## Onde ficam os dados

| Sistema | Pasta |
|---|---|
| Windows | `%LOCALAPPDATA%\Bravo Finance` |
| macOS | `~/Library/Application Support/Bravo Finance` |
| Linux | `~/.local/share/bravo-finance` |

Dentro dela: `faturas/` (lançamentos lidos, em JSON), `pdfs/` (cópia dos PDFs), `categorias.json` (suas correções) e `preferencias.json` (layout e filtros). Para fazer backup ou levar para outro computador, copie a pasta.

Regras de categoria só suas (por exemplo, nomes de lugares que você frequenta) podem ir em `regras.json`, nessa mesma pasta:

```json
{ "Bares e baladas": "BAR DO ZE|BOTECO DA ESQUINA", "Restaurantes": "CANTINA DA ANA" }
```

## Segurança

- **Sem internet.** Um bloqueio no próprio Python (`sys.addaudithook`, da biblioteca padrão) recusa qualquer conexão, resolução de nome ou pedido HTTP para fora do computador, no servidor e no leitor de PDF. A página tem Content-Security-Policy que só permite o próprio app. No Windows e no Linux, a janela abre com perfil próprio, sem extensões nem sincronização, e com todo endereço externo apontado para um proxy inexistente. No Mac, a janela recusa qualquer endereço que não seja o do app.
- **Sem porta exposta.** O servidor escuta só em 127.0.0.1, numa porta livre escolhida a cada abertura, e desliga quando a janela fecha.
- **Chave por sessão.** Ao abrir, o app recebe do servidor uma chave de uso único (por um canal privado entre os dois processos) e troca por um cookie de sessão `HttpOnly` e `SameSite=Strict`. Sem ele, o servidor não entrega nada, nem para outros programas ou usuários do mesmo computador. Gravações também exigem a mesma origem e um cabeçalho próprio, e o cabeçalho `Host` é conferido.
- **PDF isolado.** Cada fatura é lida num processo separado, com tempo e memória limitados. A senha do PDF passa pela entrada padrão desse processo, nunca pela linha de comando, e não é guardada.
- **Dados só seus.** A pasta de dados é criada só com permissão do seu usuário. Um só Bravo Finance abre por vez.
- **Sem permissões extras.** O app não pede acesso a Documentos, Downloads, iCloud, Google Drive nem a outros apps. Você escolhe o PDF numa janela do próprio sistema.
- **Dependências fixas.** O Python embutido e cada biblioteca têm versão fixa e hash SHA-256 conferido na construção (`ferramentas/versoes.sh` e `app/requirements.txt`).

Encontrou um problema de segurança? Use o aviso privado de vulnerabilidade do GitHub (aba Security) ou abra uma *issue* sem dados pessoais.

## Como funciona

```
app/
  server.py          servidor HTTP local (biblioteca padrão do Python)
  blindagem.py       bloqueio de rede
  leitor.py          leitura dos PDFs com pdfplumber (Santander + genérico)
  leitor_isolado.py  roda o leitor num processo separado e limitado
  categorias.py      regras genéricas de categoria
  abrir.py           abre a janela no Windows e no Linux
  public/            a página (HTML, CSS, JS e Chart.js 4.4.1 local)
instaladores/
  windows/           instalador .exe (NSIS)
  macos/             app nativo (Swift + WebKit) e textos do .dmg
  linux/             atalho, lançador e instalador da versão portátil
ferramentas/         construção dos instaladores, ícone e requirements com hashes
tests/               testes do leitor e de segurança, com faturas fictícias
```

### Desenvolvimento

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes --only-binary=:all: -r app/requirements.txt
BRAVO_DADOS=/tmp/bravo-teste python app/abrir.py      # abre o app com dados de teste
python -m unittest discover tests                      # testes
```

### Construir os instaladores

Os instaladores trazem um Python 3.13 próprio: o oficial da Python Software Foundation no Windows e o [python-build-standalone](https://github.com/astral-sh/python-build-standalone) no Mac e no Linux.

```bash
bash ferramentas/construir-windows.sh   # Linux ou Mac, precisa do NSIS (makensis)
bash ferramentas/construir-linux.sh     # Linux, precisa do dpkg-deb
bash ferramentas/construir-macos.sh     # Mac, precisa das Command Line Tools da Apple
```

Os arquivos saem em `dist/`. O workflow `construir` do GitHub Actions gera e testa os três em máquinas reais de cada sistema; ao criar uma tag `v*`, ele publica a versão.

## Licença

MIT. Veja [LICENSE](LICENSE). O Chart.js (MIT) está incluído em `app/public/vendor`.
