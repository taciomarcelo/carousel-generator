"""
main.py — Adiciona legendas estilo Instagram sobre imagens usando Pillow (PIL).

Fluxo:
    1. Lê as configurações e legendas de ``captions.yaml``.
    2. Lê todas as imagens da pasta ``input/`` em ordem alfabética.
    3. Valida que a quantidade de legendas é igual à de imagens.
    4. Aplica cada legenda na imagem correspondente (associação pela ordem).
    5. Salva o resultado em ``output/<timestamp>/`` sem sobrescrever execuções
       anteriores, junto com um relatório (``report.txt``) e, opcionalmente,
       um ``preview.jpg``.

Dependências: Pillow e PyYAML.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps

# --------------------------------------------------------------------------- #
# Constantes / valores padrão
# --------------------------------------------------------------------------- #

# Extensões de imagem suportadas (as demais são ignoradas).
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Ordem de preferência para a fonte quando nenhuma é configurada / encontrada.
FONT_CANDIDATES = [
    "fonts/Montserrat-Bold.ttf",
    "fonts/Outfit/static/Outfit-SemiBold.ttf",
    "fonts/Outfit/static/Outfit-Bold.ttf",
]

# Configurações padrão (podem ser sobrescritas pelo YAML e pela CLI).
DEFAULT_CONFIG = {
    "font": None,                 # None => resolvido a partir de FONT_CANDIDATES
    "font_color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": "auto",       # "auto" => proporcional ao tamanho da fonte
    "background_color": "#000000",
    "background_opacity": 170,    # 0..255
    "position": "top",            # top | center | bottom
    "safe_margin": 0.05,          # fração da menor dimensão da imagem
    "max_text_width": 0.85,       # fração da largura da imagem
    "line_spacing": "auto",       # "auto" ou float (multiplicador da altura da linha)
    "letter_spacing": "auto",     # "auto" ou int (px)
    "preview": False,
}


# --------------------------------------------------------------------------- #
# Estruturas auxiliares
# --------------------------------------------------------------------------- #

@dataclass
class ProcessResult:
    """Acumula o resultado de uma execução para o relatório final."""

    started_at: datetime
    run_dir: Path
    total_found: int = 0
    processed: List[str] = field(default_factory=list)
    ignored: List[str] = field(default_factory=list)
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (arquivo, msg)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def log(message: str, *, verbose_only: bool = False, verbose: bool = False) -> None:
    """Imprime uma mensagem de progresso, respeitando o modo verbose."""
    if verbose_only and not verbose:
        return
    print(message, flush=True)


def hex_to_rgba(color: str, opacity: int = 255) -> Tuple[int, int, int, int]:
    """Converte uma cor ``#RRGGBB`` (ou ``#RGB``) em uma tupla RGBA."""
    color = str(color).strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        raise ValueError(f"Cor inválida: '#{color}'. Use o formato #RRGGBB.")
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, max(0, min(255, int(opacity))))


# --------------------------------------------------------------------------- #
# Carregamento de configuração e legendas
# --------------------------------------------------------------------------- #

