#!/usr/bin/env python3
"""Refresh the live GitHub numbers inside assets/id-dashboard.svg.

Pulls total contributions, public repo count, followers and top languages from the
GitHub GraphQL API, then rewrites the region between the <!--dyn:...--> markers in the
SVG (both the animated and the reduced-motion copy). Standard library only.

Env: GITHUB_TOKEN (required), GH_USER (default AdharshJolly).
"""
import datetime
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "id-dashboard.svg"
README = ROOT / "README.md"

NAVY, PANEL = "#070b16", "#0c1326"
BLUE, RED, INK, MUTED = "#247bff", "#ff354f", "#f2f5fb", "#9aa6c4"
P = "id"
RX, RW = 500, 376
FALLBACK = {"Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "CSS": "#663399",
            "HTML": "#e34c26", "Java": "#b07219", "C": "#555555"}
SHORT = {"Jupyter Notebook": "Jupyter"}

QUERY = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    repositories(privacy:PUBLIC, ownerAffiliations:OWNER){totalCount}
    contributionsCollection{contributionCalendar{totalContributions}}
    langs: repositories(ownerAffiliations:OWNER, isFork:false, first:100, orderBy:{field:PUSHED_AT, direction:DESC}){
      nodes{ languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } }
    }
  }
}
"""


def fetch(login, token):
    if os.environ.get("USE_GH_CLI"):  # local runs where Python's TLS store is broken
        import subprocess
        out = subprocess.check_output(["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"login={login}"], text=True)
        body = json.loads(out)
    else:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
            headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    if "errors" in body or not body.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {body.get('errors')}")
    u = body["data"]["user"]
    sizes, colors = {}, {}
    for repo in u["langs"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or FALLBACK.get(n, "#8b97b8")
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:5]
    return {
        "contrib": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "langs": [(n, s / total * 100, colors[n]) for n, s in top],
    }


# ---------------------------------------------------------------- rendering
def fam(k):
    mono = k.startswith("Mono")
    fb = "ui-monospace,Consolas,monospace" if mono else "system-ui,'Segoe UI',Arial,sans-serif"
    return f"'{P}{k}',{fb}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def panel(x, y, w, h, rx=18):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{PANEL}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="url(#{P}-dots)"/>'
            f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="{rx-.5}" fill="none" stroke="url(#{P}-hl)" stroke-width="1"/>')


def open_tile(idx, live):
    cls = f' class="{P}tile" style="animation-delay:{0.2+idx*0.12:.2f}s"' if live else ""
    return f"<g{cls}>"


def stat_tile(x, y, w, h, label, big, sub, idx, live):
    s = open_tile(idx, live) + panel(x, y, w, h)
    s += f'<text x="{x+18}" y="{y+28}" font-family="{fam("MonoB")}" font-size="12" letter-spacing="1.800" fill="{BLUE}">{esc(label)}</text>'
    s += f'<use xlink:href="#{P}-i-github" x="{x+w-38:.1f}" y="{y+12}" width="20" height="20"/>'
    s += f'<text x="{x+18}" y="{y+72}" font-family="{fam("Disp")}" font-size="40" fill="{INK}" letter-spacing="-1">{esc(big)}</text>'
    s += f'<text x="{x+18}" y="{y+96}" font-family="{fam("Body")}" font-size="14" fill="{MUTED}">{esc(sub)}</text>'
    return s + "</g>"


def lang_tile(x, y, w, h, langs, idx, live):
    s = open_tile(idx, live) + panel(x, y, w, h)
    s += f'<text x="{x+18}" y="{y+28}" font-family="{fam("MonoB")}" font-size="12" letter-spacing="1.800" fill="{RED}">TOP LANGUAGES · PUBLIC REPOS</text>'
    bx, by, bw, bh = x + 18, y + 40, w - 36, 12
    cid = f"{P}-barclip-{'l' if live else 's'}"
    s += f'<clipPath id="{cid}"><rect x="{bx}" y="{by}" width="{bw if not live else 0}" height="{bh}" rx="6">'
    if live:
        s += f'<animate attributeName="width" from="0" to="{bw}" dur="1.2s" begin="0.9s" calcMode="spline" keyTimes="0;1" keySplines="0.16 1 0.3 1" fill="freeze"/>'
    s += "</rect></clipPath>"
    s += f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="#fff" fill-opacity=".08"/>'
    s += f'<g clip-path="url(#{cid})">'
    cx = bx
    for n, pct, col in langs:
        seg = bw * pct / 100
        s += f'<rect x="{cx:.2f}" y="{by}" width="{max(seg-1.5,0.5):.2f}" height="{bh}" fill="{col}"/>'
        cx += seg
    s += "</g>"
    colw = (w - 36) / 3
    for i, (n, pct, col) in enumerate(langs):
        lx = x + 18 + (i % 3) * colw
        ly = y + 76 + (i // 3) * 20
        name = SHORT.get(n, n)
        if len(name) > 11:
            name = name[:10] + "…"
        s += f'<circle cx="{lx+5:.1f}" cy="{ly-4}" r="4.500" fill="{col}"/>'
        s += f'<text x="{lx+15:.1f}" y="{ly}" font-family="{fam("Body")}" font-size="12.500" fill="{INK}">{esc(name)}'
        s += f'<tspan font-family="{fam("Mono")}" font-size="11.500" fill="{MUTED}" dx="5">{pct:.0f}%</tspan></text>'
    return s + "</g>"


def block(d, live):
    hw = (RW - 12) / 2
    o = f'<text x="{RX}" y="58" font-family="{fam("MonoB")}" font-size="13" letter-spacing="3" fill="{BLUE}">LIVE SNAPSHOT</text>'
    o += f'<text x="{RX}" y="86" font-family="{fam("Body")}" font-size="15" fill="{MUTED}">Pulled from the GitHub API · refreshed daily</text>'
    o += stat_tile(RX, 104, hw, 118, "GITHUB", f"{d['contrib']:,}", "contributions, last year", 0, live)
    o += stat_tile(RX + hw + 12, 104, hw, 118, "GITHUB", f"{d['repos']:,}", f"repos · {d['followers']:,} followers", 1, live)
    o += lang_tile(RX, 236, RW, 104, d["langs"], 2, live)
    return o


# ---------------------------------------------------------------- patching
def patch_svg(text, d):
    for kind, live in (("live", True), ("still", False)):
        pat = re.compile(rf"<!--dyn:{kind}-->.*?<!--/dyn:{kind}-->", re.S)
        if not pat.search(text):
            raise SystemExit(f"marker dyn:{kind} not found in {SVG}")
        rep = f"<!--dyn:{kind}-->{block(d, live)}<!--/dyn:{kind}-->"
        text = pat.sub(lambda m: rep, text)
    return text


def bump_readme():
    if not README.exists():
        return
    t = README.read_text(encoding="utf-8")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H")
    n = re.sub(r"(assets/id-dashboard\.svg\?v=)[A-Za-z0-9]+", rf"\g<1>{stamp}", t)
    if n != t:
        README.write_text(n, encoding="utf-8")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    d = fetch(os.environ.get("GH_USER", "AdharshJolly"), token)
    print(json.dumps(d, indent=1))
    old = SVG.read_text(encoding="utf-8")
    new = patch_svg(old, d)
    if new == old:
        print("no change")
        return
    SVG.write_text(new, encoding="utf-8")
    bump_readme()
    print("updated", SVG)


if __name__ == "__main__":
    main()
