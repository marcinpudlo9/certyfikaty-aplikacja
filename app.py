import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Optional

import fitz
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Generator certyfikatow", page_icon="📄", layout="wide")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(APP_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

@dataclass
class TextStyle:
    x_pct: float
    y_pct: float
    size: int
    color: str
    align: str
    prefix: str = ""


def safe_name(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"[^A-Za-z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ._ -]+", "", value)
    value = value.replace(" ", "_")
    return value[:120] or "certyfikat"


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def load_template(uploaded_file) -> Image.Image:
    raw = uploaded_file.getvalue()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        doc = fitz.open(stream=raw, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()
        return img
    return Image.open(io.BytesIO(raw)).convert("RGB")


def get_font(font_file, size: int):
    if font_file:
        font_path = os.path.join(TEMP_DIR, "uploaded_font" + os.path.splitext(font_file.name)[1])
        with open(font_path, "wb") as f:
            f.write(font_file.getvalue())
        return ImageFont.truetype(font_path, size=size), font_path
    # DejaVu exists in most Linux/Streamlit environments and supports Polish chars.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size), path
    return ImageFont.load_default(), None


def draw_text_on_image(img: Image.Image, text: str, style: TextStyle, font_file=None) -> Image.Image:
    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    font, _ = get_font(font_file, style.size)
    x = int(out.width * style.x_pct / 100)
    y = int(out.height * style.y_pct / 100)
    text = f"{style.prefix}{text}".strip()
    rgb = hex_to_rgb(style.color)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    if style.align == "Srodek":
        x -= width // 2
    elif style.align == "Prawo":
        x -= width
    draw.text((x, y), text, fill=rgb, font=font)
    return out


def compose_certificate(template: Image.Image, row: pd.Series, fields: dict, styles: dict, font_file=None) -> Image.Image:
    img = template.copy().convert("RGB")
    full_name_parts = []
    if fields.get("first") and fields["first"] != "-- brak --":
        full_name_parts.append(str(row.get(fields["first"], "")))
    if fields.get("last") and fields["last"] != "-- brak --":
        full_name_parts.append(str(row.get(fields["last"], "")))
    full_name = " ".join([p.strip() for p in full_name_parts if p and str(p) != "nan"])
    if full_name:
        img = draw_text_on_image(img, full_name, styles["name"], font_file)
    if fields.get("npwz") and fields["npwz"] != "-- brak --":
        value = str(row.get(fields["npwz"], "")).replace(".0", "")
        if value and value != "nan":
            img = draw_text_on_image(img, value, styles["npwz"], font_file)
    if fields.get("extra") and fields["extra"] != "-- brak --":
        value = str(row.get(fields["extra"], ""))
        if value and value != "nan":
            img = draw_text_on_image(img, value, styles["extra"], font_file)
    return img


def image_to_pdf_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    w, h = img.size
    c = canvas.Canvas(buffer, pagesize=(w, h))
    c.drawImage(ImageReader(img), 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    return buffer.getvalue()


def make_zip(template, df, fields, styles, font_file) -> bytes:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in df.iterrows():
            cert = compose_certificate(template, row, fields, styles, font_file)
            pdf_bytes = image_to_pdf_bytes(cert)
            first = str(row.get(fields.get("first"), "")) if fields.get("first") != "-- brak --" else ""
            last = str(row.get(fields.get("last"), "")) if fields.get("last") != "-- brak --" else ""
            npwz = str(row.get(fields.get("npwz"), "")) if fields.get("npwz") != "-- brak --" else ""
            filename = safe_name(f"{last}_{first}_{npwz}".replace(".0", "")) + ".pdf"
            zf.writestr(filename, pdf_bytes)
    return zip_buf.getvalue()



st.title("Generator certyfikatow PDF")
st.caption("Wgraj grafike certyfikatu, Excel i opcjonalnie wlasna czcionke. Po lewej ustawiasz pola, po prawej od razu widzisz podglad.")

st.markdown("### 1. Pliki")
file_col1, file_col2, file_col3 = st.columns(3)
with file_col1:
    template_file = st.file_uploader("Grafika certyfikatu / szablon", type=["png", "jpg", "jpeg", "pdf"])
with file_col2:
    excel_file = st.file_uploader("Lista uczestnikow Excel", type=["xlsx"])
with file_col3:
    font_file = st.file_uploader("Wlasna czcionka TTF/OTF", type=["ttf", "otf"])

df = None
fields = {}
columns = ["-- brak --"]
if excel_file:
    df = pd.read_excel(excel_file, dtype=str).fillna("")
    columns = ["-- brak --"] + list(df.columns)

template_img = None
if template_file:
    template_img = load_template(template_file)

control_col, preview_col = st.columns([0.82, 1.18], gap="large")

with control_col:
    st.markdown("### 2. Dane i ustawienia")

    if df is not None:
        st.success(f"Wczytano {len(df)} wierszy")
        with st.expander("Podglad danych z Excela", expanded=False):
            st.dataframe(df.head(10), use_container_width=True)

        fields["first"] = st.selectbox("Kolumna: imie", columns, index=1 if len(columns) > 1 else 0)
        fields["last"] = st.selectbox("Kolumna: nazwisko", columns, index=2 if len(columns) > 2 else 0)
        fields["npwz"] = st.selectbox("Kolumna: NPWZ", columns, index=3 if len(columns) > 3 else 0)
        fields["extra"] = st.selectbox("Dodatkowe pole na certyfikacie", columns, index=0)
    else:
        st.info("Wgraj Excel, aby wybrac kolumny i wygenerowac certyfikaty.")
        fields = {"first": "-- brak --", "last": "-- brak --", "npwz": "-- brak --", "extra": "-- brak --"}

    st.markdown("### 3. Pozycja tekstu")
    align_options = ["Lewo", "Srodek", "Prawo"]

    with st.expander("Imie i nazwisko", expanded=True):
        name_style = TextStyle(
            x_pct=st.slider("X imie i nazwisko (%)", 0.0, 100.0, 50.0, 0.1),
            y_pct=st.slider("Y imie i nazwisko (%)", 0.0, 100.0, 48.0, 0.1),
            size=st.slider("Rozmiar imienia i nazwiska", 8, 120, 48),
            color=st.color_picker("Kolor imienia i nazwiska", "#000000"),
            align=st.selectbox("Wyrownanie imienia i nazwiska", align_options, index=1),
        )
    with st.expander("NPWZ", expanded=True):
        npwz_style = TextStyle(
            x_pct=st.slider("X NPWZ (%)", 0.0, 100.0, 50.0, 0.1),
            y_pct=st.slider("Y NPWZ (%)", 0.0, 100.0, 58.0, 0.1),
            size=st.slider("Rozmiar NPWZ", 8, 80, 26),
            color=st.color_picker("Kolor NPWZ", "#000000"),
            align=st.selectbox("Wyrownanie NPWZ", align_options, index=1),
            prefix=st.text_input("Prefix NPWZ", "NPWZ: "),
        )
    with st.expander("Dodatkowe pole", expanded=False):
        extra_style = TextStyle(
            x_pct=st.slider("X dodatkowe (%)", 0.0, 100.0, 50.0, 0.1),
            y_pct=st.slider("Y dodatkowe (%)", 0.0, 100.0, 66.0, 0.1),
            size=st.slider("Rozmiar dodatkowego pola", 8, 80, 24),
            color=st.color_picker("Kolor dodatkowego pola", "#000000"),
            align=st.selectbox("Wyrownanie dodatkowego pola", align_options, index=1),
            prefix=st.text_input("Prefix dodatkowego pola", ""),
        )

styles = {"name": name_style, "npwz": npwz_style, "extra": extra_style}

with preview_col:
    st.markdown("### 4. Podglad na zywo")
    if template_img is not None:
        st.caption(f"Rozmiar szablonu: {template_img.width} x {template_img.height} px")
        if df is not None and len(df) > 0:
            preview_index = st.slider("Wiersz do podgladu", 0, len(df) - 1, 0)
            preview = compose_certificate(template_img, df.iloc[preview_index], fields, styles, font_file)
            st.image(preview, caption="Podglad certyfikatu", use_container_width=True)

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                pdf_preview = image_to_pdf_bytes(preview)
                st.download_button("Pobierz PDF z podgladu", pdf_preview, file_name="podglad_certyfikatu.pdf", mime="application/pdf", use_container_width=True)
            with action_col2:
                if st.button("Generuj ZIP dla calej listy", type="primary", use_container_width=True):
                    zip_bytes = make_zip(template_img, df, fields, styles, font_file)
                    st.session_state["zip_bytes"] = zip_bytes
            if "zip_bytes" in st.session_state:
                st.download_button("Pobierz ZIP z certyfikatami", st.session_state["zip_bytes"], file_name="certyfikaty_pdf.zip", mime="application/zip", use_container_width=True)
        else:
            st.info("Wgraj Excel, aby zobaczyc podglad z danymi uczestnika.")
            st.image(template_img, caption="Wgrany szablon", use_container_width=True)
    else:
        st.info("Najpierw wgraj grafike certyfikatu. Po wgraniu podglad bedzie widoczny tutaj od razu.")
