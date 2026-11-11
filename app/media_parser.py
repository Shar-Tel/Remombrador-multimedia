"""
Módulo para analizar y limpiar nombres de archivos multimedia (series y películas).
"""

import os
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# Extensiones de video soportadas
MEDIA_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", 
    ".webm", ".m4v", ".ts", ".m2ts", ".vob", ".mpg", ".mpeg"
}

# Extensiones de subtítulos
SUBTITLE_EXTENSIONS = {".srt", ".sub", ".ass", ".vtt"}

# Etiquetas técnicas que nunca forman parte de un título: resolución, códec,
# fuente, audio y grupos de release. Se pueden eliminar en cualquier posición.
STRONG_TAGS = [
    r"2160p", r"1080p", r"1080i", r"720p", r"576p", r"480p", r"4k", r"uhd",
    r"blu[-\s.]?ray", r"bd[-\s.]?rip", r"br[-\s.]?rip", r"dvd[-\s.]?rip",
    r"dvd[-\s.]?scr", r"dvd", r"web[-\s.]?dl", r"web[-\s.]?rip", r"webdl",
    r"hdtv", r"hd[-\s.]?rip", r"tv[-\s.]?rip", r"vhs[-\s.]?rip",
    r"x264", r"x265", r"h[.\s_-]?264", r"h[.\s_-]?265", r"hevc", r"avc",
    r"xvid", r"divx", r"10bit", r"8bit",
    r"hdr10\+", r"hdr10", r"hdr", r"sdr", r"dolby[.\s_-]?vision", r"dovi",
    r"dts[-\s.]?hd(?:[-\s.]?ma)?", r"dts", r"truehd", r"atmos", r"eac3", r"ac3",
    r"ddp\d*", r"dd\+", r"aac(?:[.\s_-]?\d(?:[.\s_-]?\d)?)?", r"mp3", r"flac",
    r"remux", r"proper", r"repack", r"rerip",
    r"yts(?:\.[a-z]{2,4})?", r"rarbg", r"eztv", r"galaxytv", r"tgx", r"ettv",
    r"psa", r"sparks", r"geckos", r"flux", r"ntb", r"strife",
    r"animerg", r"subsplease", r"erai[-\s]?raws", r"horriblesubs",
]

STRONG_TAG_REGEX = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(STRONG_TAGS) + r")(?![A-Za-z0-9])",
    re.IGNORECASE
)

# Palabras que pueden ser una etiqueta técnica (idioma, edición, audio) pero
# también parte legítima de un título ("The French Dispatch", "Dual", "[REC]").
# Solo se eliminan cuando aparecen al final del título o entre paréntesis.
AMBIGUOUS_TAGS = [
    r"latino", r"castellano", r"espa[nñ]ol", r"spanish", r"english", r"ingl[eé]s",
    r"french", r"franc[eé]s", r"italian", r"italiano", r"german", r"alem[aá]n",
    r"portuguese", r"portugu[eé]s", r"japanese", r"japon[eé]s", r"korean",
    r"coreano", r"russian", r"ruso", r"catal[aá]n", r"catalan", r"euskera",
    r"vasco", r"gallego", r"hindi",
    r"subtitulad[oa]s?", r"vosext", r"vose", r"vso", r"dual", r"multi", r"vo",
    r"subs?", r"rip", r"extended", r"unrated", r"remastered", r"imax", r"theatrical",
    r"uncut", r"criterion", r"director'?s?\s+cut",
    r"lat", r"cast", r"ita", r"fra", r"fre", r"eng", r"esp", r"ger", r"deu",
    r"por", r"jap", r"kor", r"rus", r"cat", r"eus", r"gal",
]

AMBIGUOUS_TAG_GROUP = r"(?:" + "|".join(AMBIGUOUS_TAGS) + r")"

