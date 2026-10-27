"""Grafisk manual v1 för Glasrikets GK, profilen "Glas och skog".

Bygger A4 liggande som HTML -> PDF med Chromium (headless_shell), plus en JPG per sida
och en översiktsbild. Mönster från TACADA:s manual-generator (grafisk-profil/kalla/manual.py).

Körning:
    python3 glasriket_manual.py <byggmapp>

Byggmappen får fonts/, img/ och logo/ kopierade från projektmappen (prep()).
Kräver Pillow; segno för QR-koden (annars stoppar bygget, vi trycker aldrig en låtsas-QR).
"""
import os, sys, shutil, subprocess, glob

HS = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
PF = '/mnt/project-files/glasriket'
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SIGILL = f'{PF}/logo-fornyad/sigill/smaland'
HALBILDER = os.environ.get('HALBILDER', f'{PF}/halbilder-stil-a')
HALKORT = os.environ.get('HALKORT', f'{PF}/halkort-stil-a')
VERSION = 'Version 1.1 · Oktober 2026'

# Profilen "Glas och skog"
# v1.1 (Eric 2026-10-27): den ljusa färgen är Sand i stället för den ljusblå Kristall.
DJUP, SJO, GRON, IS, KRIST, GLOD, GLOD_D = '#10202E', '#1D4756', '#3F7F86', '#9CC9C3', '#EFE6D2', '#D9A441', '#8A6220'
# Sigillets egna toner (står i logotypfilerna)
S_BRONS, S_BRONS_L = '#8C5A22', '#D49A4E'
STEN = '#E5DAC2'          # mellanyta, en ton mörkare än Sand (för rutor)
INK = DJUP

W, H, M = 1123, 794, 60   # A4 liggande i CSS-px (96 dpi)

LM = 'Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0'


# ---------------------------------------------------------------- förberedelse
def prep(out):
    from PIL import Image
    for d in ('fonts', 'img', 'logo'):
        os.makedirs(f'{out}/{d}', exist_ok=True)
    for f in glob.glob(f'{PF}/profil/typsnitt/*.ttf'):
        shutil.copy(f, f'{out}/fonts/')
    import re
    for f in glob.glob(f'{SIGILL}/*.svg'):
        # Originalfilen har en bakgrundsruta; i manualen läggs sigillet på sidans egen botten.
        s = open(f).read()
        s = re.sub(r'<metadata>.*?</metadata>', '', s, flags=re.S)
        s = re.sub(r'<rect x="-10" y="-10" width="220" height="220" fill="[^"]+"/>', '', s, count=1)
        open(f'{out}/logo/' + os.path.basename(f), 'w').write(s)
    # Målade hålbilder (repo) -> PNG med alfa, 1600 px hög
    # Senaste hålbilder (stil A, godkänd 2026-10-27) och hålkort (mörk layout 3)
    for n in range(1, 19):
        im = Image.open(f'{HALBILDER}/hal-{n:02d}-a5.webp'); im.thumbnail((1600, 1600))
        im.save(f'{out}/img/hal-{n:02d}-malad.png', optimize=True)
    for n in (3, 5, 9, 11, 14, 17, 18):
        im = Image.open(f'{HALKORT}/hal-{n:02d}-layout3.png').convert('RGB'); im.thumbnail((1100, 1640))
        im.save(f'{out}/img/kort-{n:02d}.jpg', quality=88)
    for n in ('h14-tee', 'h05-inspel', 'h03-inspel', 'h05-tee'):
        im = Image.open(f'{PF}/ogonhojd/v2/{n}.jpg').convert('RGB'); im.thumbnail((1800, 1800))
        im.save(f'{out}/img/oh-{n}.jpg', quality=86)
    # Handduken: etiketten retuscherad till enfärgsversionen med öppen (vit) boll, 2026-10-27
    for n, f in (('troja_af', f'{PF}/presentation-torsdag/kalla/troja_af.jpg'),
                 ('handduk_af', f'{PF}/logo-fornyad/sigill/produktbilder/handduk_af_vit-boll.jpg')):
        im = Image.open(f).convert('RGB'); im.thumbnail((1400, 1400))
        im.save(f'{out}/img/{n}.jpg', quality=88)
    for n in ('5-panel', 'A-frame'):
        Image.open(f'{SIGILL}/Glasriket_sigill-smaland_{n}-broderad.png').convert('RGB').save(f'{out}/img/keps-{n}.jpg', quality=90)
    # Riktig QR-kod till klubbens webbplats (segno). Ingen reserv: hellre stopp än låtsas-QR.
    import segno
    sys.path.insert(0, REPO)
    from golfholes.statistik import qr_lank  # samma adress som skylten: hålsidan med ?q=hNN
    segno.make(qr_lank({'web': 'https://www.glasriketsgk.se'}, 14), error='m').save(f'{out}/img/qr.svg', dark=DJUP, light=None, border=0)


# ---------------------------------------------------------------- hjälp
def lum(hx):
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(hx):
    return ' · '.join(str(int(hx[i:i + 2], 16)) for i in (1, 3, 5))


def seal(var, w, style=''):
    f = {'ljus': 'fargad_ljus-botten', 'mork': 'fargad_mork-botten', 'marin': 'enfarg_marinbla',
         'brons': 'enfarg_brons', 'vit': 'enfarg_vit'}[var]
    return f'<img src="logo/Glasriket_sigill-smaland_{f}.svg" style="width:{w}px;height:{w}px;display:block;{style}">'


def rings(w, h, cx, cy, color, n=7, r0=120, step=46, op=1):
    """Ringmotivet: koncentriska ringar ur sigillets dubbelring, beskurna av ytan."""
    c = ''.join(f'<circle cx="{cx}" cy="{cy}" r="{r0 + i * step}" fill="none" stroke="{color}" stroke-width="{1.6 if i % 3 == 0 else .8}"/>' for i in range(n))
    return f'<svg class="abs" style="left:0;top:0;opacity:{op}" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{c}</svg>'


