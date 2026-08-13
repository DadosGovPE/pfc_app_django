from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader


SEPLAG_LOGO_FILENAME = "LOGO SEPLAG GOV COR cópia@2x (1).png"


def _cropped_transparent_image(path):
    """Return an ImageReader without the transparent padding around a PNG."""
    with Image.open(path) as image:
        image = image.convert("RGBA")
        alpha_bounds = image.getchannel("A").getbbox()
        if alpha_bounds:
            image = image.crop(alpha_bounds)

        image_buffer = BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        return ImageReader(image_buffer)


def current_seplag_logo(media_root):
    """Return the current Seplag logo used in generated PDFs."""
    return _cropped_transparent_image(Path(media_root) / SEPLAG_LOGO_FILENAME)


def draw_certificate_visuals(pdf_canvas, media_root, page_width, page_height):
    """Draw the certificate background, signature and current institutional logos."""
    media_root = Path(media_root)

    pdf_canvas.drawImage(
        str(media_root / "Certificado-FUNDO.png"),
        230,
        0,
        width=page_width,
        height=page_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf_canvas.drawImage(
        str(media_root / "upload" / "certificado" / "assinatura.jpg"),
        130,
        100,
        width=196,
        height=50,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf_canvas.drawImage(
        str(media_root / "igpe.png"),
        50,
        20,
        width=63,
        height=50,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf_canvas.drawImage(
        current_seplag_logo(media_root),
        page_width - 255,
        15,
        width=240,
        height=65,
        preserveAspectRatio=True,
        mask="auto",
    )