# Contenido completo entre corchetes formado solo por etiquetas ambiguas.
AMBIGUOUS_CONTENT_REGEX = re.compile(
    r"(?i)" + AMBIGUOUS_TAG_GROUP
    + r"(?:[\s._\-]+" + AMBIGUOUS_TAG_GROUP + r")*"
)

# Contenido completo entre corchetes formado solo por etiquetas fuertes
# (p. ej. "[1080p BluRay x264]").
STRONG_CONTENT_REGEX = re.compile(
    r"(?i)(?:" + "|".join(STRONG_TAGS) + r")"
    r"(?:[\s._\-]+(?:" + "|".join(STRONG_TAGS) + r"))*"
)

# Etiquetas ambiguas al final de un título ya normalizado.
TRAILING_AMBIGUOUS_REGEX = re.compile(
    r"(?i)[\s._\-]+" + AMBIGUOUS_TAG_GROUP + r"[\s._\-]*$"
)

# Patrones para temporadas y episodios
SERIES_PATTERNS = [
    # S01E02 / S1E2 / s01e02-e03 / S01E02-03
    re.compile(r"(?i)\b[sS](\d{1,2})[eE](\d{1,3})(?:[-_ ]?[eE]?(\d{1,3}))?\b"),
    # 1x02 / 01x02 / 1x02-03
    re.compile(r"(?i)\b(\d{1,2})x(\d{1,3})(?:[-_ ]?(\d{1,3}))?\b"),
    # Temporada 1 Capitulo 2 / Season 1 Episode 2
    re.compile(r"(?i)\b(?:season|temporada)\s*(\d{1,2})\s*(?:episode|capitulo|capítulo|episodio|ep)\s*(\d{1,3})\b"),
    # T01E02 / T1E2
    re.compile(r"(?i)\b[tT](\d{1,2})[eE](\d{1,3})\b"),
]

# Patrón para episodios sueltos (anime, miniseries) e.g., "Ep. 05" o "E05"
LOOSE_EPISODE_PATTERNS = [
    re.compile(r"(?i)\b(?:ep|episode|capitulo|capítulo|episodio)\.?\s*(\d{1,3})\b"),
    re.compile(r"(?i)\b[eE](\d{1,3})\b"),
]

# Patrón para detectar año (1920 - 2039), con o sin paréntesis/corchetes.
YEAR_PATTERN = re.compile(r"(?:\b|[\(\[])((?:19|20)\d{2})(?:\b|[\)\]])")

# Idiomas y configuraciones de audio reconocibles en el nombre del archivo.
# Se conservan en el nombre final de las películas ("... (2021) [Latino].mkv").
LANGUAGE_PATTERNS = [
    (re.compile(r"\blatino\b|\blat\b", re.IGNORECASE), "Latino"),
    (re.compile(r"\bcastellano\b|\bcast\b", re.IGNORECASE), "Castellano"),
    (re.compile(r"\bespa[nñ]ol\b|\bespanol\b|\bspanish\b|\besp\b", re.IGNORECASE), "Español"),
    (re.compile(r"\bingl[eé]s\b|\bingles\b|\benglish\b|\beng\b", re.IGNORECASE), "Inglés"),
    (re.compile(r"\bvose(?:xt)?\b|\bvso\b|\bsubtitulad[oa]s?\b|v\.?\s*o\.?\s*s\.?\s*e\.?", re.IGNORECASE), "VOSE"),
    (re.compile(r"\bvo\b|\bversi[oó]n\s+original\b|v\.?\s*o\.?(?![a-z])", re.IGNORECASE), "VO"),
    (re.compile(r"\bdual\b", re.IGNORECASE), "Dual"),
    (re.compile(r"\bmulti\b", re.IGNORECASE), "Multi"),
    (re.compile(r"\bitaliano\b|\bitalian\b|\bita\b", re.IGNORECASE), "Italiano"),
    (re.compile(r"\bfranc[eé]s\b|\bfrances\b|\bfrench\b|\bfra\b|\bvff\b", re.IGNORECASE), "Francés"),
    (re.compile(r"\balem[aá]n\b|\bgerman\b|\bger\b|\bdeu\b", re.IGNORECASE), "Alemán"),
    (re.compile(r"\bportugu[eé]s\b|\bportuguese\b|\bpor\b", re.IGNORECASE), "Portugués"),
    (re.compile(r"\bjapon[eé]s\b|\bjapanese\b|\bjap\b", re.IGNORECASE), "Japonés"),
    (re.compile(r"\bcoreano\b|\bkorean\b|\bkor\b", re.IGNORECASE), "Coreano"),
    (re.compile(r"\bcatal[aá]n\b|\bcatalan\b|\bcat\b", re.IGNORECASE), "Catalán"),
    (re.compile(r"\beuskera\b|\bvasco\b|\beus\b", re.IGNORECASE), "Euskera"),
    (re.compile(r"\bgallego\b|\bgal\b", re.IGNORECASE), "Gallego"),
    (re.compile(r"\bruso\b|\brussian\b|\brus\b", re.IGNORECASE), "Ruso"),
    (re.compile(r"\bhindi\b|\bhin\b", re.IGNORECASE), "Hindi"),
]

