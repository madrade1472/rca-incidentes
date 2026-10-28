# -*- coding: utf-8 -*-
"""Monta o RCA a partir do incidente.json: página HTML autocontida, figura SVG e backlog.

Uso:
  python monta_rca.py incidente.json [--saida out] [--coleta-completa]

Grava em --saida:
  rca.html              o documento, página única sem dependência de rede (CSS e SVG embutidos)
  caminho_falha.svg     a figura do caminho da falha, se o incidente tiver "caminho_falha"
  linha_do_tempo.json   a linha do tempo consolidada (manual mais coleta), ordenada
  backlog.json          as ações com identificador, dono, prazo e status

A linha do tempo junta os eventos escritos no incidente.json com os arquivos da pasta indicada em
"coleta" (saída do coleta_aws.py ou do coleta_azure.py). Um evento de coleta entra apenas se o
incidente citar o seu "ref", ou se --coleta-completa for informado: o documento não é despejo de log.
Só biblioteca padrão, Python 3.8+.
"""
import argparse
import glob
import os
import sys
from html import escape

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from comum import (MARCOS, SEVERIDADES, data_prazo, definir_fuso, gravar_json, gravar_texto,  # noqa: E402
                   instante, ler_json, local, metricas)
from figura import gerar_svg  # noqa: E402
from valida_incidente import validar  # noqa: E402

ORDEM = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
TIPO = {"prevenir": "Prevenir", "detectar": "Detectar", "mitigar": "Mitigar", "processo": "Processo"}
STATUS = {"aberta": "Aberta", "em_andamento": "Em andamento", "andamento": "Em andamento",
          "concluida": "Concluída", "cancelada": "Cancelada"}
TOM_SEV = {"SEV1": "critico", "SEV2": "alto", "SEV3": "medio", "SEV4": "baixo"}
TOM_P = {"P1": "critico", "P2": "alto", "P3": "medio", "P4": "neutro"}

