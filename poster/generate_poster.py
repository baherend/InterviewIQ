#!/usr/bin/env python3
"""
InterviewIQ Academic Poster Generator — v2
Generates a 6262×11811 pt (portrait) print-ready PDF poster.
Closely matches the colleague reference layout.
"""

import os, io, math
from reportlab.lib.colors import Color, HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

# ============================================================
# CANVAS
# ============================================================
W = 6262
H = 11811

# ============================================================
# PALETTE
# ============================================================
DARK_NAVY    = HexColor('#0B1F3F')
MID_NAVY     = HexColor('#132D5E')
CYAN_ACC     = HexColor('#00BCD4')
TURQ         = HexColor('#00ACC1')
PURPLE       = HexColor('#7B1FA2')
LT_PURPLE    = HexColor('#CE93D8')
LIGHT_BG     = HexColor('#EBF5FB')
CARD_BG      = HexColor('#F5F9FC')
CARD_BD      = HexColor('#B0BEC5')
GREEN        = HexColor('#2E7D32')
ORANGE       = HexColor('#E65100')
GOLD         = HexColor('#F9A825')
WH           = white
BK           = black
DARK_T       = HexColor('#1A1A2E')
MED_T        = HexColor('#37474F')
LIGHT_T      = HexColor('#546E7A')
R_BLUE       = HexColor('#E3F2FD')
R_PURP       = HexColor('#F3E5F5')
R_GREEN      = HexColor('#E8F5E9')
INFO_BG      = HexColor('#0D2137')
TEAL_DARK    = HexColor('#00695C')
BLUE_DARK    = HexColor('#01579B')

# ============================================================
# FONTS
# ============================================================
def _reg():
    dirs = ["C:/Windows/Fonts", os.path.expanduser("~/.fonts")]
    ok = {}
    for nm, fn in [("DV","DejaVuSans.ttf"),("DVB","DejaVuSans-Bold.ttf"),
                    ("DVI","DejaVuSans-Oblique.ttf"),("DVBI","DejaVuSans-BoldOblique.ttf")]:
        found = False
        for d in dirs:
            p = os.path.join(d, fn)
            if os.path.exists(p):
                try: pdfmetrics.registerFont(TTFont(nm, p)); found = True; break
                except: pass
        ok[nm] = found
    return ok
F = _reg()

def fn(bold=False, italic=False):
    if bold and italic and F.get("DVBI"): return "DVBI"
    if bold and F.get("DVB"): return "DVB"
    if italic and F.get("DVI"): return "DVI"
    if F.get("DV"): return "DV"
    if bold: return "Helvetica-Bold"
    if italic: return "Helvetica-Oblique"
    return "Helvetica"

# ============================================================
# DRAWING PRIMITIVES
# ============================================================
def rrect(c, x, y, w, h, r=12, fill=None, stroke=None, sw=1.5):
    p = c.beginPath()
    r = min(r, w/2, h/2)
    p.moveTo(x+r,y); p.lineTo(x+w-r,y); p.arcTo(x+w-r,y,x+w,y+r,r)
    p.lineTo(x+w,y+h-r); p.arcTo(x+w,y+h-r,x+w-r,y+h,r)
    p.lineTo(x+r,y+h); p.arcTo(x+r,y+h,x,y+h-r,r)
    p.lineTo(x,y+r); p.arcTo(x,y+r,x+r,y,r); p.close()
    if fill: c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)

def rect(c, x, y, w, h, fill=None, stroke=None, sw=1):
    if fill: c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.rect(x,y,w,h, fill=1 if fill else 0, stroke=1 if stroke else 0)

def txt(c, x, y, t, sz=16, clr=BK, bold=False, italic=False):
    c.setFont(fn(bold,italic), sz); c.setFillColor(clr); c.drawString(x,y,t)

def ctxt(c, x, y, t, sz=16, clr=BK, bold=False, italic=False):
    c.setFont(fn(bold,italic), sz); c.setFillColor(clr); c.drawCentredString(x,y,t)

def rtxt(c, x, y, t, sz=16, clr=BK, bold=False):
    c.setFont(fn(bold), sz); c.setFillColor(clr); c.drawRightString(x,y,t)

def mtxt(c, x, y, lines, sz=14, clr=BK, bold=False, lh=None):
    if lh is None: lh = sz*1.4
    for i,l in enumerate(lines):
        txt(c, x, y-i*lh, l, sz, clr, bold)

def pill(c, x, y, t, bg, tc=WH, sz=13, px=14, py=5):
    c.setFont(fn(True), sz); tw = c.stringWidth(t, fn(True), sz)
    pw, ph = tw+px*2, sz+py*2
    rrect(c, x, y, pw, ph, r=ph/2, fill=bg)
    c.setFillColor(tc); c.drawString(x+px, y+py+1, t)
    return pw, ph

def sec_hdr(c, x, y, w, t, bg=DARK_NAVY, tc=WH, sz=20):
    h = sz + 22
    rrect(c, x, y, w, h, r=10, fill=bg)
    txt(c, x+18, y+10, t, sz, tc, bold=True)
    return h