# Marcadores técnicos fuertes que marcan dónde termina el título de una
# película cuando el nombre no incluye el año.
STRONG_RELEASE_MARKERS = re.compile(
    r"(?i)(?:^|[\s._\-\[\]\(\)])(?:"
    + "|".join(STRONG_TAGS)
    + r")(?=$|[\s._\-\[\]\(\)])"
)

# Un idioma/edición solo marca el final del título si va entre paréntesis o
# corchetes ("(Spanish)", "[Dual Latino]"), para no romper títulos como
# "The.French.Dispatch".
BRACKETED_AMBIGUOUS_MARKERS = re.compile(
    r"(?i)[\[\(]\s*" + AMBIGUOUS_TAG_GROUP
    + r"(?:[\s._\-]+" + AMBIGUOUS_TAG_GROUP + r")*\s*[\]\)]"
)

# Un idioma/edición al final absoluto del nombre ("Movie.Latino").
TRAILING_AMBIGUOUS_MARKER = re.compile(
    r"(?i)[\s._\-]+" + AMBIGUOUS_TAG_GROUP + r"[\s._\-]*$"
)


def detect_language(text: str) -> Optional[str]:
    """
    Detecta el idioma (o configuración de audio) presente en la parte técnica
    de un nombre de archivo. Devuelve una etiqueta normalizada o None.
    """
    if not text:
        return None

    found = []
    for pattern, label in LANGUAGE_PATTERNS:
        if label not in found and pattern.search(text):
            found.append(label)

    if not found:
        return None

    # "V.O.S.E." contiene "V.O."; no hace falta mostrar ambas etiquetas.
    if "VOSE" in found and "VO" in found:
        found.remove("VO")

    # "Dual"/"Multi" son configuraciones de audio: si hay un idioma concreto,
    # se prefiere ese.
    specific = [label for label in found if label not in ("Dual", "Multi")]
    if specific:
        return " + ".join(specific)
    return found[0]


def find_release_suffix_start(name: str) -> Optional[int]:
    """
    Devuelve la posición donde empieza el sufijo técnico de un nombre, si lo hay.

    Los marcadores fuertes (1080p, x264, BluRay...) cuentan en cualquier posición.
    Las palabras ambiguas (idioma/edición) solo cuentan si van entre paréntesis o
    al final absoluto, para no cortar títulos como "The.French.Dispatch".
    """
    starts = []
    for pattern in (
        STRONG_RELEASE_MARKERS,
        BRACKETED_AMBIGUOUS_MARKERS,
        TRAILING_AMBIGUOUS_MARKER,
    ):
        match = pattern.search(name)
        if match:
            starts.append(match.start())

    return min(starts) if starts else None