CSS = """
:root{
  color-scheme:light dark;
  --fundo:#f6f6f2;--superficie:#ffffff;--superficie-2:#f0f1ec;--texto:#1c2321;--suave:#5b6662;
  --borda:#dcdfd8;--acento:#1f6f68;--acento-suave:#e5efec;
  --critico:#b42318;--critico-suave:#fcebe9;--alto:#b54708;--alto-suave:#fdf1e3;
  --medio:#8a6a00;--medio-suave:#f8f1d6;--baixo:#2f7a4c;--baixo-suave:#e6f3ea;
  --neutro:#5b6662;--neutro-suave:#eceee9;
  --raio:10px;--sombra:0 1px 2px rgba(20,30,28,.06),0 4px 16px rgba(20,30,28,.05);
  --fonte:Inter,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --fundo:#141817;--superficie:#1b201f;--superficie-2:#222927;--texto:#e6eae8;--suave:#a4afab;
  --borda:#323b38;--acento:#62b5aa;--acento-suave:#1f302d;
  --critico:#f27a6f;--critico-suave:#3b2422;--alto:#f0a35e;--alto-suave:#3a2c1d;
  --medio:#e3c35a;--medio-suave:#363019;--baixo:#79c79a;--baixo-suave:#1d3226;
  --neutro:#a4afab;--neutro-suave:#2a3230;
  --sombra:0 1px 2px rgba(0,0,0,.3);
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.6 var(--fonte);
  font-feature-settings:"tnum" 1}
.pagina{max-width:980px;margin:0 auto;padding:40px 16px 64px}
.capa{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);
  box-shadow:var(--sombra);padding:32px 32px 28px;border-top:5px solid var(--acento)}
.sobre{margin:0 0 6px;color:var(--acento);font-size:.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
h1{margin:0 0 20px;font-size:clamp(1.6rem,3.4vw,2.2rem);line-height:1.2;letter-spacing:-.01em}
.ficha{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px 24px;margin:0}
.ficha div{min-width:0}
.ficha dt{color:var(--suave);font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase}
.ficha dd{margin:2px 0 0;font-weight:500;overflow-wrap:anywhere}
.chip{display:inline-block;padding:1px 10px;border-radius:999px;font-size:.78rem;font-weight:700;
  letter-spacing:.04em;line-height:1.7;white-space:nowrap;background:var(--neutro-suave);color:var(--neutro)}
.critico{background:var(--critico-suave);color:var(--critico)}
.alto{background:var(--alto-suave);color:var(--alto)}
.medio{background:var(--medio-suave);color:var(--medio)}
.baixo{background:var(--baixo-suave);color:var(--baixo)}
.neutro{background:var(--neutro-suave);color:var(--neutro)}
section{margin-top:44px}
h2{display:flex;align-items:baseline;gap:12px;margin:0 0 14px;font-size:1.35rem;line-height:1.3;
  padding-bottom:8px;border-bottom:1px solid var(--borda)}
h2 .num{color:var(--acento);font-size:.95rem;font-weight:700;font-variant-numeric:tabular-nums}
h3{margin:26px 0 8px;font-size:1.05rem}
p{margin:0 0 12px;text-align:justify;hyphens:auto}
.nota-sec{color:var(--suave);font-size:.92rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:0 0 20px}
.kpi{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);padding:14px 16px}
.kpi span{display:block;color:var(--suave);font-size:.78rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.kpi strong{display:block;margin-top:4px;font-size:1.45rem;line-height:1.2;font-variant-numeric:tabular-nums}
.kpi.sev{border-left:5px solid currentColor}
.kpi.sev span{color:inherit;opacity:.85}
.kpi.sev small{display:block;margin-top:4px;font-size:.8rem;line-height:1.35;color:var(--texto);opacity:.8}
.destaque{margin:18px 0;padding:16px 20px;border-left:4px solid var(--acento);background:var(--acento-suave);
  border-radius:0 var(--raio) var(--raio) 0}
.destaque b{display:block;margin-bottom:4px;color:var(--acento);font-size:.75rem;letter-spacing:.12em;text-transform:uppercase}
.destaque p{margin:0}
.tabela{overflow-x:auto;background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);margin:0 0 16px}
table{width:100%;border-collapse:collapse;font-size:.93rem}
th,td{padding:10px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--borda)}
th{background:var(--superficie-2);color:var(--suave);font-size:.75rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;white-space:nowrap}
tr:last-child td{border-bottom:0}
td.quando,td.id,td.prazo{white-space:nowrap;font-variant-numeric:tabular-nums}
td.id{font-family:var(--mono);font-size:.82rem;color:var(--suave)}
td.fonte{color:var(--suave)}
th.num,td.num{text-align:right;font-weight:600;white-space:nowrap}
tr.marco td{background:var(--acento-suave);font-weight:600}
tr.marco td.quando::before{content:"";display:inline-block;width:8px;height:8px;margin-right:8px;
  border-radius:50%;background:var(--acento);vertical-align:1px}
figure{margin:0 0 12px;background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);padding:12px}
figure svg{display:block;width:100%;height:auto;max-width:760px;margin:0 auto}
figcaption{margin-top:8px;color:var(--suave);font-size:.85rem;text-align:center}
ol.porques{list-style:none;counter-reset:pq;margin:0;padding:0}
ol.porques li{counter-increment:pq;position:relative;margin:0 0 10px;padding:12px 16px 12px 64px;
  background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio)}
ol.porques li::before{content:counter(pq);position:absolute;left:16px;top:11px;width:30px;height:30px;
  border-radius:50%;background:var(--acento-suave);color:var(--acento);font-weight:700;text-align:center;line-height:30px}
ul.lista{margin:0 0 12px;padding-left:22px}
ul.lista li{margin:0 0 6px}
.colunas{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.cartao{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);padding:16px 18px}
.cartao h3{margin-top:0}
.cartao.ok{border-top:4px solid var(--baixo)}
.cartao.nao{border-top:4px solid var(--critico)}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--borda);color:var(--suave);font-size:.85rem}
@media (max-width:640px){
  .pagina{padding-top:20px}
  .capa{padding:22px 18px}
  h2{font-size:1.2rem}
  p{text-align:left}
  .tabela.resp{background:transparent;border:0;overflow:visible}
  .resp table,.resp tbody,.resp tr,.resp td{display:block;width:100%}
  .resp thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  .resp tr{margin:0 0 10px;background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);overflow:hidden}
  .resp td{display:grid;grid-template-columns:6.5rem 1fr;gap:10px;border-bottom:1px solid var(--borda);white-space:normal}
  .resp td::before{content:attr(data-rotulo);color:var(--suave);font-size:.72rem;font-weight:700;
    letter-spacing:.05em;text-transform:uppercase;padding-top:2px}
  .resp td.num{text-align:left}
  .resp tr.marco td.quando::before{content:attr(data-rotulo);display:block;width:auto;height:auto;margin:0;
    border-radius:0;background:none;vertical-align:baseline}
}
@media print{
  :root{--fundo:#ffffff;--superficie:#ffffff;--superficie-2:#f0f1ec;--texto:#111111;--suave:#4a524f;
    --borda:#cfd3cd;--acento:#1f6f68;--acento-suave:#eaf2f0;--critico:#b42318;--critico-suave:#fcebe9;
    --alto:#b54708;--alto-suave:#fdf1e3;--medio:#7a5e00;--medio-suave:#f8f1d6;--baixo:#2f7a4c;
    --baixo-suave:#e6f3ea;--neutro:#4a524f;--neutro-suave:#eceee9;--sombra:none}
  @page{margin:16mm 14mm}
  body{font-size:10.5pt;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .pagina{max-width:none;padding:0}
  .capa{border-top-width:4px}
  section{margin-top:22pt}
  h2{break-after:avoid}
  h3{break-after:avoid}
  .kpi,.destaque,figure,ol.porques li,.cartao,tr{break-inside:avoid}
  .tabela{overflow:visible}
  thead{display:table-header-group}
}
""".strip()