def arrow_d(c, x, y1, y2, clr=MED_T, lw=2):
    c.setStrokeColor(clr); c.setLineWidth(lw)
    c.line(x,y1,x,y2); c.line(x,y2,x-5,y2+7); c.line(x,y2,x+5,y2+7)

def arrow_r(c, x1, x2, y, clr=MED_T, lw=2):
    c.setStrokeColor(clr); c.setLineWidth(lw)
    c.line(x1,y,x2,y); c.line(x2,y,x2-7,y+4); c.line(x2,y,x2-7,y-4)

def pipe_step(c, x, y, w, h, t, bg=LIGHT_BG, bd=CARD_BD, sz=12):
    rrect(c, x, y, w, h, r=8, fill=bg, stroke=bd, sw=1)
    c.setFont(fn(True), sz); c.setFillColor(DARK_T)
    tw = c.stringWidth(t, fn(True), sz)
    c.drawString(x+(w-tw)/2, y+h/2-sz/3, t)

def flow_box(c, x, y, w, h, t, bg=DARK_NAVY, tc=WH, sz=14, r=8):
    rrect(c, x, y, w, h, r=r, fill=bg)
    c.setFont(fn(True), sz); c.setFillColor(tc)
    tw = c.stringWidth(t, fn(True), sz)
    c.drawString(x+(w-tw)/2, y+h/2-sz/3, t)

def result_card(c, x, y, w, h, lbl, val, bg=R_BLUE, vc=DARK_NAVY, lc=MED_T, vs=28, ls=11):
    rrect(c, x, y, w, h, r=10, fill=bg)
    c.setFont(fn(True), vs); c.setFillColor(vc)
    tw = c.stringWidth(val, fn(True), vs)
    c.drawString(x+(w-tw)/2, y+h/2+2, val)
    c.setFont(fn(False), ls); c.setFillColor(lc)
    tw2 = c.stringWidth(lbl, fn(False), ls)
    c.drawString(x+(w-tw2)/2, y+h/2-vs+2, lbl)

# ============================================================
# QR CODE GENERATOR
# ============================================================
def make_qr_image(url_or_text, size_px=600):
    """Generate a QR code as a PIL Image."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url_or_text)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255,255,255),
            front_color=(11,31,63)  # dark navy
        ),
    )
    return img

def draw_qr_on_canvas(c, img, x, y, size_pt):
    """Draw a PIL Image onto the canvas at (x,y) with given size."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(tmp, format='PNG')
    tmp.close()
    c.drawImage(tmp.name, x, y, size_pt, size_pt, preserveAspectRatio=True, mask='auto')
    try: os.unlink(tmp.name)
    except: pass