@dataclass
class MediaFileInfo:
    file_path: str
    directory: str
    original_filename: str
    base_name: str
    extension: str
    media_type: str  # "series", "movie", "unknown"
    parsed_title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    end_episode: Optional[int] = None
    year: Optional[int] = None
    language: Optional[str] = None
    suggested_filename: Optional[str] = None
    status: str = "pending"  # "pending", "ready", "renamed", "skipped", "error"
    error_message: Optional[str] = None
    tvmaze_show_id: Optional[int] = None
    tvmaze_show_name: Optional[str] = None
    tvmaze_episode_name: Optional[str] = None
    tvmaze_premiered: Optional[str] = None
    tvmaze_matches: Optional[List[Dict[str, Any]]] = None


def sanitize_filename(name: str) -> str:
    """
    Limpia un nombre de archivo eliminando o reemplazando caracteres prohibidos
    en sistemas operativos Windows, Linux y macOS.
    Prohibidos en Windows: < > : " / \\ | ? *
    """
    if not name:
        return ""

    # Reemplazos amigables
    name = name.replace(":", " -")
    name = name.replace("?", "")
    name = name.replace('"', "'")
    name = name.replace("/", "-")
    name = name.replace("\\", "-")
    name = name.replace("*", "-")
    name = name.replace("<", "")
    name = name.replace(">", "")
    name = name.replace("|", "-")

    # Eliminar dobles espacios y guiones redundantes
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"-\s*-+", "-", name)
    # Normalizar guiones usados como separador, sin romper palabras compuestas
    # (ej: "Spider-Man" debe seguir siendo "Spider-Man").
    name = re.sub(r"\s+-\s*", " - ", name)
    name = re.sub(r"\s*-\s+", " - ", name)

    # Windows prohíbe que el nombre termine en punto o espacio
    name = name.strip(". ")
    return name


BRACKETED_CONTENT_REGEX = re.compile(r"[\[\(\{]([^\[\]\(\)\{\}]*)[\]\)\}]")
_DOMAIN_REGEX = re.compile(
    r"(?i)\.(?:com|net|org|info|biz|mx|es|tv|io|me|cc|to|ws|ru|uk|fr|de)\b"
)


def _is_technical_bracket_content(content: str) -> bool:
    """Indica si el contenido de un corchete es una etiqueta, no parte del título."""
    content = content.strip()
    if not content:
        return True
    if YEAR_PATTERN.fullmatch(content):
        return True
    if STRONG_TAG_REGEX.fullmatch(content) or STRONG_CONTENT_REGEX.fullmatch(content):
        return True
    if AMBIGUOUS_CONTENT_REGEX.fullmatch(content):
        return True
    if _DOMAIN_REGEX.search(content):
        return True
    return False


def _replace_bracketed(match: "re.Match[str]") -> str:
    content = match.group(1).strip()
    if _is_technical_bracket_content(content):
        return " "
    # Contenido legítimo: "[REC]" -> "REC".
    return f" {content} "