def esc(x):
    return escape(str(x if x is not None else ""))


def tabela(colunas, linhas, resp=True, classes_col=None, classes_linha=None):
    """colunas: rótulos; linhas: listas de HTML já escapado."""
    classes_col = classes_col or [""] * len(colunas)
    h = [f'<div class="tabela{" resp" if resp else ""}"><table><thead><tr>']
    h += [f'<th class="{cc}">{esc(c)}</th>' if cc else f"<th>{esc(c)}</th>" for c, cc in zip(colunas, classes_col)]
    h.append("</tr></thead><tbody>")
    for i, ln in enumerate(linhas):
        cl = (classes_linha or [""] * len(linhas))[i]
        h.append(f'<tr class="{cl}">' if cl else "<tr>")
        for c, cel, cc in zip(colunas, ln, classes_col):
            h.append(f'<td{f" class={chr(34)}{cc}{chr(34)}" if cc else ""} data-rotulo="{esc(c)}">{cel}</td>')
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def lista(itens):
    return '<ul class="lista">' + "".join(f"<li>{esc(i)}</li>" for i in itens) + "</ul>"


def main():
    ap = argparse.ArgumentParser(description="Monta o RCA em HTML a partir do incidente.json.")
    ap.add_argument("incidente")
    ap.add_argument("--saida", default="out")
    ap.add_argument("--coleta-completa", action="store_true")
    a = ap.parse_args()

    inc = ler_json(a.incidente)
    base = os.path.dirname(os.path.abspath(a.incidente))
    erros, avisos = validar(inc)
    for x in avisos:
        print(f"  [aviso] {x}")
    if erros:
        for x in erros:
            print(f"  [erro] {x}")
        sys.exit("corrija o incidente.json (python valida_incidente.py incidente.json)")
    definir_fuso(inc.get("fuso"))

    saida = os.path.abspath(a.saida)
    os.makedirs(saida, exist_ok=True)

    # ------------------------------------------------------------ linha do tempo
    lacunas = list(inc.get("lacunas", []))
    eventos = [dict(e, origem="manual") for e in inc.get("linha_do_tempo", [])]
    if inc.get("coleta"):
        pasta = os.path.join(base, inc["coleta"])
        refs = {e.get("ref") for e in inc.get("linha_do_tempo", []) if e.get("ref")}
        for p in sorted(glob.glob(os.path.join(pasta, "*.json"))):
            if os.path.basename(p) == "lacunas.json":
                lacunas.extend(ler_json(p))
                continue
            for e in ler_json(p):
                if a.coleta_completa or e.get("ref") in refs:
                    eventos.append(dict(e, origem=os.path.basename(p)))
    # Marco no mesmo minuto de um evento vira prefixo dele ("Detecção: ..."), sem linha repetida.
    for k, rot in MARCOS:
        if not inc["marcos"].get(k):
            continue
        mesmo = [e for e in eventos if local(e["quando"]) == local(inc["marcos"][k])]
        if mesmo:
            ev = mesmo[0]["evento"]
            mesmo[0]["evento"] = f"{rot}: {ev[0].lower()}{ev[1:]}"
            mesmo[0]["tipo"] = "marco"
        else:
            eventos.append({"quando": inc["marcos"][k], "fonte": "Marco do incidente", "evento": rot,
                            "tipo": "marco", "origem": "marco"})
    vistos, unicos = set(), []
    for e in sorted(eventos, key=lambda e: instante(e["quando"])):
        chave = (local(e["quando"]), e["evento"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(e)
    gravar_json(os.path.join(saida, "linha_do_tempo.json"), unicos)

    # ------------------------------------------------------------ backlog
    def chave_acao(x):
        d = data_prazo(x["prazo"])
        return (ORDEM[x["prioridade"]], d.toordinal() if d else 10 ** 7, x["prazo"])

    acoes = sorted(inc["acoes"], key=chave_acao)
    backlog = {"origem": f"RCA {inc['id']}", "titulo": inc["titulo"], "acoes": [
        {"id": f"{inc['id']}-A{i + 1:02d}", "titulo": x["titulo"], "tipo": x["tipo"], "prioridade": x["prioridade"],
         "dono": x["dono"], "prazo": x["prazo"], "status": x.get("status", "aberta"), "detalhe": x.get("detalhe", "")}
        for i, x in enumerate(acoes)]}
    gravar_json(os.path.join(saida, "backlog.json"), backlog)

    # ------------------------------------------------------------ figura
    svg_inline = None
    if inc.get("caminho_falha"):
        spec = inc["caminho_falha"]
        svg_arquivo = gerar_svg(spec, titulo=spec.get("titulo") or f"Caminho da falha, {inc['id']}", id_svg="cf-arquivo")
        gravar_texto(os.path.join(saida, "caminho_falha.svg"),
                     '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_arquivo + "\n")
        svg_inline = gerar_svg(spec, id_svg="cf")

    # ------------------------------------------------------------ documento
    m = inc["marcos"]
    met = metricas(inc)
    sev = inc["severidade"]
    periodo = f"{local(m['inicio_impacto'])} a {local(m['resolucao'])}"
    data_doc = inc.get("data_documento", local(m["resolucao"]).split()[0])
    fuso_txt = inc.get("fuso_rotulo") or ("de Brasília" if not inc.get("fuso") else f"no fuso {inc['fuso']}")
    s = []
    n = [0]

    def secao(titulo, corpo, ident):
        n[0] += 1
        s.append(f'<section id="{ident}"><h2><span class="num">{n[0]:02d}</span>{esc(titulo)}</h2>{corpo}</section>')

    causa = f'<div class="destaque"><b>Causa raiz</b><p>{esc(inc["causa_raiz"])}</p></div>'

    # Resumo executivo
    kpis = [f'<div class="kpi sev {TOM_SEV[sev]}"><span>Severidade</span><strong>{esc(sev)}</strong>'
            f'<small>{esc(SEVERIDADES[sev])}</small></div>']
    kpis += [f'<div class="kpi"><span>{esc(k)}</span><strong>{esc(v)}</strong></div>' for k, v in met.items()]
    secao("Resumo executivo", f'<div class="kpis">{"".join(kpis)}</div><p>{esc(inc["resumo"])}</p>{causa}', "resumo")

    # Impacto
    imp = inc.get("impacto", {})
    corpo = f'<p>{esc(imp.get("descricao", "[A CONFIRMAR]"))}</p>'
    if imp.get("numeros"):
        corpo += tabela(["Indicador", "Valor"], [[esc(x["rotulo"]), esc(x["valor"])] for x in imp["numeros"]],
                        classes_col=["", "num"])
    corpo += f'<p class="nota-sec">Severidade {esc(sev)}: {esc(SEVERIDADES[sev].lower())}.</p>'
    secao("Impacto", corpo, "impacto")

    # Linha do tempo
    corpo = (f'<p class="nota-sec">Horários {esc(fuso_txt)}. Cada evento traz a fonte de onde foi tirado; '
             f'os marcos do incidente aparecem em destaque.</p>')
    corpo += tabela(["Quando", "Evento", "Fonte"],
                    [[esc(local(e["quando"])), esc(e["evento"]), esc(e["fonte"])] for e in unicos],
                    classes_col=["quando", "", "fonte"],
                    classes_linha=["marco" if e.get("tipo") == "marco" else "" for e in unicos])
    secao("Linha do tempo", corpo, "linha-do-tempo")

    # Caminho da falha
    if svg_inline:
        corpo = ('<p>O caminho da falha, do gatilho ao impacto percebido. O trecho em vermelho marca onde o fluxo '
                 'deixou de funcionar.</p>'
                 f'<figure>{svg_inline}<figcaption>Figura 1. Caminho da falha do {esc(inc["id"])}.</figcaption></figure>')
        secao("Caminho da falha", corpo, "caminho-da-falha")

    # Porquês e causa raiz
    corpo = ('<p>Do sintoma percebido até a causa sistêmica, perguntando por que a cada passo.</p>'
             '<ol class="porques">' + "".join(f"<li>{esc(x)}</li>" for x in inc["porques"]) + "</ol>")
    secao("Os porquês", corpo, "porques")
    secao("Causa raiz", causa, "causa-raiz")
    if inc.get("fatores"):
        secao("Fatores contribuintes", lista(inc["fatores"]), "fatores")

    # Resposta ao incidente
    if inc.get("funcionou") or inc.get("nao_funcionou"):
        cart = []
        if inc.get("funcionou"):
            cart.append(f'<div class="cartao ok"><h3>O que funcionou</h3>{lista(inc["funcionou"])}</div>')
        if inc.get("nao_funcionou"):
            cart.append(f'<div class="cartao nao"><h3>O que não funcionou</h3>{lista(inc["nao_funcionou"])}</div>')
        secao("Resposta ao incidente", f'<div class="colunas">{"".join(cart)}</div>', "resposta")

    # Plano de ação
    linhas = []
    for x in backlog["acoes"]:
        acao = esc(x["titulo"]) + (f'<br><span class="nota-sec">{esc(x["detalhe"])}</span>' if x["detalhe"] else "")
        st = x["status"]
        tom_st = "baixo" if st == "concluida" else ("medio" if "andamento" in st else "neutro")
        linhas.append([esc(x["id"]), acao, esc(TIPO[x["tipo"]]),
                       f'<span class="chip {TOM_P[x["prioridade"]]}">{esc(x["prioridade"])}</span>',
                       esc(x["dono"]), esc(x["prazo"]),
                       f'<span class="chip {tom_st}">{esc(STATUS.get(st, st))}</span>'])
    corpo = ('<p>Ações ordenadas por prioridade e prazo. Cada uma tem dono e prazo e segue para o backlog '
             '(<code>backlog.json</code>).</p>'
             + tabela(["ID", "Ação", "Tipo", "Prioridade", "Dono", "Prazo", "Status"], linhas,
                      classes_col=["id", "", "", "", "", "prazo", ""]))
    secao("Plano de ação", corpo, "plano-de-acao")

    if inc.get("licoes"):
        secao("Lições aprendidas", lista(inc["licoes"]), "licoes")

    # Método e evidências
    corpo = ("<p>Análise sem culpados: o objetivo é entender por que o sistema permitiu a falha, e não quem a "
             "cometeu. Cada evento da linha do tempo e cada número deste documento têm a fonte indicada. A coleta "
             "de evidência foi feita somente em leitura.</p>")
    if inc.get("evidencias"):
        corpo += tabela(["Evidência", "Referência"], [[esc(e["rotulo"]), esc(e["ref"])] for e in inc["evidencias"]])
    secao("Método e evidências", corpo, "metodo")

    if lacunas:
        secao("Lacunas", '<p>O que não pôde ser confirmado por evidência e permanece em aberto.</p>' + lista(lacunas),
              "lacunas")

    ficha = [("Incidente", esc(inc["id"])),
             ("Severidade", f'<span class="chip {TOM_SEV[sev]}">{esc(sev)}</span>'),
             ("Ambiente", esc(inc.get("ambiente", "[A CONFIRMAR]"))),
             ("Período do impacto", esc(periodo)),
             ("Versão", esc(inc.get("versao", "1.0"))),
             ("Data do documento", esc(data_doc))]
    if inc.get("autor"):
        ficha.append(("Autoria", esc(inc["autor"])))
    ficha.append(("Classificação", f'<span class="chip neutro">{esc(inc.get("classificacao", "CONFIDENCIAL"))}</span>'))
    ficha_html = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in ficha)
    titulo_doc = f"RCA {inc['id']}: {inc['titulo']}"
    descricao = (f"Análise de causa raiz do incidente {inc['id']} ({sev}), de {periodo}, "
                 "com linha do tempo, causa raiz e plano de ação.")

    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="description" content="{esc(descricao)}">
<title>{esc(titulo_doc)}</title>
<style>
{CSS}
</style>
</head>
<body>
<main class="pagina">
<header class="capa">
<p class="sobre">Análise de causa raiz</p>
<h1>{esc(inc["titulo"])}</h1>
<dl class="ficha">{ficha_html}</dl>
</header>
{chr(10).join(s)}
<footer>{esc(titulo_doc)}. Versão {esc(inc.get("versao", "1.0"))} de {esc(data_doc)}. Documento sem culpados,
com fonte para cada evento e cada número.</footer>
</main>
</body>
</html>
"""
    destino = gravar_texto(os.path.join(saida, "rca.html"), pagina)
    print(f"linha do tempo: {len(unicos)} eventos | ações: {len(backlog['acoes'])} | métricas: {met}")
    print(f"OK -> {destino}")
    if svg_inline:
        print(f"     {os.path.join(saida, 'caminho_falha.svg')}")


if __name__ == "__main__":
    main()
