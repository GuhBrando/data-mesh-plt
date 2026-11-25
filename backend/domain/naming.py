import re
import unicodedata


def slugify(text: str) -> str:
    """Lowercase ASCII words joined by hyphens: 'Exposição de Crédito' becomes
    'exposicao-de-credito'. Empty when the text has no letter or digit."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