def clean_title_with_tags(text: str) -> Tuple[str, str]:
    """
    Limpia un título y devuelve (título_limpio, etiquetas_ambiguas_eliminadas).

    Las etiquetas ambiguas eliminadas se usan como respaldo para detectar el
    idioma cuando aparece antes del año ("El.Cuerpo.Latino.2012").
    """
    if not text:
        return "", ""

    # Corchetes/paréntesis: se eliminan si son técnicos; si no, se conserva su
    # contenido ("[REC]" -> "REC").
    text = BRACKETED_CONTENT_REGEX.sub(_replace_bracketed, text)

    # Quitar etiquetas técnicas fuertes antes de normalizar la puntuación para
    # que "H.264", "AAC2.0" o "HDR10+" se reconozcan como una sola etiqueta.
    text = STRONG_TAG_REGEX.sub(" ", text)

    # Reemplazar puntos y guiones bajos por espacios.
    text = text.replace(".", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Quitar etiquetas ambiguas finales, conservando las palabras del título.
    removed_tags: List[str] = []
    while True:
        match = TRAILING_AMBIGUOUS_REGEX.search(text)
        if not match:
            break
        remainder = text[:match.start()].strip(" -–—_.,;:/\\()[]{}")
        if not remainder:
            # El título es solo la etiqueta (ej. "Dual"): se conserva.
            break
        removed_tags.append(match.group(0).strip(" ._-"))
        text = remainder

    # Eliminar paréntesis, corchetes o llaves vacíos que hayan quedado tras
    # quitar etiquetas (ej: "( )", "[]", "( - )").
    text = re.sub(r"\(\s*[-–—_.,;:/\\]*\s*\)", " ", text)
    text = re.sub(r"\[\s*[-–—_.,;:/\\]*\s*\]", " ", text)
    text = re.sub(r"\{\s*[-–—_.,;:/\\]*\s*\}", " ", text)

    # Quitar separadores colgantes que hayan quedado al limpiar etiquetas.
    text = re.sub(r"(?:^|\s)[-–—_]+(?=\s|$)", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—_.,;:/\\()[]{}")
    return text, " ".join(removed_tags)


def clean_title_string(text: str) -> str:
    """Limpia una cadena de título quitando etiquetas técnicas y de release."""
    cleaned, _ = clean_title_with_tags(text)
    return cleaned


def parse_filename(file_path: str) -> Optional[MediaFileInfo]:
    """
    Analiza una ruta de archivo y extrae la información relevante:
    título, temporada, capítulo, año y tipo de medio.
    """
    directory, filename = os.path.split(file_path)
    base_name, extension = os.path.splitext(filename)
    ext_lower = extension.lower()

    if ext_lower not in MEDIA_EXTENSIONS and ext_lower not in SUBTITLE_EXTENSIONS:
        return None

    # Primero intentamos detectar si es una serie buscando SxxExx o 1x02
    season = None
    episode = None
    end_episode = None
    media_type = "unknown"
    title_raw = base_name
    series_match = None

    for pattern in SERIES_PATTERNS:
        match = pattern.search(base_name)
        if match:
            media_type = "series"
            series_match = match
            groups = match.groups()
            season = int(groups[0])
            episode = int(groups[1])
            if len(groups) > 2 and groups[2] is not None:
                try:
                    end_episode = int(groups[2])
                except (ValueError, TypeError):
                    end_episode = None

            # El título suele estar antes del patrón de temporada/episodio
            title_raw = base_name[:match.start()]
            break

    # Si no se detectó con los patrones principales de series, buscar episodios sueltos
    if media_type == "unknown":
        for pattern in LOOSE_EPISODE_PATTERNS:
            match = pattern.search(base_name)
            if match:
                ep_val = int(match.group(1))
                if ep_val < 2000 and not (1900 <= ep_val <= 2099):
                    media_type = "series"
                    series_match = match
                    season = 1
                    episode = ep_val
                    title_raw = base_name[:match.start()]
                    break

    # Si sigue siendo desconocido, comprobar si tiene año para clasificar como película.
    # Se usa el último año válido: el año de estreno suele ir al final del nombre
    # ("2001.A.Space.Odyssey.1968" -> 1968, "1917.2019" -> 2019).
    year = None
    year_start = None
    year_end = None
    for year_match in YEAR_PATTERN.finditer(base_name):
        year_candidate = int(year_match.group(1))
        if 1920 <= year_candidate <= 2035:
            year = year_candidate
            year_start = year_match.start()
            year_end = year_match.end()

    if year is not None:
        if media_type != "series":
            media_type = "movie"
            title_raw = base_name[:year_start]

    # En series, quitar un año final del título (ej: "The.Flash.2014.S01E01").
    # Si el título es solo el año, se conserva para no dejarlo vacío.
    if media_type == "series" and year is not None:
        stripped_title = re.sub(
            r"(?:^|[\s._\-\(\[])(?:19|20)\d{2}[\)\]]*[\s._\-]*$", "", title_raw
        ).strip(" ._-")
        if stripped_title:
            title_raw = stripped_title

    # Si aún no tiene tipo y no tiene temporada/episodio, asumimos película/video genérico.
    # Sin año, el título termina donde empieza el sufijo técnico
    # ("Movie.Name.1080p.BluRay" -> "Movie Name").
    suffix_start = None
    if media_type == "unknown":
        media_type = "movie"
        suffix_start = find_release_suffix_start(base_name)
        if suffix_start:
            title_raw = base_name[:suffix_start]

    # Parte técnica del nombre (calidad, códec, grupo, idioma...). Se usa para
    # detectar el idioma sin confundirlo con palabras del título.
    if media_type == "series" and series_match is not None:
        technical_tail = base_name[series_match.end():]
    elif year_end is not None:
        technical_tail = base_name[year_end:]
    elif suffix_start:
        technical_tail = base_name[suffix_start:]
    else:
        technical_tail = ""

    # Limpiar el título extraído. Las etiquetas ambiguas que se quitan del
    # título (p. ej. "Latino" antes del año) sirven como respaldo para el idioma.
    clean_title, trailing_tags = clean_title_with_tags(title_raw)
    language = detect_language(technical_tail) or detect_language(trailing_tags)

    # Si el título quedó vacío, usar nombre del directorio padre
    if not clean_title and directory:
        parent_dir_name = os.path.basename(directory)
        clean_title = clean_title_string(parent_dir_name)

    # Extraer año del título si aún no teníamos uno
    if not year and clean_title:
        parenthesis_year = re.search(r"\((19\d{2}|20\d{2})\)", clean_title)
        if parenthesis_year:
            year = int(parenthesis_year.group(1))
            clean_title = clean_title[:parenthesis_year.start()].strip()

    clean_title = clean_title.strip()

    return MediaFileInfo(
        file_path=os.path.abspath(file_path),
        directory=os.path.abspath(directory),
        original_filename=filename,
        base_name=base_name,
        extension=extension,
        media_type=media_type,
        parsed_title=clean_title,
        season=season,
        episode=episode,
        end_episode=end_episode,
        year=year,
        language=language,
    )


def build_suggested_filename(
    info: MediaFileInfo,
    show_name: Optional[str] = None,
    episode_title: Optional[str] = None,
    format_pattern: str = "{show} - S{season:02d}E{episode:02d} - {title}{ext}"
) -> str:
    """
    Construye el nombre sugerido para el archivo aplicando la información
    obtenida de la API o del análisis local.
    """
    ext = info.extension

    if info.media_type == "series" and info.season is not None and info.episode is not None:
        final_show = show_name or info.parsed_title or "Serie"
        final_ep_title = episode_title or f"Episodio {info.episode}"

        if info.end_episode and info.end_episode != info.episode:
            # Mantener el formato elegido por el usuario también en episodios dobles.
            episode_token = f"{info.episode:02d}-E{info.end_episode:02d}"
            pattern = (format_pattern or "").replace(
                "{episode:02d}", episode_token
            ).replace("{episode}", episode_token)
            try:
                name = pattern.format(
                    show=final_show,
                    season=info.season,
                    episode=episode_token,
                    title=final_ep_title,
                    ext=ext
                )
            except Exception:
                name = (
                    f"{final_show} - S{info.season:02d}E{info.episode:02d}"
                    f"-E{info.end_episode:02d} - {final_ep_title}{ext}"
                )
        else:
            try:
                name = format_pattern.format(
                    show=final_show,
                    season=info.season,
                    episode=info.episode,
                    title=final_ep_title,
                    ext=ext
                )
            except Exception:
                name = f"{final_show} - S{info.season:02d}E{info.episode:02d} - {final_ep_title}{ext}"
    else:
        final_title = (
            show_name
            or info.parsed_title
            or clean_title_string(info.base_name)
            or info.base_name
        )
        if info.year:
            final_title = f"{final_title} ({info.year})"
        if info.language:
            final_title = f"{final_title} [{info.language}]"
        name = f"{final_title}{ext}"

    sanitized_base = sanitize_filename(os.path.splitext(name)[0])
    return f"{sanitized_base}{ext}"


# Sufijos admitidos en subtítulos asociados: idiomas y marcas habituales.
# Se rechazan sufijos arbitrarios para no asociar "Movie.2.es.srt" a "Movie.mkv".
SUBTITLE_SUFFIX_TAGS = {
    "es", "spa", "esp", "spanish", "latino", "lat", "castellano", "cast",
    "en", "eng", "english", "ingles", "inglés",
    "fr", "fre", "fra", "french", "francais", "français", "vff", "vf",
    "de", "ger", "deu", "german", "aleman", "alemán",
    "it", "ita", "italian", "italiano",
    "pt", "por", "portuguese", "portugues", "portugués",
    "ja", "jp", "jpn", "japanese", "japones", "japonés",
    "ko", "kor", "korean", "coreano",
    "ru", "rus", "russian", "ruso",
    "ca", "cat", "catalan", "catalán",
    "eu", "eus", "euskera", "vasco",
    "gl", "glg", "gal", "gallego",
    "hi", "hin", "hindi",
    "ar", "ara", "arabic", "arabe", "árabe",
    "zh", "chi", "zho", "chs", "cht", "chinese", "chino",
    "nl", "dut", "nld", "dutch", "holandes", "holandés",
    "sv", "swe", "swedish", "sueco",
    "no", "nor", "norwegian", "noruego",
    "da", "dan", "danish", "danes",
    "fi", "fin", "finnish", "finlandes", "finlandés",
    "pl", "pol", "polish", "polaco",
    "tr", "tur", "turkish", "turco",
    "forced", "sdh", "cc", "default", "sub", "subs", "full", "foreign",
    "commentary", "dub", "dubbed", "hc", "hardsub", "softsub", "normal",
    "srt", "vtt", "ass",
}


def _is_subtitle_suffix(suffix: str) -> bool:
    """Comprueba que un sufijo tipo '.es.forced' esté formado por etiquetas conocidas."""
    parts = [p for p in re.split(r"[.\-_ ]+", suffix.strip("._- ")) if p]
    return bool(parts) and all(part.lower() in SUBTITLE_SUFFIX_TAGS for part in parts)


def find_associated_subtitles(video_path: str) -> List[Tuple[str, str]]:
    """
    Busca subtítulos asociados a un archivo de video en el mismo directorio.
    Devuelve pares (ruta_subtitulo_actual, extension_con_idioma), por ejemplo:
    (".../video.es.srt", ".es.srt")
    """
    directory, video_filename = os.path.split(video_path)
    video_base, _ = os.path.splitext(video_filename)
    video_base_lower = video_base.lower()
    results = []

    if not os.path.exists(directory):
        return results

    try:
        for fname in os.listdir(directory):
            full_sub_path = os.path.join(directory, fname)
            if not os.path.isfile(full_sub_path):
                continue

            # Comprobar si termina en una extensión de subtítulo
            for sub_ext in SUBTITLE_EXTENSIONS:
                if not fname.lower().endswith(sub_ext):
                    continue

                # Comprobar si el nombre base coincide con el del video
                sub_prefix = fname[:-len(sub_ext)]
                if sub_prefix.lower() == video_base_lower:
                    results.append((full_sub_path, sub_ext))
                elif sub_prefix.lower().startswith(video_base_lower + "."):
                    # Caso con sufijo de idioma, ej: video.es.srt o video.es.forced.srt
                    lang_tag = sub_prefix[len(video_base):]  # ".es"
                    if _is_subtitle_suffix(lang_tag):
                        results.append((full_sub_path, f"{lang_tag}{sub_ext}"))
                break
    except Exception:
        pass

    return results