def load_captions(captions_path: Path) -> Tuple[List[str], dict]:
    """
    Lê o arquivo YAML de legendas/configuração.

    Retorna ``(legendas, config)`` com ``config`` já mesclado aos padrões.
    Levanta ``FileNotFoundError`` ou ``ValueError`` em caso de problema.
    """
    if not captions_path.exists():
        raise FileNotFoundError(
            f"Arquivo de legendas não encontrado: '{captions_path}'."
        )

    with captions_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ValueError(
            "O arquivo de legendas deve ser um mapeamento YAML contendo a "
            "chave 'captions'."
        )

    captions = data.get("captions")
    if not isinstance(captions, list) or not captions:
        raise ValueError("O YAML deve conter uma lista não-vazia em 'captions'.")

    captions = [str(c) for c in captions]

    # Mescla config: começa com os padrões e sobrescreve com chaves conhecidas.
    config = dict(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in data and data[key] is not None:
            config[key] = data[key]

    return captions, config


def load_images(input_dir: Path) -> List[Path]:
    """
    Retorna a lista de imagens suportadas em ``input_dir``, ordenadas
    alfabeticamente. Arquivos não-imagem são ignorados.
    """
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Pasta de entrada não encontrada: '{input_dir}'.")

    return [
        p
        for p in sorted(input_dir.iterdir(), key=lambda p: p.name.lower())
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def list_ignored_files(input_dir: Path) -> List[str]:
    """Lista os arquivos que existem em ``input_dir`` mas não são imagens."""
    return [
        p.name
        for p in sorted(input_dir.iterdir(), key=lambda p: p.name.lower())
        if p.is_file() and p.suffix.lower() not in SUPPORTED_EXTENSIONS
    ]


# --------------------------------------------------------------------------- #
# Resolução de fonte
# --------------------------------------------------------------------------- #

def resolve_font_path(configured_font: Optional[str]) -> Optional[Path]:
    """
    Determina qual arquivo de fonte usar: a fonte configurada (YAML/CLI),
    depois os candidatos padrão. Se nenhum existir, retorna ``None`` (o
    chamador usa a fonte embutida do PIL).
    """
    candidates: List[str] = []
    if configured_font:
        candidates.append(configured_font)
    candidates.extend(FONT_CANDIDATES)

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_font(font_path: Optional[Path], size: int) -> ImageFont.FreeTypeFont:
    """Carrega a fonte no tamanho pedido, com fallback para a fonte padrão."""
    if font_path is not None:
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError:
            pass
    # Fallback: fonte embutida do Pillow.
    try:
        return ImageFont.load_default(size)
    except TypeError:
        # Versões antigas do Pillow não aceitam tamanho em load_default().
        return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# Layout de texto (quebra de linha + ajuste automático de tamanho)
# --------------------------------------------------------------------------- #

def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Largura em pixels de uma linha de texto."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    """
    Quebra ``text`` em linhas que caibam em ``max_width`` pixels. Evita, quando
    possível, deixar uma única palavra sozinha na última linha (mais elegante).
    """
    words = text.split()
    if not words:
        return [""]

    lines: List[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Reequilíbrio: evita a última linha com uma única palavra ("órfã").
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        penult_words = lines[-2].split()
        if len(penult_words) >= 2:
            moved = penult_words.pop()
            new_last = f"{moved} {lines[-1]}"
            if (
                _text_width(draw, " ".join(penult_words), font) <= max_width
                and _text_width(draw, new_last, font) <= max_width
            ):
                lines[-2] = " ".join(penult_words)
                lines[-1] = new_last

    return lines


def fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Optional[Path],
    max_width: int,
    max_height: int,
    line_spacing_factor: float,
    *,
    start_size: int,
    min_size: int = 12,
) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    """
    Reduz o tamanho da fonte até que o bloco de texto (já quebrado em linhas)
    caiba em ``max_width`` x ``max_height``.

    Retorna ``(fonte, linhas, altura_da_linha)``.
    """
    size = start_size
    while size >= min_size:
        font = load_font(font_path, size)
        lines = wrap_text(draw, text, font, max_width)

        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        block_height = int(
            line_height * len(lines)
            + line_height * line_spacing_factor * (len(lines) - 1)
        )
        widest = max((_text_width(draw, line, font) for line in lines), default=0)

        if widest <= max_width and block_height <= max_height:
            return font, lines, line_height

        size -= 2

    # Não coube nem no tamanho mínimo: usa o mínimo mesmo assim.
    font = load_font(font_path, min_size)
    lines = wrap_text(draw, text, font, max_width)
    line_height = sum(font.getmetrics())
    return font, lines, line_height


# --------------------------------------------------------------------------- #
# Renderização da legenda
# --------------------------------------------------------------------------- #

def add_caption(
    image: Image.Image, caption: str, config: dict, font_path: Optional[Path]
) -> Image.Image:
    """
    Desenha ``caption`` sobre uma cópia de ``image`` seguindo o estilo
    configurado (texto branco centralizado, contorno, fundo semi-transparente
    com gradiente suave e escala automática). Retorna a imagem em RGB.
    """
    base = image.convert("RGBA")
    width, height = base.size

    # --- Escala automática de parâmetros proporcionais à imagem -------------
    short_side = min(width, height)
    margin_px = int(short_side * float(config["safe_margin"]))
    max_text_width = int(width * float(config["max_text_width"]))
    max_text_height = int(height * 0.40)          # área máxima para o texto
    start_font_size = max(16, int(height * 0.06))  # fonte inicial proporcional

    # Espaçamento entre linhas.
    if config["line_spacing"] == "auto":
        line_spacing_factor = 0.25
    else:
        line_spacing_factor = float(config["line_spacing"])

    # Camada transparente onde tudo será desenhado.
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- Ajuste de fonte + quebra de linhas ---------------------------------
    font, lines, line_height = fit_font_size(
        draw,
        caption,
        font_path,
        max_text_width,
        max_text_height,
        line_spacing_factor,
        start_size=start_font_size,
    )

    # Espessura do contorno.
    if config["stroke_width"] == "auto":
        stroke_width = max(1, font.size // 18)
    else:
        stroke_width = int(config["stroke_width"])

    # Espaçamento entre letras.
    if config["letter_spacing"] == "auto":
        letter_spacing = 0
    else:
        letter_spacing = int(config["letter_spacing"])

    line_gap = int(line_height * line_spacing_factor)
    block_height = line_height * len(lines) + line_gap * (len(lines) - 1)

    # --- Posição vertical do bloco ------------------------------------------
    position = str(config["position"]).lower()
    if position == "center":
        block_top = (height - block_height) // 2
    elif position == "bottom":
        block_top = height - margin_px - block_height
    else:  # "top" (padrão)
        block_top = margin_px

    # --- Fundo escuro semi-transparente (com gradiente) atrás da legenda ----
    bg_opacity = int(config["background_opacity"])
    if bg_opacity > 0:
        bg_rgba = hex_to_rgba(config["background_color"], bg_opacity)
        pad_x = margin_px
        pad_y = int(line_height * 0.4)
        widest = max((_text_width(draw, ln, font) for ln in lines), default=0)
        box_left = max(0, (width - widest) // 2 - pad_x)
        box_right = min(width, (width + widest) // 2 + pad_x)
        box_top = max(0, block_top - pad_y)
        box_bottom = min(height, block_top + block_height + pad_y)
        _draw_gradient_box(overlay, box_left, box_top, box_right, box_bottom, bg_rgba)

    # --- Desenho das linhas de texto ----------------------------------------
    font_color = hex_to_rgba(config["font_color"])
    stroke_color = hex_to_rgba(config["stroke_color"])

    y = block_top
    for line in lines:
        line_w = _text_width(draw, line, font)
        if letter_spacing and len(line) > 1:
            line_w += letter_spacing * (len(line) - 1)
        x = (width - line_w) // 2

        if letter_spacing:
            _draw_line_with_spacing(
                draw, x, y, line, font, font_color, stroke_color,
                stroke_width, letter_spacing,
            )
        else:
            draw.text(
                (x, y),
                line,
                font=font,
                fill=font_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )
        y += line_height + line_gap

    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def _draw_gradient_box(
    overlay: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    color: Tuple[int, int, int, int],
) -> None:
    """
    Desenha uma faixa retangular com leve gradiente vertical (mais opaca no
    centro, suave nas bordas) atrás da legenda.
    """
    box_w = max(1, right - left)
    box_h = max(1, bottom - top)
    r, g, b, max_alpha = color

    gradient = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)
    center = box_h / 2
    for row in range(box_h):
        dist = abs(row - center) / center if center else 0
        alpha = int(max_alpha * (1.0 - 0.45 * dist))
        grad_draw.line([(0, row), (box_w, row)], fill=(r, g, b, alpha))

    overlay.alpha_composite(gradient, (left, top))


def _draw_line_with_spacing(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    line: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    stroke_fill: Tuple[int, int, int, int],
    stroke_width: int,
    letter_spacing: int,
) -> None:
    """Desenha uma linha caractere a caractere aplicando ``letter_spacing``."""
    cursor = x
    for char in line:
        draw.text(
            (cursor, y),
            char,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        bbox = draw.textbbox((0, 0), char, font=font)
        cursor += (bbox[2] - bbox[0]) + letter_spacing


# --------------------------------------------------------------------------- #
# Saída / diretórios / relatório
# --------------------------------------------------------------------------- #

def create_output_directory(output_root: Path) -> Path:
    """
    Cria (e retorna) a subpasta exclusiva desta execução dentro de
    ``output_root``, nomeada com o timestamp atual em ISO 8601 adaptado para
    nomes de diretório (``:`` -> ``-``). Nunca reutiliza uma pasta existente.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    # Garante unicidade mesmo em execuções no mesmo segundo.
    unique_dir = output_root / timestamp
    suffix = 1
    while unique_dir.exists():
        unique_dir = output_root / f"{timestamp}_{suffix}"
        suffix += 1

    unique_dir.mkdir(parents=True)
    return unique_dir


def save_image(image: Image.Image, dest: Path, original: Path) -> None:
    """Salva ``image`` em ``dest`` preservando formato/qualidade original."""
    ext = original.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        image.save(dest, quality=95, subsampling=0)
    elif ext == ".webp":
        image.save(dest, quality=95, method=6)
    else:  # PNG e afins
        image.save(dest)


def generate_report(result: ProcessResult, config: dict, report_path: Path) -> str:
    """Gera o arquivo de relatório e retorna um resumo curto para o terminal."""
    finished_at = datetime.now()
    duration = (finished_at - result.started_at).total_seconds()

    lines = [
        "=" * 60,
        "RELATÓRIO DE EXECUÇÃO — Gerador de Legendas",
        "=" * 60,
        f"Data/hora da execução : {result.started_at.isoformat(timespec='seconds')}",
        f"Duração               : {duration:.1f}s",
        f"Pasta da execução     : {result.run_dir}",
        f"Modo preview          : {'sim' if config.get('preview') else 'não'}",
        "",
        f"Imagens encontradas   : {result.total_found}",
        f"Imagens processadas   : {len(result.processed)}",
        f"Arquivos ignorados    : {len(result.ignored)}",
        f"Erros                 : {len(result.errors)}",
        "",
        "-- Arquivos processados --",
    ]
    lines += [f"  [OK] {name}" for name in result.processed] or ["  (nenhum)"]

    lines += ["", "-- Arquivos ignorados --"]
    lines += [f"  [--] {name}" for name in result.ignored] or ["  (nenhum)"]

    lines += ["", "-- Erros --"]
    if result.errors:
        lines += [f"  [ERRO] {name}: {msg}" for name, msg in result.errors]
    else:
        lines += ["  (nenhum)"]

    lines.append("=" * 60)
    content = "\n".join(lines) + "\n"
    report_path.write_text(content, encoding="utf-8")

    # Resumo compacto para o terminal.
    return (
        f"\nResumo: {len(result.processed)}/{result.total_found} imagem(ns) "
        f"processada(s), {len(result.ignored)} ignorada(s), "
        f"{len(result.errors)} erro(s).\n"
        f"Saída: {result.run_dir}"
    )


# --------------------------------------------------------------------------- #
# Orquestração do processamento
# --------------------------------------------------------------------------- #

def process_images(
    images: List[Path],
    captions: List[str],
    config: dict,
    run_dir: Path,
    result: ProcessResult,
    *,
    verbose: bool = False,
) -> None:
    """
    Aplica cada legenda à imagem correspondente e salva na pasta da execução.

    Em modo preview, apenas a primeira imagem é processada e também salva como
    ``preview.jpg``.
    """
    font_path = resolve_font_path(config.get("font"))
    if font_path:
        log(f"Fonte: {font_path}", verbose_only=True, verbose=verbose)
    else:
        log("Fonte: (padrão embutida do Pillow)", verbose_only=True, verbose=verbose)

    preview_mode = bool(config.get("preview"))
    to_process = images[:1] if preview_mode else images

    total = len(to_process)
    for idx, image_path in enumerate(to_process, start=1):
        caption = captions[idx - 1]
        log(f'[{idx}/{total}] {image_path.name}  <-  "{caption}"')

        try:
            with Image.open(image_path) as img:
                img.load()
                img = ImageOps.exif_transpose(img)  # corrige orientação EXIF
                rendered = add_caption(img, caption, config, font_path)

            dest = run_dir / image_path.name
            save_image(rendered, dest, image_path)
            result.processed.append(image_path.name)

            if preview_mode:
                preview_path = run_dir / "preview.jpg"
                rendered.save(preview_path, quality=95, subsampling=0)
                log(f"  preview salvo em {preview_path}",
                    verbose_only=True, verbose=verbose)

        except Exception as exc:  # noqa: BLE001 - reportamos qualquer falha
            result.errors.append((image_path.name, str(exc)))
            log(f"  ERRO ao processar {image_path.name}: {exc}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Define e interpreta os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Adiciona legendas estilo Instagram sobre imagens (Pillow).",
    )
    parser.add_argument("--input", default="input", help="Pasta de entrada (padrão: input)")
    parser.add_argument("--output", default="output", help="Pasta raiz de saída (padrão: output)")
    parser.add_argument("--captions", default="captions.yaml", help="Arquivo YAML (padrão: captions.yaml)")
    parser.add_argument("--preview", action="store_true", help="Processa apenas a primeira imagem")
    parser.add_argument("--font", default=None, help="Sobrescreve a fonte definida no YAML")
    parser.add_argument("--report", default="report.txt", help="Nome/caminho do relatório dentro da pasta da execução")
    parser.add_argument("--verbose", action="store_true", help="Exibe informações detalhadas")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Ponto de entrada. Retorna 0 em sucesso, 1 em erro de configuração."""
    args = parse_args(argv)

    input_dir = Path(args.input)
    output_root = Path(args.output)
    captions_path = Path(args.captions)

    # --- Carregamento de legendas/config (com tratamento de erros) ----------
    try:
        captions, config = load_captions(captions_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    # CLI tem prioridade sobre o YAML.
    if args.preview:
        config["preview"] = True
    if args.font:
        config["font"] = args.font

    # --- Carregamento das imagens -------------------------------------------
    try:
        images = load_images(input_dir)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    ignored = list_ignored_files(input_dir)

    if not images:
        print(f"ERRO: nenhuma imagem suportada encontrada em '{input_dir}'.", file=sys.stderr)
        print(f"      Formatos aceitos: {', '.join(sorted(SUPPORTED_EXTENSIONS))}", file=sys.stderr)
        return 1

    # --- Validação: quantidade de legendas == quantidade de imagens ---------
    if len(captions) != len(images):
        print(
            f"ERRO: quantidade de legendas ({len(captions)}) diferente da "
            f"quantidade de imagens ({len(images)}).",
            file=sys.stderr,
        )
        print("      Imagens (ordem alfabética):", file=sys.stderr)
        for i, img in enumerate(images, start=1):
            print(f"        {i}. {img.name}", file=sys.stderr)
        return 1

    # --- Pasta exclusiva desta execução -------------------------------------
    run_dir = create_output_directory(output_root)
    result = ProcessResult(
        started_at=datetime.now(), run_dir=run_dir, total_found=len(images)
    )
    result.ignored = ignored

    log(f"Pasta desta execução: {run_dir}")
    if config.get("preview"):
        log("Modo PREVIEW ativado: apenas a primeira imagem será processada.")
    if ignored:
        log(
            f"{len(ignored)} arquivo(s) ignorado(s): {', '.join(ignored)}",
            verbose_only=True,
            verbose=args.verbose,
        )

    # --- Processamento -------------------------------------------------------
    process_images(images, captions, config, run_dir, result, verbose=args.verbose)

    # --- Relatório -----------------------------------------------------------
    report_path = run_dir / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary = generate_report(result, config, report_path)

    print(summary)
    print(f"Relatório: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
