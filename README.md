# Bravo Finance (app Financeiro)

Painel local para acompanhar as faturas do cartão de crédito. Você envia o PDF da fatura e ele mostra gráficos e tabelas: gastos por categoria, evolução mês a mês, parcelas que ainda vão vencer, assinaturas e os maiores estabelecimentos.

**Privacidade em primeiro lugar.** Tudo roda no seu computador. O PDF é lido localmente em Python, o servidor só aceita conexões da própria máquina (127.0.0.1) e a página não carrega nada da internet. Não há conta, nuvem, telemetria nem anúncios.

## Recursos

- Lê faturas em PDF de vários bancos: leitor dedicado para o Santander e um leitor genérico testado com layouts no estilo Nubank, Itaú e Banco do Brasil (veja [Bancos](#bancos)).
- Confere a leitura: compara a soma dos lançamentos com o total da fatura e avisa quando não bate.
- PDF com senha: pergunta a senha na hora e não a guarda.
- Vários cartões e bancos no mesmo mês, somados no painel.
- Cards e painéis personalizáveis (o que cada card mostra, nome, ordem, largura, esconder).
- Filtros por período, categoria, banco, cartão, à vista ou parcelado e busca.
- Categorias automáticas, com correção manual que vale para todas as faturas.
- Tema claro e escuro, funciona em telas pequenas.

## Baixar e instalar

| Seu computador | 1. Baixe | 2. Instale |
|---|---|---|
| **Windows 10 ou 11** | [Financeiro-Windows.zip](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/Financeiro-Windows.zip) | Extraia o zip e dê dois cliques em **Instalar.bat** |
| **Mac** (macOS 11 ou mais novo) | [Financeiro-macOS.zip](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/Financeiro-macOS.zip) | Abra o zip, clique com o botão direito em **Instalar.command** e escolha **Abrir** |
| **Linux** | [Financeiro-Linux.tar.gz](https://github.com/pedrobravorosin/bravo-finance/releases/latest/download/Financeiro-Linux.tar.gz) | Extraia e rode `bash financeiro/instaladores/linux/instalar.sh` |

**3. Abra** o **Financeiro** pelo atalho na Área de Trabalho ou no Menu Iniciar (Windows), pelo Dock ou Launchpad (Mac) ou pelo menu de aplicativos (Linux). Não precisa criar conta.

**Avisos normais na primeira vez**
- Windows: se aparecer "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**. O aviso aparece porque o instalador não tem assinatura digital paga.
- Mac: se o macOS pedir para instalar as "ferramentas de linha de comando", aceite, espere terminar e abra o **Instalar.command** de novo.

Cada pacote traz um `LEIA-ME.txt` com o passo a passo. Todas as versões ficam na página de [Releases](https://github.com/pedrobravorosin/bravo-finance/releases), com o `SHA256SUMS.txt` para conferir os arquivos.

### Detalhes dos instaladores

| Sistema | Pacote | Como funciona |
|---|---|---|
| Windows 10 e 11 | `Financeiro-Windows.zip` | `Instalar.bat`. Traz o Python oficial e as bibliotecas: instala sem internet e sem administrador. Abre numa janela própria do Edge. |
| macOS 11+ | `Financeiro-macOS.zip` | `Instalar.command`. Usa só ferramentas da Apple (Python 3 e Swift das Command Line Tools) e cria um app nativo com WebKit. |
| Linux | `Financeiro-Linux.tar.gz` | `instaladores/linux/instalar.sh`. Usa o Python do sistema num ambiente próprio e cria o atalho no menu. |

Nenhum instalador configura o app para iniciar com o computador: ele liga quando você abre e desliga quando você fecha.

Para instalar direto do código: clone o repositório e rode `bash instaladores/macos/instalar.sh` ou `bash instaladores/linux/instalar.sh`.

## Bancos

O leitor genérico procura linhas que começam com uma data (`12/10`, `12 OUT`, `12/10/2026`) e terminam com um valor em reais, e lê total, vencimento, mínimo e limite pelo texto. Ele tenta a página inteira e em colunas e fica com a leitura cuja soma mais se aproxima do total da fatura.

Se a fatura do seu banco não bater, abra uma *issue* descrevendo o layout. **Nunca anexe sua fatura real.** Prefira recriar algumas linhas com valores inventados, como em `tests/gerar_exemplos.py`.

Fatura escaneada ou foto não funciona: use o PDF baixado do app ou do site do banco.

## Onde ficam os dados

| Sistema | Pasta |
|---|---|
| Windows | `%LOCALAPPDATA%\Financeiro\dados` |
| macOS | `~/Library/Application Support/Financeiro/dados` |
| Linux | `~/.local/share/financeiro/dados` |

Dentro dela: `faturas/` (lançamentos lidos, em JSON), `pdfs/` (cópia dos PDFs), `categorias.json` (suas correções) e `preferencias.json` (layout e filtros). Para fazer backup ou levar para outro computador, copie a pasta.

Regras de categoria só suas (por exemplo, nomes de lugares que você frequenta) podem ir em `dados/regras.json`, que não faz parte do código:

```json
{ "Bares e baladas": "BAR DO ZE|BOTECO DA ESQUINA", "Restaurantes": "CANTINA DA ANA" }
```

## Como funciona

```
app/
  server.py      servidor HTTP local (biblioteca padrão do Python), só em 127.0.0.1
  leitor.py      leitura dos PDFs com pdfplumber (Santander + genérico)
  categorias.py  regras genéricas de categoria
  abrir.py       abre a janela no Windows e no Linux e desliga o servidor ao fechar
  public/        a página (HTML, CSS, JS e Chart.js 4.4.1 local)
instaladores/    Windows (PowerShell), macOS (app Swift + WebKit), Linux (shell + .desktop)
ferramentas/     geração de requirements com hashes e dos pacotes de instalação
tests/           testes com faturas fictícias
```

Dependências: Python 3.9 a 3.14 e `pdfplumber` com versões fixas e conferidas por hash em `app/requirements.txt`. Para atualizar, edite `ferramentas/gerar_requirements.py`, rode-o e rode os testes.

### Desenvolvimento

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes --only-binary=:all: -r app/requirements.txt
FATURAS_DATA=/tmp/financeiro-teste python app/server.py   # abre em http://localhost:47821
pip install reportlab && python -m unittest discover tests  # reportlab só para gerar os PDFs de teste
bash ferramentas/empacotar.sh                               # gera os pacotes em dist/
```

Ao criar uma tag `v*`, o GitHub Actions roda os testes e publica os três pacotes na página de Releases.

## Segurança

- O servidor só escuta em 127.0.0.1, confere o cabeçalho `Host` e exige um cabeçalho próprio para gravar (bloqueia outros sites abertos no navegador).
- A página usa Content-Security-Policy restrita e não carrega recursos externos.
- As pastas de dados são criadas só com permissão do seu usuário.
- Encontrou um problema de segurança? Abra uma *issue* sem dados pessoais ou use o aviso privado de vulnerabilidade do GitHub.

## Licença

MIT. Veja [LICENSE](LICENSE). O Chart.js (MIT) está incluído em `app/public/vendor`.