# ============================================================
# LOGO DRAWING
# ============================================================
def draw_academy_logo(c, cx, cy, r):
    """Egyptian Military Academy style logo."""
    # Outer dark ring
    c.setStrokeColor(HexColor('#1A237E')); c.setLineWidth(5)
    c.setFillColor(HexColor('#0D47A1'))
    c.circle(cx, cy, r, fill=1, stroke=1)
    # Gold inner ring
    c.setStrokeColor(GOLD); c.setLineWidth(3)
    c.circle(cx, cy, r*0.82, fill=0, stroke=1)
    # Center eagle/shield shape
    c.setFillColor(GOLD)
    c.circle(cx, cy, r*0.38, fill=1, stroke=0)
    # Inner detail
    c.setFillColor(HexColor('#0D47A1'))
    c.circle(cx, cy, r*0.22, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont(fn(True), r*0.22)
    c.drawCentredString(cx, cy-r*0.07, "*")
    # Labels
    c.setFont(fn(True), r*0.16); c.setFillColor(WH)
    c.drawCentredString(cx, cy+r*0.52, "EGYPTIAN MILITARY")
    c.drawCentredString(cx, cy-r*0.52, "ACADEMY")

def draw_academy_logo2(c, cx, cy, r):
    """Second academy logo (slightly different)."""
    c.setStrokeColor(HexColor('#B71C1C')); c.setLineWidth(5)
    c.setFillColor(HexColor('#C62828'))
    c.circle(cx, cy, r, fill=1, stroke=1)
    c.setStrokeColor(GOLD); c.setLineWidth(3)
    c.circle(cx, cy, r*0.82, fill=0, stroke=1)
    c.setFillColor(GOLD)
    c.circle(cx, cy, r*0.38, fill=1, stroke=0)
    c.setFillColor(HexColor('#C62828'))
    c.circle(cx, cy, r*0.22, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont(fn(True), r*0.22)
    c.drawCentredString(cx, cy-r*0.07, "*")
    c.setFont(fn(True), r*0.16); c.setFillColor(WH)
    c.drawCentredString(cx, cy+r*0.52, "NATIONAL")
    c.drawCentredString(cx, cy-r*0.52, "DEFENSE COLLEGE")

def draw_digilians_logo(c, cx, cy, r):
    """Digilians logo."""
    # Hexagonal base
    c.setFillColor(CYAN_ACC); c.circle(cx, cy, r, fill=1, stroke=0)
    # Shield shape
    c.setFillColor(WH)
    c.setFont(fn(True), r*0.55)
    c.drawCentredString(cx, cy-r*0.15, "D")
    c.setFont(fn(True), r*0.17)
    c.drawCentredString(cx, cy-r*0.58, "DIGILIANS")

def draw_ministry_logo(c, cx, cy, r):
    """Ministry of Communications logo."""
    c.setFillColor(HexColor('#1B5E20')); c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont(fn(True), r*0.28)
    c.drawCentredString(cx, cy+r*0.1, "وزارة")
    c.setFont(fn(True), r*0.2)
    c.drawCentredString(cx, cy-r*0.2, "الاتصالات")

# ============================================================
# HEADER
# ============================================================
def draw_header(c):
    # Dark navy header band
    rect(c, 0, H-530, W, 530, fill=DARK_NAVY)
    # Cyan accent line
    rect(c, 0, H-533, W, 4, fill=CYAN_ACC)

    # Main title
    c.setFont(fn(True), 148)
    c.setFillColor(WH)
    c.drawCentredString(W/2, H-210, "InterviewIQ")

    # Subtitle
    c.setFont(fn(False), 46)
    c.setFillColor(CYAN_ACC)
    c.drawCentredString(W/2, H-295, "AI-Powered Multimodal Mock Interview Evaluation Platform")

    # Left logos
    logo_y = H-430
    draw_academy_logo(c, 320, logo_y, 95)
    draw_academy_logo2(c, 560, logo_y, 85)

    # Right logos
    draw_digilians_logo(c, W-430, logo_y, 88)
    draw_ministry_logo(c, W-210, logo_y, 82)

    # Personnel info
    info_y = H-385
    # Presented by
    txt(c, 780, info_y, "Presented by:", 24, HexColor('#90CAF9'))
    names = ["Hossam Abdelaziz Ahmed","Khaled Elnoselhy","Baher Azer",
             "Ahmed Fouad Hashem","Abdelrhman Mousa"]
    for i,nm in enumerate(names):
        txt(c, 780, info_y-28-i*26, nm, 21, WH)

    # Supervision
    txt(c, 2700, info_y, "Under Supervision of:", 24, HexColor('#90CAF9'))
    txt(c, 2700, info_y-28, "Maj. Gen. (R.) Prof. Dr.", 21, WH)
    txt(c, 2700, info_y-54, "Gouda Ismail Salama", 21, WH)

    # TA
    txt(c, 4300, info_y, "Section Teaching Assistant:", 24, HexColor('#90CAF9'))
    txt(c, 4300, info_y-28, "Eng. Omar", 21, WH)

    # Year
    txt(c, 4300, info_y-70, "Academic Year:", 24, HexColor('#90CAF9'))
    txt(c, 4300, info_y-98, "2025 / 2026", 21, WH)

def draw_info_bar(c):
    by = H-625; bh = 82
    rect(c, 0, by, W, bh, fill=INFO_BG)
    rect(c, 0, by+bh, W, 4, fill=CYAN_ACC)

# ============================================================
# LEFT COLUMN
# ============================================================
def draw_left(c, x, y0, w):
    y = y0; pad = 28

    # 01 ABSTRACT
    h = sec_hdr(c, x, y-34, w, "01  ABSTRACT"); y -= 34+h+14
    ch = 350
    rrect(c, x, y-ch, w, ch, r=12, fill=CARD_BG, stroke=CARD_BD)
    lines = [
        "InterviewIQ is a web-based multimodal",
        "mock-interview coaching platform that",
        "evaluates technical answer correctness,",
        "vocal emotion, and temporal visual behavior.",
        "",
        "The system separates Technical Score, Model",
        "Classification Confidence, and behavioral",
        "delivery indicators to provide interpretable",
        "feedback without treating classifiers as",
        "abilities, probabilities as direct measurements",
        "of competence, or personal confidence.",
    ]
    mtxt(c, x+pad, y-28, lines, 15, DARK_T, lh=21)
    pill(c, x+pad, y-ch+18, "NLP + AUDIO + VISION", CYAN_ACC)
    y -= ch+22

    # 02 AIM OF THE WORK
    h = sec_hdr(c, x, y-34, w, "02  AIM OF THE WORK"); y -= 34+h+14
    ch = 300
    rrect(c, x, y-ch, w, ch, r=12, fill=CARD_BG, stroke=CARD_BD)
    aims = [
        (">>  Develop an interpretable AI-powered", GREEN),
        ("    multimodal mock-interview platform", DARK_T),
        ("", None),
        (">>  Provide structured feedback on Technical", GREEN),
        ("    Answer Correctness, Vocal Delivery, and", DARK_T),
        ("    Visual Behavioral Patterns.", DARK_T),
        ("", None),
        (">>  Position the system as an Interview", GREEN),
        ("    Coaching & Research Prototype, not an", DARK_T),
        ("    Autonomous Hiring System.", DARK_T),
    ]
    for i,(t,c_) in enumerate(aims):
        if t: txt(c, x+pad, y-26-i*25, t, 15, c_ or DARK_T, bold=(">>" in t))
    y -= ch+22

    # 03 DATASET
    h = sec_hdr(c, x, y-34, w, "03  DATASET"); y -= 34+h+14
    sub_w = (w-20)/2; sub_h = 400

    # BAVED card
    rrect(c, x, y-sub_h, sub_w, sub_h, r=12, fill=CARD_BG, stroke=CARD_BD)
    # Header band
    rrect(c, x, y-38, sub_w, 38, r=12, fill=BLUE_DARK)
    rect(c, x, y-38, sub_w, 14, fill=BLUE_DARK)
    txt(c, x+14, y-30, "BAVED – AUDIO", 16, WH, bold=True)
    # Mic icon
    c.setFillColor(R_BLUE); c.circle(x+sub_w/2, y-85, 30, fill=1, stroke=0)
    txt(c, x+sub_w/2-8, y-92, "(mic)", 14, DARK_T)
    # Info
    ty = y-130
    for i,t in enumerate(["• 1,935 Audio Recordings","• 60 Speaker IDs","• 7 Arabic Words"]):
        txt(c, x+18, ty-i*22, t, 14, DARK_T)
    # Table
    ty2 = ty-90
    txt(c, x+18, ty2, "Split       Actors    Samples", 13, DARK_NAVY, bold=True)
    for i,r in enumerate(["Train      1–18       3,656","Valid.     19–21     624","Test       22–24     624"]):
        txt(c, x+18, ty2-22-i*20, r, 13, DARK_T)

    # RAVDESS card
    rx = x+sub_w+20
    rrect(c, rx, y-sub_h, sub_w, sub_h, r=12, fill=CARD_BG, stroke=CARD_BD)
    rrect(c, rx, y-38, sub_w, 38, r=12, fill=PURPLE)
    rect(c, rx, y-38, sub_w, 14, fill=PURPLE)
    txt(c, rx+14, y-30, "RAVDESS – VISUAL", 16, WH, bold=True)
    c.setFillColor(R_PURP); c.circle(rx+sub_w/2, y-85, 30, fill=1, stroke=0)
    txt(c, rx+sub_w/2-8, y-92, "(vid)", 14, DARK_T)
    ty = y-130
    for i,t in enumerate(["• 24 Professional Actors","• 8 Acted Emotion Categories"]):
        txt(c, rx+18, ty-i*22, t, 14, DARK_T)
    ty2 = ty-65
    txt(c, rx+18, ty2, "Split       Actors    Samples", 13, DARK_NAVY, bold=True)
    for i,r in enumerate(["Train      1–18       3,656","Valid.     19–21     624","Test       22–24     624"]):
        txt(c, rx+18, ty2-22-i*20, r, 13, DARK_T)

    y -= sub_h+22

    # 04 TOOLS
    h = sec_hdr(c, x, y-34, w, "04  USED TOOLS & TECHNOLOGIES"); y -= 34+h+14
    tch = 460
    rrect(c, x, y-tch, w, tch, r=12, fill=CARD_BG, stroke=CARD_BD)
    tools = [
        ("React", HexColor('#61DAFB'), DARK_T),
        ("FastAPI", TEAL_DARK, WH),
        ("Python", HexColor('#3776AB'), WH),
        ("SQLAlchemy", HexColor('#D71F00'), WH),
        ("Whisper", HexColor('#FF6F00'), WH),
        ("BGE-M3", HexColor('#1565C0'), WH),
        ("(Embedding)", HexColor('#1565C0'), WH),
        ("mDeBERTa", HexColor('#6A1B9A'), WH),
        ("Wav2Vec2", HexColor('#00838F'), WH),
        ("BLSTM", HexColor('#283593'), WH),
        ("PyTorch", HexColor('#EE4C2C'), WH),
        ("TCN", TEAL_DARK, WH),
        ("Swin", HexColor('#4527A0'), WH),
        ("Transformer", HexColor('#4527A0'), WH),
        ("LoRA / PEFT", ORANGE, WH),
    ]
    cols = 4; tw_ = (w-55)/cols; th_ = 58; gap_ = 12
    for i,(nm,bg,tc) in enumerate(tools):
        col = i%cols; row = i//cols
        tx = x+25+col*(tw_+gap_); ty = y-28-row*(th_+gap_)
        rrect(c, tx, ty-th_, tw_, th_, r=8, fill=bg)
        c.setFont(fn(True), 15); c.setFillColor(tc)
        tw = c.stringWidth(nm, fn(True), 15)
        c.drawString(tx+(tw_-tw)/2, ty-th_/2-5, nm)
    y -= tch+22
    return y

# ============================================================
# CENTER COLUMN
# ============================================================
def draw_center(c, x, y0, w):
    y = y0

    # 05 SYSTEM OVERVIEW
    h = sec_hdr(c, x, y-34, w, "05  SYSTEM OVERVIEW"); y -= 34+h+16
    soh = 1600
    rrect(c, x, y-soh, w, soh, r=12, fill=CARD_BG, stroke=CARD_BD)

    # Top flow
    fy = y-55; bw = 275; bh = 55; gx = 55
    total_fw = 4*bw + 3*gx
    sx = x + (w-total_fw)/2

    boxes = [
        ("Candidate", HexColor('#37474F')),
        ("React + Vite", HexColor('#1565C0')),
        ("FastAPI Backend", TEAL_DARK),
        ("Interview Recording", DARK_NAVY),
    ]
    for i,(t,bg) in enumerate(boxes):
        bx = sx + i*(bw+gx)
        flow_box(c, bx, fy-bh, bw, bh, t, bg=bg, sz=14)
        # small icon circle above
        c.setFillColor(bg); c.circle(bx+bw/2, fy+22, 18, fill=1, stroke=0)
        icons = ["C","W","B","R"]
        c.setFont(fn(True), 14); c.setFillColor(WH)
        c.drawCentredString(bx+bw/2, fy+17, icons[i])
        if i < 3:
            arrow_r(c, bx+bw, bx+bw+gx, fy-bh/2, MED_T)

    # Sub text under last box
    c.setFont(fn(False), 11); c.setFillColor(HexColor('#90CAF9'))
    ctxt(c, sx+3*(bw+gx)+bw/2, fy-bh+14, "Audio + Video + Question Context", 11, HexColor('#90CAF9'))

    # Arrow down
    mid = x+w/2
    arrow_d(c, mid, fy-bh, fy-bh-45, MED_T)

    # Three pipeline column headers
    pl_y = fy-bh-50; pl_h = 42
    pw3 = (w-50)/3
    headers = [
        ("NLP PIPELINE", BLUE_DARK),
        ("AUDIO PIPELINE", TEAL_DARK),
        ("VISUAL PIPELINE", PURPLE),
    ]
    for i,(t,bg) in enumerate(headers):
        px = x+15+i*(pw3+10)
        flow_box(c, px, pl_y-pl_h, pw3, pl_h, t, bg=bg, sz=14)

    # Pipeline step boxes
    sw = pw3-8; sh = 44; sg = 10; sox = 4

    # --- NLP ---
    nlp = ["Speech","ASR / faster-whisper","Claim Decomposition",
           "BGE-M3 Retrieval","Natural Language Inference","Precision + Coverage"]
    nsy = pl_y-pl_h-sg
    for i,t in enumerate(nlp):
        nsy -= sh+sg
        pipe_step(c, x+sox, nsy, sw, sh, t, bg=LIGHT_BG, sz=12)
    # Tech Score output
    nsy -= sg+55
    flow_box(c, x+sox, nsy, sw, 48, "TECHNICAL SCORE", bg=DARK_NAVY, sz=13)

    # --- AUDIO ---
    audio = ["Audio","Wav2Vec2-Large-XLSR-53","BLSTM","Low / Neutral / High Emotion"]
    asy = pl_y-pl_h-sg
    aox = x+15+pw3+10+sox
    for i,t in enumerate(audio):
        asy -= sh+sg
        pipe_step(c, aox, asy, sw, sh, t, bg=LIGHT_BG, sz=12)
    asy -= sg+55
    flow_box(c, aox, asy, sw, 48, "VOCAL OUTPUT", bg=TEAL_DARK, sz=13)
    c.setFont(fn(False), 10); c.setFillColor(HexColor('#B2DFDB'))
    ctxt(c, aox+sw/2, asy+12, "(Model Confidence)", 10, HexColor('#B2DFDB'))

    # --- VISUAL ---
    vis = ["Video","MTCNN Face Detection","Swin Transformer Tiny + LoRA",
           "Temporal Analysis","Reliability via Evidence Gate"]
    vsy = pl_y-pl_h-sg
    vox = x+15+2*(pw3+10)+sox
    for i,t in enumerate(vis):
        vsy -= sh+sg
        pipe_step(c, vox, vsy, sw, sh, t, bg=HexColor('#F3E5F5'), sz=11)
    vsy -= sg+55
    flow_box(c, vox, vsy, sw, 48, "VISUAL BEHAVIORAL CONF.", bg=PURPLE, sz=12)

    # Indicators
    ind_y = nsy-70
    iw = (sw-12)/2
    rrect(c, x+sox, ind_y, iw, 42, r=8, fill=R_GREEN, stroke=GREEN, sw=1.5)
    ctxt(c, x+sox+iw/2, ind_y+14, "Vocal Delivery Indicator", 13, GREEN, bold=True)
    rrect(c, aox, ind_y, iw, 42, r=8, fill=R_PURP, stroke=PURPLE, sw=1.5)
    ctxt(c, aox+iw/2, ind_y+14, "Valid Visual Behavioral Conf.", 12, PURPLE, bold=True)

    # Proposed Delivery Indicator
    pdi_y = ind_y-80; pdi_w = w-60
    rrect(c, x+30, pdi_y, pdi_w, 95, r=12, fill=HexColor('#E0F7FA'), stroke=CYAN_ACC, sw=2)
    ctxt(c, x+30+pdi_w/2, pdi_y+62, "PROPOSED DELIVERY INDICATOR", 20, DARK_NAVY, bold=True)
    ctxt(c, x+30+pdi_w/2, pdi_y+18, "60% Vocal + 40% Visual", 34, CYAN_ACC, bold=True)
    # Note
    ctxt(c, x+30+pdi_w/2, pdi_y-22, "Experimental configurable baseline - not human-calibrated", 13, ORANGE, italic=True)

    # Candidate Feedback Report
    cfr_y = pdi_y-70
    flow_box(c, x+w/2-190, cfr_y, 380, 48, "CANDIDATE FEEDBACK REPORT", bg=DARK_NAVY, sz=15)

    y -= soh+22

    # 06 METHODOLOGY
    h = sec_hdr(c, x, y-34, w, "06  METHODOLOGY"); y -= 34+h+14
    mh = 360
    rrect(c, x, y-mh, w, mh, r=12, fill=CARD_BG, stroke=CARD_BD)

    # NLP subflow
    ty = y-32
    txt(c, x+22, ty, "NLP – Answer Correctness", 16, BLUE_DARK, bold=True)
    ty -= 30
    nlp_f = ["ASR","Claim Decomp.","Retrieval\n(BGE-M3)","NLI\n(mDeBERTa)","Precision +\nCoverage","Technical Score"]
    fsw = (w-50)/len(nlp_f); fsh = 55
    for i,t in enumerate(nlp_f):
        sx = x+22+i*(fsw+4)
        lines = t.split('\n')
        rrect(c, sx, ty-fsh, fsw-4, fsh, r=6, fill=R_BLUE)
        c.setFont(fn(True), 11); c.setFillColor(DARK_T)
        tw = c.stringWidth(lines[0], fn(True), 11)
        c.drawString(sx+(fsw-4-tw)/2, ty-fsh/2+(len(lines)-1)*6, lines[0])
        for j in range(1,len(lines)):
            c.setFont(fn(False), 9); c.setFillColor(MED_T)
            tw = c.stringWidth(lines[j], fn(False), 9)
            c.drawString(sx+(fsw-4-tw)/2, ty-fsh/2+(len(lines)-1)*6-j*13, lines[j])
        if i<len(nlp_f)-1:
            c.setStrokeColor(MED_T); c.setLineWidth(1.5)
            c.line(sx+fsw-4, ty-fsh/2, sx+fsw, ty-fsh/2)

    # Audio subflow
    ty -= fsh+42
    txt(c, x+22, ty, "AUDIO – Emotion Recognition", 16, TEAL_DARK, bold=True)
    ty -= 30
    aud_f = ["Wav2Vec2","BLSTM","Emotion Classification\n(Low / Neutral / High)"]
    fsw2 = (w-50)/3
    for i,t in enumerate(aud_f):
        sx = x+22+i*(fsw2+4)
        lines = t.split('\n')
        h2 = fsh + max(0,(len(lines)-1)*13)
        rrect(c, sx, ty-h2, fsw2-4, h2, r=6, fill=HexColor('#E0F2F1'))
        c.setFont(fn(True), 11); c.setFillColor(DARK_T)
        tw = c.stringWidth(lines[0], fn(True), 11)
        c.drawString(sx+(fsw2-4-tw)/2, ty-h2/2+(len(lines)-1)*6, lines[0])
        for j in range(1,len(lines)):
            c.setFont(fn(False), 9); c.setFillColor(MED_T)
            tw = c.stringWidth(lines[j], fn(False), 9)
            c.drawString(sx+(fsw2-4-tw)/2, ty-h2/2+(len(lines)-1)*6-j*13, lines[j])
        if i<len(aud_f)-1:
            c.setStrokeColor(MED_T); c.setLineWidth(1.5)
            c.line(sx+fsw2-4, ty-h2/2, sx+fsw2, ty-h2/2)

    # Visual subflow
    ty -= fsh+50
    txt(c, x+22, ty, "VISUAL – Behavioral Analysis", 16, PURPLE, bold=True)
    ty -= 30
    vis_f = ["MTCNN","Swin + LoRA","Temporal Analysis","Evidence Gate","VBC"]
    fsw3 = (w-50)/5
    for i,t in enumerate(vis_f):
        sx = x+22+i*(fsw3+4)
        rrect(c, sx, ty-fsh, fsw3-4, fsh, r=6, fill=R_PURP)
        c.setFont(fn(True), 11); c.setFillColor(DARK_T)
        tw = c.stringWidth(t, fn(True), 11)
        c.drawString(sx+(fsw3-4-tw)/2, ty-fsh/2-4, t)
        if i<len(vis_f)-1:
            c.setStrokeColor(MED_T); c.setLineWidth(1.5)
            c.line(sx+fsw3-4, ty-fsh/2, sx+fsw3, ty-fsh/2)

    y -= mh+22
    return y

# ============================================================
# RIGHT COLUMN
# ============================================================
def draw_right(c, x, y0, w):
    y = y0

    # 07 RESULTS
    h = sec_hdr(c, x, y-34, w, "07  RESULTS"); y -= 34+h+14

    # Audio results
    arh = 210
    rrect(c, x, y-arh, w, arh, r=12, fill=CARD_BG, stroke=CARD_BD)
    rrect(c, x, y-38, w, 38, r=12, fill=BLUE_DARK)
    rect(c, x, y-38, w, 14, fill=BLUE_DARK)
    txt(c, x+16, y-30, "AUDIO – BAVED NB09 (Source-Domain Results)", 14, WH, bold=True)
    mw = (w-50)/3
    for i,(l,v) in enumerate([
        ("TEST ACCURACY","89.15%"),("MACRO-F1","89.19%"),("NEUTRAL PRECISION","86.36%")]):
        result_card(c, x+15+i*(mw+10), y-arh+18, mw, arh-65, l, v, bg=R_BLUE, vs=30, ls=11)
    y -= arh+16

    # Visual results
    vrh = 240
    rrect(c, x, y-vrh, w, vrh, r=12, fill=CARD_BG, stroke=CARD_BD)
    rrect(c, x, y-38, w, 38, r=12, fill=PURPLE)
    rect(c, x, y-38, w, 14, fill=PURPLE)
    txt(c, x+16, y-30, "VISUAL – RAVDESS (Source-Domain Results)", 14, WH, bold=True)
    mw2 = (w-40)/2; mh2 = 75
    for i,(l,v) in enumerate([
        ("VALIDATION ACCURACY","73.88%"),("TEST ACCURACY","73.24%"),
        ("WEIGHTED F1","72.29%"),("MACRO-F1","68.85%")]):
        col = i%2; row = i//2
        mx = x+15+col*(mw2+10); my = y-58-row*(mh2+12)
        rrect(c, mx, my, mw2, mh2, r=8, fill=R_PURP)
        c.setFont(fn(True), 24); c.setFillColor(PURPLE)
        tw = c.stringWidth(v, fn(True), 24)
        c.drawString(mx+(mw2-tw)/2, my+mh2/2+4, v)
        ctxt(c, mx+mw2/2, my+10, l, 10, MED_T)
    y -= vrh+16

    # NLP results
    nrh = 270
    rrect(c, x, y-nrh, w, nrh, r=12, fill=CARD_BG, stroke=CARD_BD)
    rrect(c, x, y-38, w, 38, r=12, fill=BLUE_DARK)
    rect(c, x, y-38, w, 14, fill=BLUE_DARK)
    txt(c, x+16, y-30, "NLP – REAL CLAIM DISTRIBUTION MISMATCH", 14, WH, bold=True)

    ty = y-68
    txt(c, x+22, ty, "Gold Set Macro-F1", 15, DARK_NAVY, bold=True)
    ty -= 10
    hw = (w-50)/2
    # Zero-shot
    rrect(c, x+20, ty-72, hw, 72, r=8, fill=R_GREEN)
    txt(c, x+32, ty-22, "Zero-shot", 12, MED_T)
    txt(c, x+32, ty-58, "0.880", 28, GREEN, bold=True)
    # LoRA
    rrect(c, x+35+hw, ty-72, hw, 72, r=8, fill=R_GREEN)
    txt(c, x+47+hw, ty-22, "LoRA Adapter", 12, MED_T)
    txt(c, x+47+hw, ty-58, "0.850", 28, GREEN, bold=True)

    ty -= 95
    txt(c, x+22, ty, "Real-Claims Coverage", 15, DARK_NAVY, bold=True)
    ty -= 10
    rrect(c, x+20, ty-72, hw, 72, r=8, fill=HexColor('#FFF3E0'))
    txt(c, x+32, ty-22, "Zero-shot", 12, MED_T)
    txt(c, x+32, ty-58, "0.395", 28, ORANGE, bold=True)
    rrect(c, x+35+hw, ty-72, hw, 72, r=8, fill=HexColor('#FFF3E0'))
    txt(c, x+47+hw, ty-22, "LoRA Adapter", 12, MED_T)
    txt(c, x+47+hw, ty-58, "0.180", 28, ORANGE, bold=True)

    y -= nrh+16

    # 08 PLATFORM ACCESS
    h = sec_hdr(c, x, y-34, w, "08  PLATFORM ACCESS"); y -= 34+h+14
    pah = 290
    rrect(c, x, y-pah, w, pah, r=12, fill=CARD_BG, stroke=CARD_BD)
    rrect(c, x+22, y-pah+22, w-44, pah-44, r=8, fill=HexColor('#263238'))
    ctxt(c, x+w/2, y-pah/2+22, "Master Your Interview.", 24, CYAN_ACC, bold=True)
    ctxt(c, x+w/2, y-pah/2-12, "Get Hired.", 18, HexColor('#B0BEC5'))
    ctxt(c, x+w/2, y-pah/2-45, "Three Independent AI Systems", 13, HexColor('#78909C'))
    y -= pah+16

    # 09 QR CODES
    h = sec_hdr(c, x, y-34, w, "09  QR & DEMO ACCESS"); y -= 34+h+14
    qrh = 400
    rrect(c, x, y-qrh, w, qrh, r=12, fill=CARD_BG, stroke=CARD_BD)

    qr_size = 260
    qr_gap = 40
    total_qr = 2*qr_size + qr_gap
    qsx = x + (w-total_qr)/2

    # Generate QR codes
    qr1_img = make_qr_image("https://interview-iq-demo.example.com")
    qr2_img = make_qr_image("https://github.com/interviewiq")

    # QR 1
    q1x = qsx; q1y = y-50
    rrect(c, q1x, q1y-qr_size-40, qr_size, qr_size+40, r=10, fill=WH, stroke=CARD_BD)
    draw_qr_on_canvas(c, qr1_img, q1x+15, q1y-qr_size-20, qr_size-30)
    ctxt(c, q1x+qr_size/2, q1y-qr_size-55, "Presentation / Demo", 16, DARK_T, bold=True)

    # QR 2
    q2x = qsx+qr_size+qr_gap
    rrect(c, q2x, q1y-qr_size-40, qr_size, qr_size+40, r=10, fill=WH, stroke=CARD_BD)
    draw_qr_on_canvas(c, qr2_img, q2x+15, q1y-qr_size-20, qr_size-30)
    ctxt(c, q2x+qr_size/2, q1y-qr_size-55, "GitHub Repository", 16, DARK_T, bold=True)

    y -= qrh+16

    # 10 CONCLUSION
    h = sec_hdr(c, x, y-34, w, "10  CONCLUSION"); y -= 34+h+14
    cch = 440
    rrect(c, x, y-cch, w, cch, r=12, fill=CARD_BG, stroke=CARD_BD)
    concs = [
        (">>  InterviewIQ demonstrates the feasibility of", GREEN),
        ("    an interpretable multimodal mock-interview", DARK_T),
        ("    coaching architecture.", DARK_T),
        ("", None),
        (">>  Integrates NLP, Audio, Vision, and Web", GREEN),
        ("    technologies successfully.", DARK_T),
        ("", None),
        (">>  Separates Technical Correctness from Delivery", GREEN),
        ("    Indicators and preserves interpretability.", DARK_T),
        ("", None),
        (">>  Current experimental results support the", GREEN),
        ("    research prototype but do not yet establish", DARK_T),
        ("    unrestricted real-world hiring validity.", DARK_T),
        ("", None),
        (">>  Provides a credible engineering foundation for", GREEN),
        ("    explainable AI-assisted interview coaching.", DARK_T),
    ]
    ty = y-30
    for i,(t,clr) in enumerate(concs):
        if t: txt(c, x+28, ty-i*26, t, 15, clr, bold=(">>" in t))
    y -= cch+16

    # 11 FUTURE WORK
    h = sec_hdr(c, x, y-34, w, "11  FUTURE WORK"); y -= 34+h+14
    fwh = 200
    rrect(c, x, y-fwh, w, fwh, r=12, fill=CARD_BG, stroke=CARD_BD)
    futs = [
        "•  Real-time interview analysis",
        "•  Multi-language support",
        "•  HR / ATS integration",
        "•  Advanced transformer-based emotion detection",
    ]
    ty = y-30
    for i,t in enumerate(futs):
        txt(c, x+28, ty-i*30, t, 16, DARK_T)
    y -= fwh+16
    return y

# ============================================================
# MAIN
# ============================================================
def generate(path):
    c = canvas.Canvas(path, pagesize=(W, H))
    c.setTitle("InterviewIQ – Academic Poster")
    c.setAuthor("InterviewIQ Team")

    # White background
    rect(c, 0, 0, W, H, fill=WH)

    # Columns
    mg = 42; cg = 32
    tw_ = W - 2*mg - 2*cg
    cw = tw_/3
    c1x = mg
    c2x = mg + cw + cg
    c3x = mg + 2*(cw+cg)
    ct = H - 650

    draw_header(c)
    draw_info_bar(c)
    draw_left(c, c1x, ct, cw)
    draw_center(c, c2x, ct, cw)
    draw_right(c, c3x, ct, cw)

    # Footer
    rect(c, 0, 0, W, 8, fill=CYAN_ACC)

    c.save()
    print(f"Poster saved: {path}")
    print(f"Canvas: {W} x {H} pt ({W/72:.1f}\" x {H/72:.1f}\" at 72 DPI)")
    print(f"At 150 DPI: {W/150:.1f}\" x {H/150:.1f}\"")

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "InterviewIQ_Poster.pdf")
    generate(out)
