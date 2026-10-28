# -*- coding: utf-8 -*-
"""figura.py: desenha o caminho da falha como SVG, só com biblioteca padrão.

O spec fica em "caminho_falha" no incidente.json:

  {"passos": [
     {"tipo": "no",   "titulo": "Origem", "sub": "o que aconteceu ali", "nota": "19/10 17:30"},
     {"tipo": "seta", "rotulo": "carga diária"},
     {"tipo": "seta", "rotulo": "job de transformação", "alerta": "FALHA"},
     {"tipo": "no",   "titulo": "Destino", "sub": "...", "alerta": true}
  ]}

"no" é uma caixa; "seta" liga a caixa anterior à seguinte. "alerta" (true ou um texto curto) marca
em vermelho o ponto em que a falha aconteceu. "nota" aparece ao lado da caixa, "rotulo" ao lado da seta.
Não há ícones de provedores: o fluxo é neutro e não depende de licença de terceiros.

A largura do texto é estimada por uma heurística por caractere, suficiente para quebrar as linhas
sem estourar as caixas em fontes sem serifa comuns.
"""
import unicodedata
from html import escape

# Largura média relativa ao tamanho da fonte, por classe de caractere.
_ESTREITOS = set("iljtfrI.,;:!|'()[]{}/\\`")
_LARGOS = set("mwMW@%")
_MAIUSC_LARGOS = set("CDGHNOQUVXAKR&")


def largura(texto, tam, negrito=False):
    total = 0.0
    for ch in texto:
        base = unicodedata.normalize("NFD", ch)[0]
        if base == " ":
            f = 0.28
        elif base in _ESTREITOS:
            f = 0.30
        elif base in _LARGOS:
            f = 0.86
        elif base in _MAIUSC_LARGOS:
            f = 0.72
        elif base.isupper():
            f = 0.64
        elif base.isdigit():
            f = 0.56
        else:
            f = 0.53
        total += f
    return total * tam * (1.07 if negrito else 1.0)


def quebrar(texto, max_px, tam, negrito=False):
    """Quebra o texto em linhas que caibam em max_px, palavra a palavra."""
    linhas, atual = [], ""
    for palavra in str(texto or "").split():
        tentativa = f"{atual} {palavra}".strip()
        if largura(tentativa, tam, negrito) <= max_px:
            atual = tentativa
            continue
        if atual:
            linhas.append(atual)
        # palavra maior que a linha inteira: corta por caractere
        while largura(palavra, tam, negrito) > max_px:
            corte = len(palavra)
            while corte > 1 and largura(palavra[:corte] + "-", tam, negrito) > max_px:
                corte -= 1
            linhas.append(palavra[:corte] + "-")
            palavra = palavra[corte:]
        atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


