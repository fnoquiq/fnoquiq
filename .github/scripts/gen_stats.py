#!/usr/bin/env python3
"""Gera cards de estatisticas (SVG) do perfil, com dados reais da API do GitHub.
Roda localmente (GH_TOKEN=$(gh auth token)) e no CI (GITHUB_TOKEN).
Sem dependencias externas — apenas a stdlib."""
import json
import os
import sys
import urllib.request

USER = os.environ.get("STATS_USER", "fnoquiq")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# paleta dark neon
BG = "#0d1117"
BORDER = "#00d9ff"
TITLE = "#00d9ff"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
VALUE = "#03a87c"

if not TOKEN:
    sys.exit("ERRO: defina GH_TOKEN ou GITHUB_TOKEN")

HEADERS = {"Authorization": f"bearer {TOKEN}", "User-Agent": "stats-gen"}


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={**HEADERS, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def rest_count(q):
    url = "https://api.github.com/search/" + q
    req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r).get("total_count", 0)
    except Exception:
        return 0


def fetch():
    q = """
    query($login:String!){
      user(login:$login){
        name
        followers{ totalCount }
        repositories(ownerAffiliations:OWNER, isFork:false, first:100, orderBy:{field:STARGAZERS,direction:DESC}){
          totalCount
          nodes{ stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } }
        }
      }
    }"""
    u = gql(q, {"login": USER})["data"]["user"]
    repos = u["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#858585"})
            langs[n]["size"] += e["size"]
    return {
        "name": u["name"] or USER,
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "stars": stars,
        "commits": rest_count(f"commits?q=author:{USER}"),
        "prs": rest_count(f"issues?q=type:pr+author:{USER}"),
        "issues": rest_count(f"issues?q=type:issue+author:{USER}"),
        "langs": langs,
    }


def br(n):
    return f"{n:,}".replace(",", ".")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stats_svg(d):
    W, H = 495, 195
    rows = [
        ("⭐", "Estrelas conquistadas", br(d["stars"])),
        ("\U0001f4dd", "Commits", br(d["commits"])),
        ("\U0001f465", "Seguidores", br(d["followers"])),
    ]
    rows2 = [
        ("\U0001f500", "Pull Requests", br(d["prs"])),
        ("\U0001f41b", "Issues", br(d["issues"])),
        ("\U0001f4e6", "Repositórios", br(d["repos"])),
    ]
    def col(items, x0):
        out = []
        y = 82
        for icon, label, val in items:
            out.append(f'<text x="{x0}" y="{y}" font-size="15">{icon}</text>')
            out.append(f'<text x="{x0+26}" y="{y}" fill="{TEXT}" font-size="14">{esc(label)}</text>')
            out.append(f'<text x="{x0+205}" y="{y}" fill="#ffffff" font-size="15" font-weight="700" text-anchor="end">{val}</text>')
            y += 36
        return "\n".join(out)
    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif">
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-opacity="0.55"/>
  <text x="25" y="42" fill="{TITLE}" font-size="19" font-weight="700">⚡ Estatísticas de {esc(d["name"])}</text>
  <line x1="25" y1="55" x2="470" y2="55" stroke="#21262d"/>
  {col(rows, 28)}
  {col(rows2, 262)}
</svg>'''
    return svg


def languages_svg(d):
    langs = d["langs"]
    total = sum(v["size"] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1]["size"])[:6]
    W = 495
    barY = 70
    barX = 25
    barW = 445
    # barra empilhada
    segs = []
    x = barX
    for name, v in top:
        w = v["size"] / total * barW
        segs.append(f'<rect x="{x:.1f}" y="{barY}" width="{w:.1f}" height="10" fill="{v["color"]}"/>')
        x += w
    if x < barX + barW:  # restante
        segs.append(f'<rect x="{x:.1f}" y="{barY}" width="{barX+barW-x:.1f}" height="10" fill="#30363d"/>')
    # legenda em 2 colunas x 3
    leg = []
    for i, (name, v) in enumerate(top):
        pct = v["size"] / total * 100
        cx = 30 if i < 3 else 260
        cy = 108 + (i % 3) * 28
        leg.append(f'<circle cx="{cx}" cy="{cy-4}" r="6" fill="{v["color"]}"/>')
        leg.append(f'<text x="{cx+14}" y="{cy}" fill="{TEXT}" font-size="14">{esc(name)} <tspan fill="{MUTED}">{pct:.1f}%</tspan></text>')
    H = 200
    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif">
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-opacity="0.55"/>
  <text x="25" y="42" fill="{TITLE}" font-size="19" font-weight="700">\U0001f9ea Linguagens mais usadas</text>
  <line x1="25" y1="52" x2="470" y2="52" stroke="#21262d"/>
  <clipPath id="r"><rect x="{barX}" y="{barY}" width="{barW}" height="10" rx="5"/></clipPath>
  <g clip-path="url(#r)">{''.join(segs)}</g>
  {''.join(leg)}
</svg>'''
    return svg


def main():
    d = fetch()
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(d))
    with open(os.path.join(OUTDIR, "languages.svg"), "w", encoding="utf-8") as f:
        f.write(languages_svg(d))
    print("OK:", {k: d[k] for k in ("stars", "commits", "prs", "issues", "followers", "repos")})


if __name__ == "__main__":
    main()
