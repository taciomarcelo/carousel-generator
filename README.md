# carousel-generator

Adiciona legendas estilo Instagram sobre imagens usando Pillow (PIL). Ideal para
gerar carrosséis de imóveis com texto sobreposto de forma padronizada.

O fluxo é simples: você coloca as imagens em `input/`, escreve as legendas em
`captions.yaml` (uma por imagem, na ordem alfabética dos arquivos) e roda o
script. O resultado sai em `output/<timestamp>/`, sem sobrescrever execuções
anteriores, junto com um `report.txt`.

## Requisitos

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) (recomendado) ou `pip`
- Dependências: Pillow e PyYAML

## Instalação

Com **uv** (recomendado — usa o `uv.lock` do projeto):

```bash
uv sync
```

Ou com **pip** + venv:

```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install "pillow>=12.2.0" "pyyaml>=6.0.3"
```

## Uso básico

1. Coloque as imagens em `input/` (formatos aceitos: `.jpg`, `.jpeg`, `.png`, `.webp`).
2. Edite `captions.yaml` com uma legenda por imagem, na **ordem alfabética** dos arquivos.
3. Rode o script:

```bash
# Com uv:
uv run main.py

# Ou, com o venv ativado:
python main.py
```

> A quantidade de legendas em `captions.yaml` deve ser **igual** à quantidade de
> imagens em `input/`. Caso contrário, o script aborta e lista as imagens na
> ordem em que são associadas.

## Comandos e opções (CLI)

Todos os exemplos abaixo funcionam com `python main.py ...` ou `uv run main.py ...`.

```bash
# Processar todas as imagens (padrão)
uv run main.py

# Prévia rápida: processa APENAS a primeira imagem
# (salva também um preview.jpg na pasta da execução)
uv run main.py --preview

# Usar outra pasta de entrada / saída
uv run main.py --input minhas_fotos --output resultados

# Usar outro arquivo de legendas/configuração
uv run main.py --captions outro.yaml

# Sobrescrever a fonte definida no YAML
uv run main.py --font "fonts/Montserrat-Bold.ttf"

# Nome/caminho do relatório dentro da pasta da execução
uv run main.py --report relatorio.txt

# Saída detalhada (fonte usada, arquivos ignorados etc.)
uv run main.py --verbose

# Ajuda completa
uv run main.py --help
```

| Opção        | Padrão          | Descrição                                              |
|--------------|-----------------|--------------------------------------------------------|
| `--input`    | `input`         | Pasta de entrada com as imagens.                       |
| `--output`   | `output`        | Pasta raiz onde as execuções são salvas.               |
| `--captions` | `captions.yaml` | Arquivo YAML de legendas/configuração.                 |
| `--preview`  | (desligado)     | Processa apenas a primeira imagem.                     |
| `--font`     | (do YAML)       | Caminho da fonte `.ttf`, sobrescreve o YAML.           |
| `--report`   | `report.txt`    | Nome/caminho do relatório dentro da pasta da execução. |
| `--verbose`  | (desligado)     | Exibe informações detalhadas.                          |

Argumentos da CLI têm prioridade sobre os valores do `captions.yaml`.

## Configuração (`captions.yaml`)

Todos os parâmetros são opcionais e possuem valores padrão. A lista `captions`
é obrigatória.

```yaml
font: "fonts/Outfit/static/Outfit-SemiBold.ttf"
font_color: "#FFFFFF"
stroke_color: "#000000"
stroke_width: auto          # "auto" ou um inteiro (px)
background_color: "#000000"
background_opacity: 170     # 0..255  (0 = sem fundo)
position: top               # top | center | bottom
safe_margin: 0.05           # fração da menor dimensão da imagem
max_text_width: 0.85        # fração da largura da imagem
line_spacing: auto          # "auto" ou float (multiplicador)
letter_spacing: auto        # "auto" ou inteiro (px)
preview: false

# A associação é feita pela ORDEM ALFABÉTICA dos arquivos em input/.
# A quantidade de legendas deve ser igual à quantidade de imagens.
captions:
  - Vista aérea da fazenda
  - Sede com ampla área verde ao redor
  - Casa principal
  - Área gourmet
```

| Parâmetro            | Padrão      | Descrição                                                |
|----------------------|-------------|----------------------------------------------------------|
| `font`               | (automático)| Caminho da fonte `.ttf`.                                  |
| `font_color`         | `#FFFFFF`   | Cor do texto.                                             |
| `stroke_color`       | `#000000`   | Cor do contorno do texto.                                |
| `stroke_width`       | `auto`      | Espessura do contorno; `auto` = proporcional à fonte.    |
| `background_color`   | `#000000`   | Cor da faixa atrás do texto.                             |
| `background_opacity` | `170`       | Opacidade da faixa (`0..255`). **`0` desativa o fundo.** |
| `position`           | `top`       | Posição vertical do texto: `top`, `center` ou `bottom`.  |
| `safe_margin`        | `0.05`      | Margem de segurança (fração da menor dimensão).          |
| `max_text_width`     | `0.85`      | Largura máxima do texto (fração da largura da imagem).   |
| `line_spacing`       | `auto`      | Espaçamento entre linhas; `auto` ou multiplicador float. |
| `letter_spacing`     | `auto`      | Espaçamento entre letras; `auto` ou inteiro (px).        |
| `preview`            | `false`     | Se `true`, processa apenas a primeira imagem.            |

### Fundo transparente ou desativado

Para remover a faixa escura atrás do texto, use opacidade `0` (nesse caso vale
reforçar o contorno para manter a legibilidade):

```yaml
background_opacity: 0
stroke_color: "#000000"
stroke_width: 3
```

Para apenas deixar o fundo mais discreto, reduza o valor (ex.: `60` bem sutil,
`100` médio).

## Saída

Cada execução cria uma pasta única em `output/`, nomeada com o timestamp:

```
output/
└── 2026-07-01T08-50-12/
    ├── <imagens com legenda>
    ├── report.txt          # relatório da execução
    └── preview.jpg         # apenas no modo --preview
```
