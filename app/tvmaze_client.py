"""
Cliente para la API de TVmaze con soporte de caché y emparejamiento inteligente.
"""

import difflib
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from app.media_parser import MediaFileInfo, build_suggested_filename

logger = logging.getLogger(__name__)

USER_AGENT = "RenombradorMultimedia/1.0 (+https://github.com/media-renamer)"
TIMEOUT_SECONDS = 8

DEFAULT_FORMAT = "{show} - S{season:02d}E{episode:02d} - {title}{ext}"

# Similitud mínima para aceptar automáticamente un show de TVmaze.
MIN_MATCH_SCORE = 0.7
# Similitud exigida a las películas: TVmaze es una base de datos de series, por lo
# que solo se acepta una coincidencia prácticamente exacta.
MIN_MOVIE_MATCH_SCORE = 0.95
# Número máximo de candidatos que se contrastan con sus nombres alternativos (akas).
MAX_AKA_CANDIDATES = 4

# Penalizaciones para coincidencias obtenidas con variantes del título o con
# nombres alternativos, de forma que siempre se prefiera el nombre original.
VARIANT_WEIGHT = 0.95
AKA_WEIGHT = 0.95


class TVmazeClient:
    """
    Cliente para interactuar con la API pública de TVmaze (https://www.tvmaze.com/api).
    No requiere API Key.
    """

    def __init__(self):
        # Caché de búsquedas: query -> lista de shows
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}
        # Caché de episodios por show_id: show_id -> dict con {(season, number): episode_name}
        self._episodes_cache: Dict[int, Dict[Tuple[int, int], str]] = {}
        # Caché de detalles de show: show_id -> show_dict
        self._shows_cache: Dict[int, Dict[str, Any]] = {}
        # Caché de nombres alternativos (akas): show_id -> lista de nombres
        self._akas_cache: Dict[int, List[str]] = {}
        # Último error de red registrado (para distinguirlo de "no encontrada")
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # HTTP / caché
    # ------------------------------------------------------------------
    def _http_get_json(self, url: str) -> Any:
        """Realiza una petición HTTP GET y devuelve el JSON deserializado."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            content = response.read().decode(charset)
            return json.loads(content)

    def search_shows(self, query: str) -> List[Dict[str, Any]]:
        """
        Busca series por nombre en TVmaze.
        Devuelve una lista de diccionarios de show con id, name, premiered, etc.
        """
        query_clean = query.strip().lower()
        if not query_clean:
            return []

        if query_clean in self._search_cache:
            return self._search_cache[query_clean]

        encoded_query = urllib.parse.quote(query.strip())
        url = f"https://api.tvmaze.com/search/shows?q={encoded_query}"

        try:
            data = self._http_get_json(url)
            shows = []
            for item in data:
                show = item.get("show")
                if show:
                    # La puntuación de relevancia de TVmaze se conserva como
                    # criterio de desempate (clave privada, no se muestra en la UI).
                    show["_search_score"] = float(item.get("score") or 0.0)
                    shows.append(show)
                    self._shows_cache[show["id"]] = show
            self._search_cache[query_clean] = shows
            self.last_error = None
            return shows
        except Exception as e:
            logger.warning(f"Error al buscar en TVmaze para '{query}': {e}")
            self.last_error = str(e)
            return []

    def get_show_episodes(self, show_id: int) -> Dict[Tuple[int, int], str]:
        """
        Obtiene la lista completa de episodios de una serie y los indexa en memoria
        por (temporada, número de episodio).
        """
        if show_id in self._episodes_cache:
            return self._episodes_cache[show_id]

        url = f"https://api.tvmaze.com/shows/{show_id}/episodes?specials=1"
        episodes_map: Dict[Tuple[int, int], str] = {}

        try:
            episodes = self._http_get_json(url)
            for ep in episodes:
                season = ep.get("season")
                number = ep.get("number")
                name = ep.get("name")
                if season is not None and number is not None and name:
                    episodes_map[(int(season), int(number))] = name.strip()

            self._episodes_cache[show_id] = episodes_map
            return episodes_map
        except Exception as e:
            logger.warning(f"Error al obtener episodios para show {show_id}: {e}")
            return {}

    def _get_aka_names(self, show_id: int) -> List[str]:
        """Obtiene los nombres alternativos (akas) de una serie, con caché."""
        if show_id in self._akas_cache:
            return self._akas_cache[show_id]

        names: List[str] = []
        try:
            data = self._http_get_json(f"https://api.tvmaze.com/shows/{show_id}/akas")
            for item in data:
                name = (item.get("name") or "").strip()
                if name:
                    names.append(name)
        except Exception as e:
            logger.debug(f"No se pudieron obtener akas de {show_id}: {e}")

        self._akas_cache[show_id] = names
        return names

    # ------------------------------------------------------------------
    # Comparación de títulos
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_name(text: str) -> str:
        """Normaliza un título para poder compararlo de forma tolerante."""
        text = (text or "").lower()
        text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
        text = text.replace("&", " and ")
        # Conservar letras y números de cualquier alfabeto (cirílico, CJK, etc.)
        text = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _name_similarity(cls, a: str, b: str) -> float:
        """Devuelve una similitud entre 0 y 1 entre dos títulos."""
        na, nb = cls._normalize_name(a), cls._normalize_name(b)
        if not na or not nb:
            return 0.0
        if na == nb:
            return 1.0

        ratio = difflib.SequenceMatcher(None, na, nb).ratio()

        # Si el título corto (de dos o más palabras) aparece completo dentro del
        # otro, se considera una coincidencia razonable. Se exige más de una
        # palabra para evitar que "Show" coincida con "Regular Show".
        short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
        if len(short.split()) >= 2 and short in long:
            ratio = max(ratio, 0.8)

        return ratio

    @classmethod
    def _query_variants(cls, title: str) -> List[str]:
        """
        Genera variantes de búsqueda para un título. TVmaze no encuentra nada si
        se incluye el año al final (ej. "The Flash 2014"), así que se prueban
        variantes sin año y sin artículos iniciales.
        """
        variants: List[str] = []

        def add(value: str):
            value = re.sub(r"\s+", " ", value or "").strip(" .-_")
            if value and value.lower() not in {v.lower() for v in variants}:
                variants.append(value)

        add(title)

        base = (title or "").strip()
        # "The Flash 2014", "The Flash (2014)", "The.Flash.2014"
        no_year = re.sub(
            r"(?:^|[\s._\-\(\[])(?:19|20)\d{2}[\)\]]*[\s._\-]*$", "", base
        ).strip(" .-_")
        add(no_year)

        # Artículos iniciales: "Los Simpsons" -> "Simpsons", "The Office" -> "Office"
        for current in list(variants):
            no_article = re.sub(
                r"^(?:the|el|la|los|las)\s+", "", current, flags=re.IGNORECASE
            ).strip()
            add(no_article)

        return variants

    def _best_aka_score(
        self, title: str, variants: List[str], show: Dict[str, Any]
    ) -> float:
        """Compara el título con los nombres alternativos (akas) de una serie."""
        show_id = show.get("id")
        if show_id is None:
            return 0.0

        aka_names = self._get_aka_names(int(show_id))
        if not aka_names:
            return 0.0

        best = 0.0
        for candidate in [title] + variants[1:]:
            for aka in aka_names:
                best = max(best, self._name_similarity(candidate, aka))
        return best

    def _is_confident_show_match(self, title: str, show: Dict[str, Any]) -> bool:
        """Comprueba si un show coincide de forma prácticamente exacta con el título."""
        variants = self._query_variants(title)
        name = show.get("name", "")

        if self._name_similarity(title, name) >= MIN_MOVIE_MATCH_SCORE:
            return True
        if any(
            self._name_similarity(variant, name) * VARIANT_WEIGHT >= MIN_MOVIE_MATCH_SCORE
            for variant in variants[1:]
        ):
            return True
        return (
            self._best_aka_score(title, variants, show) * AKA_WEIGHT
            >= MIN_MOVIE_MATCH_SCORE
        )

    # ------------------------------------------------------------------
    # Emparejamiento
    # ------------------------------------------------------------------
    def find_best_show_match(
        self, title: str, year: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Busca y selecciona el show que mejor coincida con el título y año opcional.
        Devuelve None si no hay una coincidencia suficientemente fiable.
        """
        if not title or not title.strip():
            return None

        variants = self._query_variants(title)

        # Reunir candidatos de todas las variantes (sin duplicados).
        candidates: Dict[int, Dict[str, Any]] = {}
        for query in variants:
            for show in self.search_shows(query):
                show_id = show.get("id")
                if show_id is None:
                    continue
                previous = candidates.get(show_id)
                if (
                    previous is None
                    or show.get("_search_score", 0.0)
                    > previous.get("_search_score", 0.0)
                ):
                    candidates[show_id] = show

        if not candidates:
            return None

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for show in candidates.values():
            name = show.get("name", "")

            # Se compara tanto el título original como sus variantes.
            score = self._name_similarity(title, name)
            for variant in variants[1:]:
                score = max(
                    score, self._name_similarity(variant, name) * VARIANT_WEIGHT
                )

            # El año ayuda a desambiguar remakes ("Doctor Who" 1963 / 2005 / 2023),
            # pero solo si el nombre ya se parece lo suficiente.
            if year and score >= 0.5:
                premiered = str(show.get("premiered") or "")
                if premiered.startswith(str(year)):
                    score += 0.05
                elif premiered[:4].isdigit() and abs(int(premiered[:4]) - int(year)) <= 1:
                    score += 0.02

            # La relevancia de TVmaze solo desempata.
            score += min(float(show.get("_search_score", 0.0)) / 100.0, 0.05)
            scored.append((score, show))

        scored.sort(key=lambda item: item[0], reverse=True)

        # Si ningún nombre coincide con claridad, probar los nombres alternativos
        # (por ejemplo, "Money Heist" es un aka de "La Casa de Papel").
        if len(self._normalize_name(title).split()) >= 2:
            for index, (score, show) in enumerate(list(scored[:MAX_AKA_CANDIDATES])):
                if score >= 0.95:
                    continue
                aka_score = self._best_aka_score(title, variants, show) * AKA_WEIGHT
                if aka_score > score:
                    scored[index] = (aka_score, show)

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_show = scored[0]

        # Los títulos de una sola palabra son muy propensos a falsos positivos
        # ("Show" -> "Mr. Show"), así que se exige más precisión.
        min_score = MIN_MATCH_SCORE
        if len(self._normalize_name(title).split()) < 2:
            min_score = 0.85

        if best_score >= min_score:
            return best_show

        logger.info(
            "Sin coincidencia fiable en TVmaze para %r (mejor candidato: %r, %.2f)",
            title,
            best_show.get("name"),
            best_score,
        )
        return None

    # ------------------------------------------------------------------
    # Generación del nombre sugerido
    # ------------------------------------------------------------------
    def apply_show_to_info(
        self,
        info: MediaFileInfo,
        show: Dict[str, Any],
        format_pattern: str = DEFAULT_FORMAT,
    ) -> MediaFileInfo:
        """
        Aplica un show de TVmaze a la información del archivo y regenera el
        nombre sugerido (incluye episodios dobles).
        """
        info.tvmaze_show_id = show.get("id")
        info.tvmaze_show_name = show.get("name")
        info.tvmaze_premiered = show.get("premiered")
        info.tvmaze_episode_name = None
        info.error_message = None

        if info.media_type == "series" and info.season is not None and info.episode is not None:
            show_id = show.get("id")
            episodes = self.get_show_episodes(int(show_id)) if show_id is not None else {}
            ep_title = episodes.get((info.season, info.episode))

            # Si es un episodio doble, intentar obtener el título del segundo.
            if info.end_episode and info.end_episode != info.episode:
                second_title = episodes.get((info.season, info.end_episode))
                if ep_title and second_title and ep_title != second_title:
                    ep_title = f"{ep_title} & {second_title}"

            info.tvmaze_episode_name = ep_title

            if not ep_title:
                info.error_message = (
                    "Episodio no encontrado en TVmaze "
                    f"(temporada {info.season}, episodio {info.episode})"
                )

        info.suggested_filename = build_suggested_filename(
            info,
            show_name=info.tvmaze_show_name,
            episode_title=info.tvmaze_episode_name,
            format_pattern=format_pattern or DEFAULT_FORMAT,
        )
        info.status = "ready"
        return info

    def process_file_info(
        self,
        info: MediaFileInfo,
        format_pattern: str = DEFAULT_FORMAT,
    ) -> MediaFileInfo:
        """
        Consulta la API de TVmaze con la información del archivo y genera
        el nombre sugerido.
        """
        self.last_error = None

        try:
            show = self.find_best_show_match(info.parsed_title, info.year)

            # Para películas se exige una coincidencia prácticamente exacta:
            # TVmaze es una base de datos de series y no queremos renombrar una
            # película con el nombre de una serie parecida.
            if (
                show
                and info.media_type != "series"
                and not self._is_confident_show_match(info.parsed_title, show)
            ):
                show = None

            if show:
                info.tvmaze_matches = self.search_shows(info.parsed_title)
                self.apply_show_to_info(info, show, format_pattern)

                # Para películas/TV movies sin año en el nombre, tomarlo del estreno.
                if info.media_type != "series" and not info.year and show.get("premiered"):
                    try:
                        info.year = int(str(show["premiered"])[:4])
                        info.suggested_filename = build_suggested_filename(
                            info,
                            show_name=info.tvmaze_show_name,
                            format_pattern=format_pattern or DEFAULT_FORMAT,
                        )
                    except (TypeError, ValueError):
                        pass
            else:
                # No encontrada (o sin coincidencia fiable): nombre limpio local.
                info.suggested_filename = build_suggested_filename(
                    info, format_pattern=format_pattern or DEFAULT_FORMAT
                )
                info.status = "ready"
                if self.last_error:
                    info.error_message = (
                        "No se pudo conectar con TVmaze: "
                        f"{self.last_error} (nombre sugerido localmente)"
                    )
                else:
                    info.error_message = (
                        "No encontrada en TVmaze (nombre sugerido localmente)"
                    )

        except Exception as e:
            info.status = "error"
            info.error_message = f"Error al procesar: {e}"
            info.suggested_filename = build_suggested_filename(
                info, format_pattern=format_pattern or DEFAULT_FORMAT
            )

        return info