CSS = f'''
@font-face{{font-family:'Spectral';src:url(fonts/Spectral-Regular.ttf);font-weight:400}}
@font-face{{font-family:'Spectral';src:url(fonts/Spectral-Medium.ttf);font-weight:500}}
@font-face{{font-family:'Spectral';src:url(fonts/Spectral-Italic.ttf);font-style:italic}}
@font-face{{font-family:'Hanken';src:url(fonts/HankenGrotesk-Regular.ttf);font-weight:400}}
@font-face{{font-family:'Hanken';src:url(fonts/HankenGrotesk-Medium.ttf);font-weight:500}}
@font-face{{font-family:'Hanken';src:url(fonts/HankenGrotesk-SemiBold.ttf);font-weight:600}}
@page{{size:297mm 210mm;margin:0}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#777}}
.pg{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:{KRIST};color:{INK};font-family:Hanken;
  page-break-after:always;break-after:page;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.pg.dark{{background:{DJUP};color:{KRIST}}}
.abs{{position:absolute}}
.hd{{position:absolute;left:{M}px;right:{M}px;top:30px;display:flex;justify-content:space-between;font:600 8px/1 Hanken;letter-spacing:.22em;text-transform:uppercase;color:{GRON}}}
.dark .hd{{color:{IS};opacity:.8}}
.ft{{position:absolute;left:{M}px;right:{M}px;bottom:24px;font:400 7.5px/1.3 Hanken;opacity:.6}}
.ey{{font:600 9px/1 Hanken;letter-spacing:.2em;text-transform:uppercase;color:{GLOD_D}}}
.dark .ey{{color:{GLOD}}}
h1{{font:400 40px/1.08 Spectral;margin:12px 0 0;letter-spacing:-.005em}}
h2{{font:400 21px/1.2 Spectral}}
h3{{font:600 9px/1.3 Hanken;letter-spacing:.16em;text-transform:uppercase}}
p{{font:400 12.5px/1.6 Hanken;margin:0 0 10px}}
.lead{{font:400 15.5px/1.5 Hanken}}
.sm{{font:400 10.5px/1.5 Hanken}}
.xs{{font:400 8.5px/1.45 Hanken}}
.mut{{opacity:.72}}
.cap{{font:400 9px/1.4 Hanken;opacity:.75}}
.b{{font-weight:600}}
.rule{{border-top:1px solid rgba(16,32,46,.18)}}
.dark .rule{{border-top-color:rgba(239,230,210,.22)}}
.tile{{position:absolute;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.no{{position:absolute;width:22px;height:22px;border-radius:50%;background:#7A2430;color:#fff;font:600 13px/22px Hanken;text-align:center}}
.x{{position:absolute;left:0;top:0}}
'''

P = []


def page(body, n=None, dark=False, lm=False, ft_text=None):
    hd = '' if n is None else f'<div class="hd"><span>Glasrikets Golfklubb · Grafisk manual</span><span>{n:02d}</span></div>'
    ft = ''
    if lm or ft_text:
        parts = [x for x in (ft_text, LM if lm else None) if x]
        ft = f'<div class="ft">{" · ".join(parts)}</div>'
    return f'<section class="pg{" dark" if dark else ""}">{hd}{body}{ft}</section>'


def title(eyebrow, t, x=M, y=78, w=520, size=None):
    s = f'style="font-size:{size}px"' if size else ''
    return f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px"><div class="ey">{eyebrow}</div><h1 {s}>{t}</h1></div>'


def txt(x, y, w, html, cls=''):
    return f'<div class="abs {cls}" style="left:{x}px;top:{y}px;width:{w}px">{html}</div>'


# ================================================================ SIDOR
TOC = [('Logotypen', 3), ('Frizon och minsta storlek', 4), ('Färgversioner', 5), ('Så gör vi inte', 6),
       ('Färger', 7), ('Färger i bruk', 8), ('Typsnitt', 9), ('Typografisk hierarki', 10),
       ('Bildspråk: banan ovanifrån', 11), ('Bildspråk: i ögonhöjd', 12), ('Hålkort', 13), ('Hålskylt', 14),
       ('Sociala medier', 15), ('Profilprodukter', 16), ('Filpaket och märkning', 17)]