ESTILO = """
svg.cf{--cf-fundo:#ffffff;--cf-caixa:#f5f6f3;--cf-borda:#c9cfca;--cf-texto:#1c2321;--cf-suave:#5b6662;
--cf-seta:#7d8883;--cf-acento:#1f6f68;--cf-alerta:#b42318;--cf-alerta-fundo:#fcebe9;--cf-tag-texto:#ffffff;
font-family:Inter,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
@media (prefers-color-scheme:dark){svg.cf{--cf-fundo:#1b201f;--cf-caixa:#232a28;--cf-borda:#3b4542;
--cf-texto:#e6eae8;--cf-suave:#a4afab;--cf-seta:#8b9793;--cf-acento:#62b5aa;--cf-alerta:#f27a6f;
--cf-alerta-fundo:#3b2422;--cf-tag-texto:#1b201f}}
@media print{svg.cf{--cf-fundo:#ffffff;--cf-caixa:#f5f6f3;--cf-borda:#c9cfca;--cf-texto:#1c2321;
--cf-suave:#5b6662;--cf-seta:#7d8883;--cf-acento:#1f6f68;--cf-alerta:#b42318;--cf-alerta-fundo:#fcebe9;
--cf-tag-texto:#ffffff}}
svg.cf .fundo{fill:var(--cf-fundo)}
svg.cf .caixa{fill:var(--cf-caixa);stroke:var(--cf-borda);stroke-width:1}
svg.cf .caixa.alerta{fill:var(--cf-alerta-fundo);stroke:var(--cf-alerta);stroke-width:2}
svg.cf .barra{fill:var(--cf-acento)}
svg.cf .barra.alerta{fill:var(--cf-alerta)}
svg.cf .titulo{fill:var(--cf-texto);font-weight:650;font-size:15px}
svg.cf .cabeca{fill:var(--cf-texto);font-weight:650;font-size:16px}
svg.cf .sub{fill:var(--cf-suave);font-size:13px}
svg.cf .nota{fill:var(--cf-suave);font-size:12px;font-style:italic}
svg.cf .nota.alerta{fill:var(--cf-alerta);font-style:normal;font-weight:600}
svg.cf .guia{stroke:var(--cf-borda);stroke-width:1;stroke-dasharray:3 3}
svg.cf .guia.alerta{stroke:var(--cf-alerta)}
svg.cf .linha{stroke:var(--cf-seta);stroke-width:2;fill:none}
svg.cf .linha.alerta{stroke:var(--cf-alerta);stroke-width:2.5}
svg.cf .ponta{fill:var(--cf-seta)}
svg.cf .ponta.alerta{fill:var(--cf-alerta)}
svg.cf .rotulo{fill:var(--cf-suave);font-size:12.5px}
svg.cf .rotulo.alerta{fill:var(--cf-alerta);font-weight:600}
svg.cf .tag{fill:var(--cf-alerta)}
svg.cf .tag-texto{fill:var(--cf-tag-texto);font-size:11px;font-weight:700;letter-spacing:.04em}
svg.cf .legenda{fill:var(--cf-suave);font-size:12px}
""".strip()

# Geometria
LARG = 760
MARGEM = 24
CX_X, CX_L = MARGEM, 480          # caixa
NOTA_X = CX_X + CX_L + 28          # coluna de notas
NOTA_L = LARG - MARGEM - NOTA_X
PAD_H, PAD_V = 18, 14
T_TIT, T_SUB, T_NOTA, T_ROT, T_TAG = 15, 13, 12, 12.5, 11
LH_TIT, LH_SUB, LH_NOTA, LH_ROT = 20, 18, 16, 17
SETA_MIN = 58


def _tag(x_dir, y_meio, texto):
    """Pílula vermelha alinhada à direita em x_dir. Devolve o SVG e a largura."""
    texto = texto.upper()
    w = largura(texto, T_TAG, True) * 1.06 + 16
    h = 20
    x = x_dir - w
    return (f'<rect class="tag" x="{x:.1f}" y="{y_meio - h / 2:.1f}" width="{w:.1f}" height="{h}" rx="10"/>'
            f'<text class="tag-texto" x="{x + w / 2:.1f}" y="{y_meio + 4:.1f}" text-anchor="middle">{escape(texto)}</text>'), w


