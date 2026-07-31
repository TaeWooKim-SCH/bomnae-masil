from __future__ import annotations

"""Generate print-ready QR stands for the fixed R3-10 demo merchants."""

import csv
import io
from pathlib import Path

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "pipeline" / "seeds" / "demo_merchants.csv"
OUTPUT = ROOT / "output" / "pdf" / "demo_verify_stands.pdf"
BASE_URL = "https://bomnae-masil.vercel.app"


def generate() -> Path:
    import psycopg2
    from .load_source_data import database_url
    with SEED.open(encoding="utf-8-sig", newline="") as stream:
        seeds = list(csv.DictReader(stream))
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT merchant_id, name, address, verify_code FROM merchants WHERE merchant_id = ANY(%s)", ([row["merchant_id"] for row in seeds],))
            shops = {row[0]: row[1:] for row in cursor.fetchall()}
    if len(shops) != 5 or any(shops[row["merchant_id"]][2] != row["verify_code"] for row in seeds):
        raise RuntimeError("DB verification-code seed does not match the five demo merchants")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # 한글 폰트 탐색 — Windows(맑은고딕)·macOS(나눔고딕/애플고딕) 어느 쪽에서 실행해도 동작
    font = "KoreanStand"
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        str(Path.home() / "Library/Fonts/NanumGothic-Bold.ttf"),
        str(Path.home() / "Library/Fonts/NanumGothic-Regular.ttf"),
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]
    font_path = next((c for c in candidates if Path(c).exists()), None)
    if font_path is None:
        raise SystemExit("한글 TTF 폰트를 찾지 못했습니다 — candidates 목록에 경로를 추가하세요")
    pdfmetrics.registerFont(TTFont(font, font_path))
    document = canvas.Canvas(str(OUTPUT), pagesize=A4)
    width, height = A4
    for row in seeds:
        name, address, code = shops[row["merchant_id"]]
        url = f"{BASE_URL}/verify?m={row['merchant_id']}&c={code}"
        image = qrcode.make(url)
        buffer = io.BytesIO(); image.save(buffer, format="PNG"); buffer.seek(0)
        document.setFont(font, 28); document.drawCentredString(width / 2, height - 110, "봄내마실 퀘스트 인증")
        document.setFont(font, 22); document.drawCentredString(width / 2, height - 160, name)
        document.setFont(font, 12); document.drawCentredString(width / 2, height - 185, address)
        document.drawImage(ImageReader(buffer), width / 2 - 125, height / 2 - 95, 250, 250)
        document.setFont(font, 16); document.drawCentredString(width / 2, height / 2 - 130, "QR을 찍고 인증 코드를 입력해 주세요")
        document.setFont(font, 34); document.drawCentredString(width / 2, height / 2 - 180, code)
        document.setFont(font, 9); document.drawCentredString(width / 2, 70, url)
        document.showPage()
    document.save()
    return OUTPUT


if __name__ == "__main__":
    print(generate())
