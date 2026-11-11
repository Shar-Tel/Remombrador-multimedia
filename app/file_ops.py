"""
Operaciones de renombrado seguras y transaccionales.

El renombrado se hace en dos fases usando nombres temporales, de modo que
funcionan los intercambios de nombre (A -> B y B -> A) y los ciclos. Si algo
falla a mitad, se intenta restaurar el estado original para no dejar el video
y sus subtítulos con nombres incoherentes.
"""

import os
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


class RenameError(Exception):
    """Error base de las operaciones de renombrado."""


class DuplicateDestinationError(RenameError):
    """Dos archivos del mismo lote terminarían con el mismo nombre."""

    def __init__(self, destinations: Sequence[str]):
        self.destinations = list(destinations)
        names = ", ".join(sorted({os.path.basename(p) for p in self.destinations}))
        super().__init__(f"Nombre de destino duplicado: {names}")


class ExistingDestinationError(RenameError):
    """El destino ya existe y no forma parte del lote."""

    def __init__(self, destinations: Sequence[str]):
        self.destinations = list(destinations)
        names = "\n".join(os.path.basename(p) for p in self.destinations)
        super().__init__(f"Ya existe un archivo con el nombre de destino:\n{names}")


class MissingSourceError(RenameError):
    """El archivo de origen ya no existe."""

    def __init__(self, sources: Sequence[str]):
        self.sources = list(sources)
        names = "\n".join(os.path.basename(p) for p in self.sources)
        super().__init__(f"No se encontró el archivo de origen:\n{names}")


class RenameTransactionError(RenameError):
    """Falló el renombrado y se intentó restaurar el estado original."""

    def __init__(self, message: str, rollback_errors: Optional[Sequence[str]] = None):
        self.rollback_errors = list(rollback_errors or [])
        if self.rollback_errors:
            message += "\n\nAdemás, no se pudieron restaurar:\n" + "\n".join(
                self.rollback_errors
            )
        super().__init__(message)


@dataclass
class RenameGroup:
    """Renombrado de un video junto con sus subtítulos asociados."""

    video_src: str
    video_dst: str
    subtitles: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class RenameRecord:
    """Cambios realmente realizados, para poder deshacerlos."""

    video_old: str
    video_new: str
    subtitles: List[Tuple[str, str]] = field(default_factory=list)

    def reversed_group(self) -> RenameGroup:
        return RenameGroup(
            video_src=self.video_new,
            video_dst=self.video_old,
            subtitles=[(new, old) for old, new in self.subtitles],
        )


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _unique_temp_path(src: str) -> str:
    directory = os.path.dirname(src) or "."
    while True:
        candidate = os.path.join(directory, f".renombrador-tmp-{uuid.uuid4().hex}")
        if not os.path.exists(candidate):
            return candidate


def _restore(source: str, destination: str) -> Optional[str]:
    """Intenta mover source -> destination y devuelve un error legible o None."""
    if not os.path.exists(source):
        return f"No se encontró {os.path.basename(source)} para restaurar."
    try:
        os.replace(source, destination)
        return None
    except OSError as exc:
        return f"{os.path.basename(source)} -> {os.path.basename(destination)}: {exc}"


def execute_rename_groups(
    groups: Sequence[RenameGroup], overwrite: bool = False
) -> List[Optional[RenameRecord]]:
    """
    Ejecuta uno o varios grupos de renombrado de forma transaccional.

    Devuelve una lista alineada con ``groups``: un ``RenameRecord`` por cada
    grupo que cambió algo, o ``None`` si el grupo era un no-op.

    Si ``overwrite`` es False y algún destino externo ya existe, lanza
    ``ExistingDestinationError`` sin tocar el disco. Los destinos duplicados
    dentro del mismo lote se rechazan siempre.
    """
    group_list = list(groups)
    records: List[Optional[RenameRecord]] = [None] * len(group_list)

    # Operaciones reales: el video siempre va antes que sus subtítulos.
    operations: List[Tuple[str, str, int]] = []
    for index, group in enumerate(group_list):
        if os.path.abspath(group.video_src) != os.path.abspath(group.video_dst):
            operations.append((group.video_src, group.video_dst, index))
        for sub_src, sub_dst in group.subtitles:
            if os.path.abspath(sub_src) != os.path.abspath(sub_dst):
                operations.append((sub_src, sub_dst, index))

    if not operations:
        return records

    missing = [src for src, _, _ in operations if not os.path.exists(src)]
    if missing:
        raise MissingSourceError(missing)

    # Destinos duplicados (comparación insensible a mayúsculas en Windows).
    seen: dict = {}
    duplicates: List[str] = []
    for _, dst, _ in operations:
        key = _norm(dst)
        if key in seen:
            duplicates.append(dst)
        else:
            seen[key] = dst
    if duplicates:
        raise DuplicateDestinationError(duplicates)

    # Colisiones con archivos externos al lote.
    source_keys = {_norm(src) for src, _, _ in operations}
    external = [
        dst
        for _, dst, _ in operations
        if os.path.exists(dst) and _norm(dst) not in source_keys
    ]
    if external and not overwrite:
        raise ExistingDestinationError(external)

    # Fase 1: apartar todos los orígenes con nombres temporales. Esto libera
    # los destinos y permite intercambios/ciclos sin colisiones.
    staged: List[Tuple[str, str, str]] = []
    for src, dst, _ in operations:
        temp = _unique_temp_path(src)
        try:
            os.replace(src, temp)
        except OSError as exc:
            rollback_errors = [
                err
                for old_src, _, old_temp in reversed(staged)
                for err in [_restore(old_temp, old_src)]
                if err
            ]
            raise RenameTransactionError(
                f"No se pudo preparar el renombrado de "
                f"{os.path.basename(src)}: {exc}",
                rollback_errors,
            ) from exc
        staged.append((src, dst, temp))

    # Fase 2: mover los temporales a su destino final.
    for position, (src, dst, temp) in enumerate(staged):
        try:
            os.replace(temp, dst)
        except OSError as exc:
            rollback_errors = []

            # Los destinos ya completados pueden ser el origen de otra operación
            # (cadena A->B->C). Primero se apartan todos para liberar las rutas.
            rollback_temps: List[Tuple[str, str]] = []
            for old_src, old_dst, _ in staged[:position]:
                rollback_temp = _unique_temp_path(old_dst)
                error = _restore(old_dst, rollback_temp)
                if error:
                    rollback_errors.append(error)
                else:
                    rollback_temps.append((old_src, rollback_temp))

            for old_src, rollback_temp in rollback_temps:
                error = _restore(rollback_temp, old_src)
                if error:
                    rollback_errors.append(error)

            # Restaurar el que falló y los que aún no se habían movido.
            for old_src, _, old_temp in staged[position:]:
                error = _restore(old_temp, old_src)
                if error:
                    rollback_errors.append(error)

            raise RenameTransactionError(
                f"No se pudo renombrar {os.path.basename(src)} -> "
                f"{os.path.basename(dst)}: {exc}",
                rollback_errors,
            ) from exc

    changed_indices = {op_index for _, _, op_index in operations}
    for index in changed_indices:
        group = group_list[index]
        records[index] = RenameRecord(
            video_old=group.video_src,
            video_new=group.video_dst,
            subtitles=list(group.subtitles),
        )

    return records