def gerar_svg(spec, titulo=None, id_svg="caminho-falha"):
    """Devolve o SVG do caminho da falha. titulo, se informado, aparece como cabeçalho visível."""
    passos = spec.get("passos", [])
    partes = []
    y = MARGEM
    if titulo:
        partes.append(f'<text class="cabeca" x="{MARGEM}" y="{y + 16}">{escape(titulo)}</text>')
        y += 40
    centro = CX_X + CX_L / 2
    tem_alerta = False
    anterior_no = False

    for p in passos:
        alerta = bool(p.get("alerta"))
        tem_alerta = tem_alerta or alerta
        cls = " alerta" if alerta else ""
        if p.get("tipo") == "seta":
            rot_x = centro + 16
            rot_max = LARG - MARGEM - rot_x
            tag_svg, tag_w = "", 0
            texto_tag = p["alerta"] if isinstance(p.get("alerta"), str) else ("FALHA" if alerta else "")
            if texto_tag:
                tag_w = largura(texto_tag.upper(), T_TAG, True) * 1.06 + 16 + 8
            linhas = quebrar(p.get("rotulo", ""), rot_max - tag_w, T_ROT, alerta)
            alt = max(SETA_MIN, len(linhas) * LH_ROT + 26)
            y0, y1 = y, y + alt
            partes.append(f'<line class="linha{cls}" x1="{centro}" y1="{y0}" x2="{centro}" y2="{y1 - 9}"/>')
            partes.append(f'<path class="ponta{cls}" d="M{centro - 6} {y1 - 10} L{centro + 6} {y1 - 10} L{centro} {y1} Z"/>')
            meio = (y0 + y1) / 2
            if texto_tag:
                svg_t, w = _tag(rot_x + tag_w - 8, meio, texto_tag)
                partes.append(svg_t)
            ty = meio - (len(linhas) - 1) * LH_ROT / 2 + 4.5
            for i, l in enumerate(linhas):
                partes.append(f'<text class="rotulo{cls}" x="{rot_x + tag_w:.1f}" y="{ty + i * LH_ROT:.1f}">{escape(l)}</text>')
            y = y1
            anterior_no = False
            continue

        # nó
        if anterior_no:
            y += 18  # dois nós seguidos sem seta: só um respiro
        interno = CX_L - 2 * PAD_H - 6
        tag_txt = p["alerta"] if isinstance(p.get("alerta"), str) else ("ponto de falha" if alerta else "")
        tit = quebrar(p.get("titulo", ""), interno, T_TIT, True)
        sub = quebrar(p.get("sub", ""), interno, T_SUB)
        alt = PAD_V * 2 + len(tit) * LH_TIT + (len(sub) * LH_SUB + 4 if sub else 0) - 4
        alt = max(alt, 52)
        partes.append(f'<rect class="caixa{cls}" x="{CX_X}" y="{y}" width="{CX_L}" height="{alt}" rx="8"/>')
        partes.append(f'<rect class="barra{cls}" x="{CX_X}" y="{y}" width="5" height="{alt}" rx="2"/>')
        ty = y + PAD_V + 14
        tx = CX_X + PAD_H + 4
        for l in tit:
            partes.append(f'<text class="titulo" x="{tx}" y="{ty}">{escape(l)}</text>')
            ty += LH_TIT
        ty += 2
        for l in sub:
            partes.append(f'<text class="sub" x="{tx}" y="{ty}">{escape(l)}</text>')
            ty += LH_SUB
        if tag_txt:
            svg_t, _ = _tag(CX_X + CX_L - 12, y, tag_txt)
            partes.append(svg_t)
        if p.get("nota"):
            nl = quebrar(p["nota"], NOTA_L, T_NOTA, alerta)
            meio = y + alt / 2
            partes.append(f'<line class="guia{cls}" x1="{CX_X + CX_L + 4}" y1="{meio}" x2="{NOTA_X - 6}" y2="{meio}"/>')
            ny = meio - (len(nl) - 1) * LH_NOTA / 2 + 4
            for i, l in enumerate(nl):
                partes.append(f'<text class="nota{cls}" x="{NOTA_X}" y="{ny + i * LH_NOTA:.1f}">{escape(l)}</text>')
        y += alt
        anterior_no = True

    if tem_alerta:
        y += 26
        partes.append(f'<rect class="tag" x="{MARGEM}" y="{y - 10}" width="12" height="12" rx="3"/>')
        partes.append(f'<text class="legenda" x="{MARGEM + 20}" y="{y}">Em vermelho, o ponto em que a falha aconteceu</text>')
        y += 4
    altura = y + MARGEM
    rotulo_acess = escape(titulo or spec.get("titulo") or "Caminho da falha")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="cf" id="{id_svg}" viewBox="0 0 {LARG} {altura:.0f}" '
            f'width="{LARG}" height="{altura:.0f}" role="img" aria-labelledby="{id_svg}-t">'
            f'<title id="{id_svg}-t">{rotulo_acess}</title><style>{ESTILO}</style>'
            f'<rect class="fundo" x="0" y="0" width="{LARG}" height="{altura:.0f}" rx="12"/>'
            + "".join(partes) + "</svg>")