def build_pages():
    # 1 Omslag ---------------------------------------------------
    P.append(page(f'''{rings(W, H, 330, 397, IS, n=12, r0=250, step=40, op=.13)}
<div class="abs" style="left:110px;top:177px">{seal('mork', 440)}</div>
<div class="abs" style="left:650px;top:268px;width:420px">
 <div class="ey">Glasrikets Golfklubb</div>
 <div style="font:400 64px/1.02 Spectral;margin-top:18px">Grafisk<br>manual</div>
 <div style="width:56px;border-top:1.5px solid {GLOD};margin:28px 0 22px"></div>
 <div class="lead" style="opacity:.85">Profilen Glas och skog</div>
</div>
<div class="abs xs" style="left:650px;bottom:44px;opacity:.6;letter-spacing:.06em">{VERSION}</div>''', dark=True))

    # 2 Inledning + innehåll -------------------------------------
    toc = ''.join(f'<div style="display:flex;justify-content:space-between;padding:7px 0" class="rule"><span class="sm">{t}</span><span class="sm mut">{n:02d}</span></div>' for t, n in TOC)
    P.append(page(f'''{title('Inledning', 'Glas och skog')}
{txt(M, 196, 450, f"""<p class="lead">Färgerna kommer ur glaset i Glasriket och skogen runt banan. Mörkt glas bär bilderna, ljus sand bär texten och glöden är accenten.</p>
<p style="margin-top:18px">Profilen vilar på fyra saker: sigillet, sex färger, två typsnitt och banan själv som bild. Med dem ser allt från scorekort och hålskyltar till inlägg och klubbtröjor ut att komma från samma klubb.</p>
<p>Den här manualen visar hur delarna används. Följ den så långt det går. Står ni inför något manualen inte täcker, välj det enklaste alternativet med mest luft.</p>""")}
<div class="abs" style="left:{M}px;top:520px;display:flex;gap:28px">
 <div style="width:132px"><h2>Lugnt</h2><div class="sm mut" style="margin-top:6px">Få element och mycket luft.</div></div>
 <div style="width:132px"><h2>Klart</h2><div class="sm mut" style="margin-top:6px">Banan ska gå att läsa på en sekund.</div></div>
 <div style="width:132px"><h2>Eget</h2><div class="sm mut" style="margin-top:6px">Glaset och skogen, ingen annan klubbs.</div></div>
</div>
<div class="abs" style="left:640px;top:96px;width:423px"><h3 style="color:{GRON};margin-bottom:12px">Innehåll</h3>{toc}</div>''', 2))

    # 3 Logotypen, anatomi ----------------------------------------
    S = 470; X0, Y0 = 70, 180
    def pt(u, v):  # sigillets koordinater (viewBox -6..206) -> sidan
        return X0 + (u + 6) / 212 * S, Y0 + (v + 6) / 212 * S
    marks = [((128, 17), 'Ringtexten', 'Klubbens namn i versaler längs ringen.'),
             ((91, 69), 'Stjärnan', 'Glimten i glaset.'),
             ((181.5, 99), 'Granarna', 'Skogen runt banan, en på var sida.'),
             ((104, 126), 'Pokalen', 'Glaset från Glasriket och pokalen för spelet.'),
             ((128, 183), 'Orten', 'Växjö · Småland.')]
    call = ''; lab = ''
    for i, ((u, v), t, d) in enumerate(marks):
        x, y = pt(u, v); ly = 210 + i * 98
        call += f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{640}" y2="{ly + 9}" stroke="{GRON}" stroke-width=".8"/><circle cx="{x:.0f}" cy="{y:.0f}" r="3.6" fill="{GRON}" stroke="#fff" stroke-width="1.4"/>'
        lab += f'<div class="abs" style="left:652px;top:{ly}px;width:380px"><div style="font:400 19px/1 Spectral">{t}</div><div class="sm mut" style="margin-top:6px">{d}</div></div>'
    P.append(page(f'''{title('Logotyp', 'Sigillet', w=900)}
{txt(640, 102, 420, '<p class="sm mut">Sigillet är klubbens logotyp. Det är ritat som vektor och hämtas alltid från filpaketet. Det skrivs aldrig om med typsnitt och byggs aldrig om i delar.</p>')}
<div class="abs" style="left:{X0}px;top:{Y0}px">{seal('ljus', S)}</div>
<svg class="x" width="{W}" height="{H}">{call}</svg>{lab}''', 3))

    # 4 Frizon och minsta storlek --------------------------------
    D = 300; X = D / 4
    fz = (f'<div class="abs" style="left:{M}px;top:170px;width:{D + 2 * X}px;height:{D + 2 * X}px;border:1px dashed {GRON};background:rgba(63,127,134,.07)">'
          f'<div class="abs" style="left:{X}px;top:{X}px;width:{D}px;height:{D}px;background:{KRIST};outline:1px solid rgba(63,127,134,.35)"></div>'
          f'<div class="abs" style="left:{X}px;top:{X}px">{seal("ljus", D)}</div>'
          + ''.join(f'<div class="abs" style="left:{l}px;top:{t}px;width:{X}px;height:{X}px;display:flex;align-items:center;justify-content:center;font:500 13px Spectral;color:{GRON}">X</div>'
                    for l, t in ((0, X + D / 2 - X / 2), (X + D, X + D / 2 - X / 2), (X + D / 2 - X / 2, 0), (X + D / 2 - X / 2, X + D)))
          + '</div>')
    mm = 96 / 25.4
    mins = ''
    for (lab_, d, size, var), y, hh in zip((('Tryck', 'Minst 25 mm i diameter.', 25 * mm, 'ljus'),
                                             ('Skärm', 'Minst 120 px i diameter.', 120 / 2, 'ljus'),
                                             ('Brodyr', 'Minst 50 mm. Gör alltid en provbrodyr.', 50 * mm, 'marin')), (170, 300, 430), (122, 122, 224)):
        mins += (f'<div class="abs rule" style="left:640px;top:{y}px;width:423px;height:{hh}px;padding-top:16px">'
                 f'<div style="font:400 19px/1 Spectral">{lab_}</div><div class="sm mut" style="margin-top:6px;width:200px">{d}</div>'
                 f'<div class="abs" style="right:0;top:16px">{seal(var, round(size))}</div></div>')
    P.append(page(f'''{title('Logotyp', 'Frizon och minsta storlek', w=900)}
{fz}{txt(M, 640, 450, '<p class="sm mut">X är en fjärdedel av sigillets diameter. Inga andra element får komma närmare sigillet än X, på någon sida. Frizonen gäller även mot pappers- och bildkant.</p>')}
{mins}{txt(640, 680, 423, '<p class="xs mut">Tryck och brodyr visas i verklig storlek när sidan skrivs ut i 100 %. Skärmexemplet är förminskat. Under minsta storlek blir ringtexten oläslig: använd då klubbens namn i text.</p>')}''', 4))

    # 5 Färgversioner --------------------------------------------
    vers = [('ljus', KRIST, 'Färgad, ljus botten', 'Grundversion. Sand, vitt och ljusa bilder.', True),
            ('mork', DJUP, 'Färgad, mörk botten', 'Djupglas och Sjöglas. Omslag, skylt, inlägg.', False),
            ('marin', '#FFFFFF', 'Enfärg Djupglas', 'Enfärgstryck, stämplar, dokument.', True),
            ('brons', KRIST, 'Enfärg brons', 'Folie och prägling på ljust.', True),
            ('vit', SJO, 'Enfärg vit', 'Mörka ytor, glas, gravyr och dekaler.', False),
            ('keps', None, 'Broderad', 'Kläder. Färgad mörk version i tråd.', False)]
    tiles = ''
    tw, th, gx = 315, 196, 24
    for i, (v, bg, t, d, brd) in enumerate(vers):
        x = M + (i % 3) * (tw + gx); y = 150 + (i // 3) * 296
        b = 'border:1px solid rgba(16,32,46,.12);' if brd else ''
        inner = seal(v, 150) if v != 'keps' else ''
        bgs = f'background:{bg};' if bg else 'background:url(img/keps-5-panel.jpg) 50% 34%/150%;'
        tiles += f'<div class="tile" style="left:{x}px;top:{y}px;width:{tw}px;height:{th}px;{bgs}{b}">{inner}</div>'
        tiles += f'<div class="abs" style="left:{x}px;top:{y + th + 10}px;width:{tw}px"><div class="sm b">{t}</div><div class="sm mut">{d}</div></div>'
    P.append(page(f'''{title('Logotyp', 'Färgversioner', w=600)}
{txt(640, 94, 423, '<p class="sm mut">Använd den färgade versionen när det går. Enfärgsversionerna är för tekniker som bara klarar en färg. Välj alltid den version som ger störst kontrast mot botten.</p>')}{tiles}''', 5))

    # 6 Så gör vi inte -------------------------------------------
    wrongs = [('Sträck eller tryck inte ihop', KRIST, seal('ljus', 140, 'transform:scaleX(1.4)')),
              ('Vrid inte', KRIST, seal('ljus', 140, 'transform:rotate(-14deg)')),
              ('Byt inte färger', KRIST, seal('ljus', 140, 'filter:hue-rotate(150deg) saturate(1.6)')),
              ('Ingen skugga, glöd eller effekt', KRIST, seal('ljus', 140, 'filter:drop-shadow(5px 7px 4px rgba(0,0,0,.55))')),
              ('Inte på mellantoner med låg kontrast', GRON, seal('marin', 140)),
              ('Beskär inte och bryt inte ut delar', KRIST, f'<div style="width:150px;height:150px;overflow:hidden;position:relative"><div class="abs" style="left:-140px;top:-45px">{seal("ljus", 430)}</div></div>')]
    wt = ''
    for i, (t, bg, inner) in enumerate(wrongs):
        x = M + (i % 3) * (tw + gx); y = 150 + (i // 3) * 296
        wt += (f'<div class="tile" style="left:{x}px;top:{y}px;width:{tw}px;height:{th}px;background:{bg};border:1px solid rgba(16,32,46,.12)">{inner}'
               f'<svg class="x" width="{tw}" height="{th}"><line x1="22" y1="{th - 22}" x2="{tw - 22}" y2="22" stroke="#7A2430" stroke-width="2.2"/></svg></div>'
               f'<div class="abs sm" style="left:{x}px;top:{y + th + 10}px;width:{tw}px">{t}</div>')
    P.append(page(f'''{title('Logotyp', 'Så gör vi inte', w=600)}
{txt(640, 94, 423, '<p class="sm mut">Sigillet används precis som det levereras. Behöver ni en variant som inte finns i filpaketet, fråga hellre än bygg själva.</p>')}{wt}''', 6))

    # 7 Färger ---------------------------------------------------
    cols = [('Djupglas', DJUP, 'Mörka ytor, rubriker och text', KRIST, 160),
            ('Sjöglas', SJO, 'Ramar, skyltkant, mörka ytor', KRIST, 160),
            ('Glasgrön', GRON, 'Detaljer och etiketter', KRIST, 160),
            ('Isglas', IS, 'Text och linjer på mörkt', DJUP, 160),
            ('Sand', KRIST, 'Ljusa ytor och text på mörkt', DJUP, 160),
            ('Glöd', GLOD, 'Accent, bara på mörkt', DJUP, 163)]
    sw = ''; x = M
    for nm, hx, role, tc, wd in cols:
        b = 'border:1px solid rgba(16,32,46,.15);' if hx == KRIST else ''
        sw += (f'<div class="abs" style="left:{x}px;top:164px;width:{wd}px;height:330px;background:{hx};color:{tc};{b}padding:16px">'
               f'<div style="font:400 20px/1.1 Spectral">{nm}</div>'
               f'<div class="xs" style="position:absolute;left:16px;right:12px;bottom:14px;opacity:.9">{role}</div></div>'
               f'<div class="abs xs" style="left:{x}px;top:506px;width:{wd}px;line-height:1.7"><span class="b">{hx}</span><br>RGB {rgb(hx)}<br>'
               f'<span class="mut">CMYK fastställs efter tryckprov<br>Pantone fastställs efter tryckprov</span></div>')
        x += wd + 8.0
    extra = ''
    for i, (nm, hx, d) in enumerate((('Mörk glöd', GLOD_D, 'Glöd som text och linje på ljus botten.'),
                                     ('Sigillets brons', S_BRONS, 'Bara i sigillet, ljus botten. Står i logotypfilerna.'),
                                     ('Sigillets ljusa brons', S_BRONS_L, 'Bara i sigillet, mörk botten. Står i logotypfilerna.'))):
        xx = M + i * 340
        extra += (f'<div class="abs" style="left:{xx}px;top:620px;width:320px;display:flex;gap:12px">'
                  f'<div style="width:46px;height:46px;background:{hx};flex:none"></div>'
                  f'<div class="xs"><span class="b">{nm} {hx}</span> · RGB {rgb(hx)}<br><span class="mut">{d}</span></div></div>')
    P.append(page(f'''{title('Färger', 'Sex färger ur glas och skog', w=600)}
{txt(640, 94, 423, '<p class="sm mut">Skärmvärdena gäller alltid för webb, sociala medier och film. Tryckvärdena sätts mot ett riktigt tryckprov innan första tryckningen och förs in i nästa version av manualen.</p>')}
{sw}<div class="abs rule" style="left:{M}px;top:600px;width:{W - 2 * M}px"></div>{extra}''', 7))

    # 8 Färger i bruk: proportioner + kontrast --------------------
    prop = [(DJUP, 30, 'Djupglas'), (KRIST, 40, 'Sand'), (SJO, 12, 'Sjöglas'), (GRON, 8, 'Glasgrön'), (IS, 6, 'Isglas'), (GLOD, 4, 'Glöd')]
    bar = ''; x = M; tot = W - 2 * M
    for hx, pc, nm in prop:
        wd = tot * pc / 100
        b = 'border:1px solid rgba(16,32,46,.15);' if hx == KRIST else ''
        bar += f'<div class="abs" style="left:{x:.1f}px;top:170px;width:{wd:.1f}px;height:64px;background:{hx};{b}"></div><div class="abs xs" style="left:{x:.1f}px;top:242px;width:{max(wd, 60):.0f}px">{nm} {pc} %</div>'
        x += wd
    pairs = [(KRIST, DJUP), (DJUP, KRIST), (IS, DJUP), (GLOD, DJUP), (KRIST, SJO), (DJUP, IS),
             (GLOD_D, KRIST), (GRON, KRIST), (KRIST, GRON), (GLOD, KRIST)]
    cards = ''
    for i, (fg, bg) in enumerate(pairs):
        c = contrast(fg, bg)
        ok = 'Löptext och rubriker' if c >= 4.5 else ('Rubriker och etiketter, inte löptext' if c >= 3 else 'Undvik')
        nm = {DJUP: 'Djupglas', KRIST: 'Sand', IS: 'Isglas', GLOD: 'Glöd', SJO: 'Sjöglas', GRON: 'Glasgrön', GLOD_D: 'Mörk glöd'}
        x = M + (i % 5) * 201; y = 330 + (i // 5) * 196
        b = 'border:1px solid rgba(16,32,46,.12);' if bg == KRIST else ''
        bad = c < 3
        cards += (f'<div class="abs" style="left:{x}px;top:{y}px;width:189px;height:112px;background:{bg};color:{fg};{b}padding:14px">'
                  f'<div style="font:400 30px/1 Spectral">Aa</div><div class="xs" style="margin-top:12px">{nm[fg]} på {nm[bg].lower()}</div>'
                  + (f'<svg class="x" width="189" height="112"><line x1="14" y1="98" x2="175" y2="14" stroke="#7A2430" stroke-width="2"/></svg>' if bad else '') +
                  f'</div><div class="abs xs" style="left:{x}px;top:{y + 120}px;width:192px"><span class="b">Kontrast {c:.1f}:1</span><br><span class="mut">{ok}</span></div>')
    P.append(page(f'''{title('Färger', 'Färger i bruk', w=600)}
{txt(640, 94, 423, '<p class="sm mut">Sand och Djupglas bär profilen. Sjöglas och Glasgrön ger djup, Isglas och Glöd är detaljer. Proportionerna nedan är en riktlinje för en hel trycksak eller ett flöde, inte för varje enskild yta.</p>')}
{bar}<div class="abs" style="left:{M}px;top:296px"><h3 style="color:{GRON}">Text på färg</h3></div>{cards}''', 8, ft_text='Kontrast enligt WCAG 2.1. Löptext kräver minst 4,5:1, stor text och etiketter minst 3:1.'))

    # 9 Typsnitt -------------------------------------------------
    P.append(page(f'''{title('Typografi', 'Två typsnitt', w=600)}
<div class="abs" style="left:{M}px;top:170px;width:470px">
 <h3 style="color:{GRON}">Rubriker · Spectral</h3>
 <div style="font:400 120px/1 Spectral;margin-top:16px">Aa</div>
 <div style="font:400 19px/1.45 Spectral;margin-top:16px">ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ<br>abcdefghijklmnopqrstuvwxyzåäö<br>0123456789 <i>Kursiv för citat</i></div>
 <p class="sm mut" style="margin-top:16px">Rubriker, hålnummer, citat och korta texter. Regular som standard, Medium för små rubriker på skylt och skärm. Raka siffror, så att de fungerar även i Word och PowerPoint.</p>
</div>
<div class="abs" style="left:600px;top:170px;width:463px">
 <h3 style="color:{GRON}">Text · Hanken Grotesk</h3>
 <div style="font:400 120px/1 Hanken;margin-top:16px">Aa</div>
 <div style="font:400 19px/1.45 Hanken;margin-top:16px">Regular · <span style="font-weight:500">Medium</span> · <span style="font-weight:600">SemiBold</span><br>abcdefghijklmnopqrstuvwxyzåäö<br>0123456789</div>
 <p class="sm mut" style="margin-top:16px">Löptext, avstånd, tabeller, bildtexter och etiketter. Etiketter sätts i SemiBold versaler med spärrning 0,2 em. Medium används för betoning i stället för fetstil.</p>
</div>
{txt(M, 700, 1000, '<p class="xs mut">Båda typsnitten är fria att använda, även kommersiellt (SIL Open Font License 1.1), och ingår i filpaketet. Finns de inte i ett system: Georgia ersätter Spectral och Arial ersätter Hanken Grotesk.</p>')}''', 9))

    # 10 Hierarki ------------------------------------------------
    rows = [('Hålnummer', 'Spectral Regular', '120–300 pt', 'Skylt och hålkort'),
            ('Rubrik 1', 'Spectral Regular', '28–40 pt · radavstånd 1,1', 'Omslag, inlägg, webb'),
            ('Rubrik 2', 'Spectral Regular', '16–21 pt · radavstånd 1,2', 'Avsnitt'),
            ('Etikett', 'Hanken SemiBold, versaler', '7–9 pt · spärrning 0,2 em', 'Överrubriker, par och index'),
            ('Ingress', 'Hanken Regular', '12–14 pt · radavstånd 1,5', 'En eller två meningar'),
            ('Brödtext', 'Hanken Regular', '9–10 pt · radavstånd 1,5–1,6', 'Löptext, 55–75 tecken per rad'),
            ('Bildtext', 'Hanken Regular', '7–8 pt', 'Bildtexter, upphov')]
    tb = ''.join(f'<div class="rule" style="display:flex;padding:8px 0"><div class="sm b" style="width:96px">{a}</div><div class="sm" style="width:156px">{b}</div><div class="sm" style="width:176px">{c}</div><div class="sm mut" style="flex:1">{d}</div></div>' for a, b, c, d in rows)
    ex = f'''<div class="abs" style="left:650px;top:160px;width:413px;height:420px;background:#fff;padding:34px 34px;box-shadow:0 10px 30px rgba(16,32,46,.12)">
 <div class="ey">Hål 3 · Par 4 · Index 16</div>
 <div style="font:400 34px/1.08 Spectral;margin-top:12px">Genvägen kräver<br>240 meter</div>
 <div style="font:400 14px/1.5 Hanken;margin-top:14px">Ett kort par 4 som svänger höger mot en liten, inbunkrad green.</div>
 <div style="font:400 10.5px/1.6 Hanken;margin-top:14px;opacity:.85">Out längs hela högersidan och en damm till höger om tee 49. Den långtslående genar mot greenen, men det krävs en carry på cirka 240 meter.</div>
 <div style="display:flex;gap:26px;margin-top:22px"><div><div style="font:400 30px/1 Spectral">290</div><div class="xs mut">meter · tee 52 · 56 · 60</div></div><div><div style="font:400 30px/1 Spectral">274</div><div class="xs mut">meter · tee 49</div></div><div><div style="font:400 30px/1 Spectral">199</div><div class="xs mut">meter · tee 44</div></div></div>
 <div class="xs mut" style="position:absolute;left:34px;bottom:26px">Texten är hämtad från hålkortet för hål 3.</div></div>'''
    P.append(page(f'''{title('Typografi', 'Typografisk hierarki', w=560)}
<div class="abs" style="left:{M}px;top:170px;width:560px">{tb}</div>
{txt(M, 500, 540, '<p class="sm mut">Storlekarna gäller tryck. På skärm används samma steg i pixlar, till exempel rubrik 1 i 40–56 px och brödtext i 16–18 px. Håll dig till tre storlekar per yta, och låt aldrig en mellanrubrik bli mindre än brödtexten.</p>')}{ex}''', 10))

    # 11 Bildspråk ovanifrån -------------------------------------
    holes = (5, 9, 14, 17, 18)
    bw, bh = 182, 420
    im = ''.join(f'<div class="abs" style="left:{M + i * (bw + 15)}px;top:180px;width:{bw}px;height:{bh}px;background:url(img/hal-{n:02d}-malad.png) 50% 50%/contain no-repeat"></div>'
                 f'<div class="abs xs" style="left:{M + i * (bw + 15)}px;top:{180 + bh + 8}px;width:{bw}px;text-align:center;opacity:.75">Hål {n}</div>' for i, n in enumerate(holes))
    P.append(page(f'''{title('Bildspråk', 'Banan i huvudrollen', w=560)}
{txt(640, 94, 423, '<p class="sm mut">Banan visas ovanifrån, med riktiga former: fairway, green, bunkrar, vatten och skog ligger där de ligger. Ljuset är sol och tidig höst, med glöden i björkarna. Inga människor i bilderna.</p>')}{im}
<div class="abs" style="left:{M}px;top:650px;width:{W - 2 * M}px;display:flex;gap:30px">
 <div style="flex:1"><h3 style="color:{GRON}">Alltid</h3><div class="sm" style="margin-top:6px">Hela hålet i bild, från tee till green. Samma storlek när flera hål visas tillsammans.</div></div>
 <div style="flex:1"><h3 style="color:{GRON}">Aldrig</h3><div class="sm" style="margin-top:6px">Påhittade hinder, flyttade green eller bilder från en annan bana.</div></div>
 <div style="flex:1"><h3 style="color:{GRON}">Märkning</h3><div class="sm" style="margin-top:6px">Publika hålbilder har Lantmäteriets upphovsrad. Ingen annan märkning på eller vid bilderna.</div></div>
</div>''', 11, lm=True))

    # 12 Ögonhöjd ------------------------------------------------
    P.append(page(f'''{title('Bildspråk', 'I ögonhöjd', w=560)}
{txt(640, 94, 423, '<p class="sm mut">Bilder från spelarens ögonhöjd används där platsen går att känna igen: utslaget på hål 14, inspelet på hål 5 och hål 3. De byggs på Lantmäteriets höjddata så att terrängen stämmer med verkligheten.</p>')}
<div class="abs" style="left:{M}px;top:180px;width:600px;height:400px;background:url(img/oh-h14-tee.jpg) 50% 45%/cover"></div>
<div class="abs" style="left:{M + 616}px;top:180px;width:387px;height:192px;background:url(img/oh-h05-inspel.jpg) 50% 60%/cover"></div>
<div class="abs" style="left:{M + 616}px;top:388px;width:387px;height:192px;background:url(img/oh-h03-inspel.jpg) 50% 45%/cover"></div>
<div class="abs cap" style="left:{M}px;top:588px">Hål 14 från tee</div>
<div class="abs cap" style="left:{M + 616}px;top:588px">Hål 5, inspel · Hål 3, inspel</div>
{txt(M, 640, 1000, '<p class="sm">Använd ögonhöjdsbilder som stämning på webb, i inlägg och i presentationer. Lägg text på en lugn del av himlen eller på en tonad yta i Djupglas, aldrig rakt över fairway eller green.</p>')}''', 12, lm=True))

    # 13 Hålkort -------------------------------------------------
    cw, ch = 315, 470
    kort = ''.join(f'<div class="abs" style="left:{M + i * (cw + 29)}px;top:150px;width:{cw}px;height:{ch}px;background:url(img/kort-{n:02d}.jpg) center/cover;box-shadow:0 10px 26px rgba(16,32,46,.16)"></div>' for i, n in enumerate((3, 14, 17)))
    spec = [('Hålbilden', 'Hela hålet ovanifrån, med alla tees utmärkta.'), ('Hålnummer', 'Spectral, störst på kortet.'),
            ('Par, index och längder', 'Hanken, längd per tee i meter.'), ('Rubrik och råd', 'En rubrik om hålet och råd från pro:n.')]
    sp = ''.join(f'<div class="rule" style="padding:9px 0;width:236px"><div class="sm b">{a}</div><div class="sm mut">{b}</div></div>' for a, b in spec)
    P.append(page(f'''{title('Tillämpningar', 'Hålkort', w=560)}
{kort}<div class="abs" style="left:{M}px;top:640px;width:1003px;display:flex;gap:20px">{sp}</div>
{txt(640, 94, 423, '<p class="sm mut">Hålkorten för hål 3, 14 och 17 som de ser ut i dag. Alla 18 hål följer samma uppställning. Före tryck sätts korten med profilens typsnitt och godkänns av klubben hål för hål.</p>')}''', 13, lm=True))

    # 14 Hålskylt ------------------------------------------------
    s = 0.56  # px per cm*10 -> skylt 700 x 1000 mm = 392 x 560 px
    sw_, sh_ = 700 * s, 1000 * s
    sign = f'''<div class="abs" style="left:{M + 40}px;top:150px;width:{sw_:.0f}px;height:{sh_:.0f}px;background:{SJO};padding:8px;box-shadow:0 16px 36px rgba(16,32,46,.25);display:flex;flex-direction:column;gap:6px">
 <div style="height:{150 * s:.0f}px;background:{DJUP};color:{KRIST};display:flex;align-items:center;justify-content:center;font:400 34px Spectral">Nordvik-hålet</div>
 <div style="flex:1;background:{DJUP};color:{KRIST};position:relative">
   <div class="abs" style="left:10px;top:10px;width:146px;bottom:10px;background:url(img/hal-14-malad.png) 50% 50%/contain no-repeat"></div>
   <div class="abs" style="left:176px;top:22px;width:180px">
     <div style="font:400 84px/1 Spectral">14</div>
     <div style="font:600 9px Hanken;letter-spacing:.2em;color:{GLOD};margin:10px 0 12px">PAR 4 · INDEX 1</div>
     <div style="font:500 11px/1.9 Hanken">60 · 369 m<br>56 · 335 m<br>52 · 49 · 44 · 290 m</div>
     <div style="font:400 15px/1.3 Spectral;margin-top:22px">Banans svåraste utslag.</div>
     <div style="font:400 9.5px/1.5 Hanken;margin-top:6px;opacity:.85">Ett smalt dogleg höger. Out längs hela vänstersidan.</div>
   </div>
   <div class="abs" style="left:176px;bottom:10px;width:180px;font:400 6px/1.3 Hanken;opacity:.6">{LM}</div>
 </div>
 <div style="height:{200 * s:.0f}px;background:{KRIST};color:{DJUP};position:relative">
   <div class="abs" style="left:16px;top:16px;font:600 7px Hanken;letter-spacing:.2em;color:{GRON}">PRESENTERAS AV</div>
   <div class="abs" style="left:16px;top:38px;font:500 30px/1 Spectral;letter-spacing:.02em">Nordvik</div>
   <div class="abs" style="left:16px;top:74px;font:600 7px Hanken;letter-spacing:.3em">BYGG &amp; TRÄ</div>
   <img src="img/qr.svg" class="abs" style="right:16px;top:14px;width:68px;height:68px">
   <div class="abs" style="right:16px;top:86px;width:68px;text-align:center;font:500 7px Hanken;color:{GRON}">glasriketsgk.se</div>
 </div></div>'''
    spec = [('Format', '70 × 100 cm, stående.'), ('Platta 1 · Rubrik', 'Sponsorns namn följt av ”-hålet”, i Spectral. Sand på Djupglas.'),
            ('Platta 2 · Hålguide', 'Hålbild, nummer, par, index och längder. Byts aldrig.'),
            ('Platta 3 · Sponsor', 'Sponsorns logga i en färg och QR-kod på Sand. Byts när sponsorn byts.'),
            ('Ram', 'Sjöglas runt plattorna.'), ('Tillverkning', 'Ecosign. Färger stäms av mot tryckprov.')]
    sp = ''.join(f'<div class="rule" style="padding:8px 0"><div class="sm b">{a}</div><div class="sm mut">{b}</div></div>' for a, b in spec)
    P.append(page(f'''{title('Tillämpningar', 'Hålskylt', w=560)}
{sign}<div class="abs" style="left:560px;top:150px;width:503px">{sp}</div>
{txt(560, 540, 503, '<p class="xs mut">Nordvik är en påhittad exempelsponsor. Hålguiden visar riktiga uppgifter för hål 14. QR-koden leder till hålets sida på klubbens webbplats.</p>')}''', 14, lm=True))

    # 15 Sociala medier ------------------------------------------
    pw, ph = 264, 330
    def post(x, inner, bg):
        return f'<div class="abs" style="left:{x}px;top:150px;width:{pw}px;height:{ph}px;background:{bg};overflow:hidden;box-shadow:0 10px 26px rgba(16,32,46,.16)">{inner}</div>'
    lmline = f'<div class="abs" style="left:12px;right:12px;bottom:8px;font:400 4.6px/1.3 Hanken;opacity:.6">{LM}</div>'
    p1 = post(M, f'''<div class="abs" style="left:10px;top:10px;width:110px;bottom:18px;background:url(img/hal-14-malad.png) 50% 50%/contain no-repeat"></div>
<div class="abs" style="left:132px;top:24px;right:12px;color:{KRIST}"><div style="font:600 6.5px Hanken;letter-spacing:.2em;color:{GLOD}">VECKANS HÅL</div>
<div style="font:400 70px/.9 Spectral;margin-top:8px">14</div><div style="font:600 6.5px Hanken;letter-spacing:.14em;margin-top:8px;color:{IS}">PAR 4 · INDEX 1</div>
<div style="font:400 7.5px/1.5 Hanken;margin-top:6px;opacity:.85">60 · 369 m<br>56 · 335 m<br>52 · 49 · 44 · 290 m</div>
<div style="font:400 14px/1.12 Spectral;margin-top:18px">Banans svåraste utslag.</div></div>{lmline}''', DJUP)
    p2 = post(M + pw + 18, f'''{rings(pw, ph, pw / 2, 114, IS, n=7, r0=84, step=22, op=.14)}<div class="abs" style="left:{(pw - 150) / 2}px;top:39px">{seal('mork', 150)}</div>
<div class="abs" style="left:0;right:0;top:218px;text-align:center;color:{KRIST}"><div style="font:600 6.5px Hanken;letter-spacing:.2em;color:{GLOD}">SÄSONGEN 2027</div>
<div style="font:400 20px/1.15 Spectral;margin-top:10px">Banan,<br>hål för hål.</div></div>''', DJUP)
    p3 = post(M + 2 * (pw + 18), f'''<div class="abs" style="left:8px;top:10px;width:118px;bottom:18px;background:url(img/hal-17-malad.png) 50% 50%/contain no-repeat"></div>
<div class="abs" style="left:132px;top:24px;right:12px;color:{KRIST}"><div style="font:600 6.5px Hanken;letter-spacing:.2em;color:{GLOD}">SPELA BANAN</div>
<div style="font:400 70px/.9 Spectral;margin-top:8px">17</div><div style="font:600 6.5px Hanken;letter-spacing:.14em;margin-top:8px;color:{IS}">PAR 3 · INDEX 5</div>
<div style="font:400 7.5px/1.5 Hanken;margin-top:6px;opacity:.85">52 · 56 · 60 · 128 m<br>49 · 44 · 89 m</div>
<div style="font:400 14px/1.12 Spectral;margin-top:18px">Banans signaturhål.</div></div>{lmline}''', DJUP)
    icons = {
        'Banan': f'<path d="M-5 9V-10l11 4-11 4" fill="none" stroke="{IS}" stroke-width="1.6"/><ellipse cx="-2" cy="9" rx="9" ry="2.4" fill="none" stroke="{IS}" stroke-width="1.4"/>',
        'Sponsorer': f'<path d="M0-11L2.2-2.2 11 0 2.2 2.2 0 11-2.2 2.2-11 0-2.2-2.2Z" fill="{GLOD}"/>',
        'Tävlingar': f'<path d="M-8-9h16v4a8 8 0 0 1-16 0zM0 3v5M-5 10h10" fill="none" stroke="{IS}" stroke-width="1.6"/>',
        'Klubben': f'<path d="M0-11l6 8h-3l5 7h-3l5 7h-20l5-7h-3l5-7h-3z" fill="{IS}"/>',
        'Kontakt': f'<circle r="10" fill="none" stroke="{IS}" stroke-width="1.6"/><path d="M0-5v6l4 3" fill="none" stroke="{IS}" stroke-width="1.6"/>'}
    ic = ''.join(f'<div style="text-align:center;width:60px"><svg width="54" height="54" viewBox="-27 -27 54 54"><circle r="26" fill="{DJUP}"/>{g}</svg><div class="xs" style="margin-top:6px">{t}</div></div>' for t, g in icons.items())
    P.append(page(f'''{title('Tillämpningar', 'Sociala medier', w=560)}
{txt(640, 94, 423, '<p class="sm mut">Inlägg i 4:5 på Djupglas som visar hela hålet. Tre fästa inlägg överst i flödet och höjdpunkter i klubbens färger.</p>')}
{p1}{p2}{p3}
<div class="abs" style="left:{M}px;top:494px;width:{3 * pw + 36}px"><div class="cap">Fästa inlägg: veckans hål, sigillet och spela banan. Lantmäteriets upphovsrad följer med varje publik hålbild.</div></div>
<div class="abs" style="left:906px;top:150px;width:157px"><h3 style="color:{GRON}">Profilbild</h3>
<div style="margin-top:12px;width:120px;height:120px;border-radius:50%;background:{DJUP};display:flex;align-items:center;justify-content:center">{seal('mork', 104)}</div>
<div class="xs mut" style="margin-top:8px">Färgad version på Djupglas, beskuren rund.</div></div>
<div class="abs" style="left:{M}px;top:570px;width:600px"><h3 style="color:{GRON}">Höjdpunkter</h3><div style="display:flex;gap:22px;margin-top:12px">{ic}</div></div>
{txt(640, 570, 423, '<p class="sm">Text i inlägg: en kort rubrik i Spectral, fakta i Hanken. Hålnummer och längder hämtas alltid från hålkortet.</p>')}''', 15))

    # 16 Profilprodukter -----------------------------------------
    pr = [('img/troja_af.jpg', '50% 45%', '150%', 'Stickad tröja', 'Brodyr på vänster bröst, 45–55 mm.'),
          ('img/keps-A-frame.jpg', '50% 40%', 'cover', 'Keps, sex paneler', 'Brodyr centrerad på framstycket, 55–65 mm.'),
          ('img/keps-5-panel.jpg', '50% 40%', 'cover', 'Keps, fem paneler', 'Brodyr på framstycket, 55–65 mm.'),
          ('img/handduk_af.jpg', '50% 55%', '125%', 'Handduk', 'Enfärg Djupglas på vävd etikett.')]
    gw = 236
    g = ''.join(f'<div class="abs" style="left:{M + i * (gw + 18)}px;top:160px;width:{gw}px;height:{gw * 1.3:.0f}px;background:url({f}) {pos}/{sz}"></div>'
                f'<div class="abs" style="left:{M + i * (gw + 18)}px;top:{160 + gw * 1.3 + 10:.0f}px;width:{gw}px"><div class="sm b">{t}</div><div class="sm mut">{d}</div></div>'
                for i, (f, pos, sz, t, d) in enumerate(pr))
    P.append(page(f'''{title('Tillämpningar', 'Profilprodukter', w=560)}
{txt(640, 94, 423, '<p class="sm mut">Kläder broderas med den färgade mörka versionen på mörka plagg och enfärg Djupglas på ljusa. Sigillet placeras på vänster bröst eller mitt fram, aldrig på ärmen.</p>')}{g}
{txt(M, 560, 1000, '<p class="sm">Minsta storlek för brodyr är 50 mm. Ringtexten är den känsligaste delen, så beställ alltid en provbrodyr och godkänn den innan en hel serie syrs. Trådfärger väljs mot provet, nära Glöd, Sand och Djupglas.</p>')}''', 16, ft_text='Produktbilderna är visualiseringar som visar placeringen'))

    # 17 Filpaket och märkning -----------------------------------
    files = [('Sigillet', 'Färgad ljus botten, färgad mörk botten, enfärg Djupglas, brons och vit. SVG, PDF och PNG.'),
             ('Brodyr', 'Montage på keps med fem och sex paneler, som underlag till brodyrfirman.'),
             ('Färger', 'HEX och RGB. CMYK och Pantone kommer efter tryckprov.'),
             ('Typsnitt', 'Spectral (Regular, Medium, Kursiv) och Hanken Grotesk (Regular, Medium, SemiBold), med licens.'),
             ('Hålbilder', 'Hålbilder och hålkort, hål för hål när de är godkända av klubben.')]
    fl = ''.join(f'<div class="rule" style="display:flex;padding:11px 0"><div style="width:150px;font:400 17px/1.2 Spectral">{a}</div><div class="sm" style="flex:1;opacity:.85">{b}</div></div>' for a, b in files)
    P.append(page(f'''{rings(W, H, M + 60, H - 120, IS, n=9, r0=100, step=40, op=.1)}<div class="abs" style="left:{M}px;bottom:60px">{seal('mork', 120)}</div>
{title('Filer', 'Filpaket och märkning', w=560)}
<div class="abs" style="left:{M}px;top:170px;width:520px">{fl}</div>
<div class="abs" style="left:640px;top:170px;width:423px">
 <h3 style="color:{GLOD}">Upphov</h3>
 <p class="sm" style="margin-top:8px">Hålbilder, hålkort och visualiseringar bygger på Lantmäteriets öppna data. Allt publikt material som visar dem har raden:</p>
 <div style="font:400 15px/1.4 Spectral;margin:12px 0 26px;padding-left:14px;border-left:2px solid {GLOD}">{LM}</div>
 <h3 style="color:{GLOD}">Märkning</h3>
 <p class="sm" style="margin-top:8px">Bilder märks aldrig med hur de är gjorda, varken i bildtext, alt-text eller sidfot. Där det behövs räcker en diskret rad i sidfoten: ”Vissa bilder är visualiseringar.”</p>
 <h3 style="color:{GLOD};margin-top:26px">Frågor om profilen</h3>
 <p class="sm" style="margin-top:8px">Klubbens kansli äger profilen. Behövs en ny variant eller tillämpning, utgå från manualen och fråga hellre än gissa.</p>
</div>''', 17, dark=True))

    # 18 Baksida -------------------------------------------------
    P.append(page(f'''{rings(W, H, W / 2, 340, IS, n=10, r0=180, step=40, op=.1)}
<div class="abs" style="left:{(W - 220) / 2}px;top:230px">{seal('mork', 220)}</div>
<div class="abs" style="left:0;right:0;top:500px;text-align:center"><div style="font:400 26px Spectral">Glasrikets Golfklubb</div>
<div class="xs" style="margin-top:12px;opacity:.65;letter-spacing:.06em">Grafisk manual · {VERSION}</div></div>
<div class="abs xs" style="left:0;right:0;bottom:40px;text-align:center;opacity:.5">Profil och manual: TACADA</div>''', dark=True))


def render(out):
    os.chdir(out)
    build_pages()
    head = f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
    open('manual.html', 'w').write(head + ''.join(P) + '</body></html>')
    os.makedirs('sidor', exist_ok=True)
    for i, p in enumerate(P, 1):
        fn = f'p{i:02d}.html'
        open(fn, 'w').write(head + p + '</body></html>')
        subprocess.run([HS, '--no-sandbox', '--hide-scrollbars', f'--window-size={W},{H}', '--force-device-scale-factor=2',
                        '--virtual-time-budget=8000', f'--screenshot=sidor/s{i:02d}.png', f'file://{out}/{fn}'], capture_output=True)
    subprocess.run([HS, '--no-sandbox', '--virtual-time-budget=30000', '--no-pdf-header-footer',
                    '--print-to-pdf=manual.pdf', f'file://{out}/manual.html'], capture_output=True)
    from PIL import Image
    for f in sorted(glob.glob('sidor/s*.png')):
        Image.open(f).convert('RGB').save(f[:-4] + '.jpg', quality=88); os.remove(f)
    # Översikt: 6 x 3
    th = [Image.open(f) for f in sorted(glob.glob('sidor/s*.jpg'))]
    tw_, tg = 480, 24
    th_ = round(tw_ * H / W)
    cols = 6; rows = -(-len(th) // cols)
    ov = Image.new('RGB', (cols * tw_ + (cols + 1) * tg, rows * th_ + (rows + 1) * tg), (229, 218, 194))
    for i, im in enumerate(th):
        ov.paste(im.resize((tw_, th_), Image.LANCZOS), (tg + (i % cols) * (tw_ + tg), tg + (i // cols) * (th_ + tg)))
    ov.save('oversikt.jpg', quality=88)
    print(len(P), 'sidor')


if __name__ == '__main__':
    out = os.path.abspath(sys.argv[1])
    os.makedirs(out, exist_ok=True)
    prep(out)
    render(out)
