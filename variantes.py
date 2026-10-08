"""
Variantes de una ruta agrupadas por uso (Windows, Linux/Mac, código, web, partes).

    secciones_de(["C:\\docs\\a.pdf"]) -> [("Windows", [("Ruta completa", "C:\\docs\\a.pdf"), ...]), ...]
"""
from __future__ import annotations

import ctypes
import html
import json
import os
import shlex
from pathlib import Path

ES_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------- utilidades

def _unc(s: str) -> str | None:
    """Unidad mapeada (Z:\\...) -> ruta de red \\\\servidor\\recurso\\..."""
    if not ES_WINDOWS or len(s) < 2 or s[1] != ":":
        return None
    buf = ctypes.create_unicode_buffer(1024)
    largo = ctypes.c_ulong(len(buf))
    if ctypes.windll.mpr.WNetGetConnectionW(s[:2], buf, ctypes.byref(largo)) != 0:
        return None
    return buf.value + s[2:]


def _corta(s: str) -> str | None:
    """Ruta corta 8.3 (C:\\PROGRA~1\\...), útil para programas viejos."""
    if not ES_WINDOWS:
        return None
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(s, buf, len(buf)) == 0:
        return None
    return buf.value if buf.value != s else None


def _unix_desde_windows(s: str, prefijo: str) -> str | None:
    """C:\\a\\b -> {prefijo}c/a/b (WSL: /mnt/, Git Bash: /, Cygwin: /cygdrive/)."""
    if len(s) >= 2 and s[1] == ":":
        return f"{prefijo}{s[0].lower()}{s[2:].replace(chr(92), '/')}"
    return None


def _relativa_usuario(p: Path) -> str | None:
    try:
        rel = p.relative_to(Path.home())
    except ValueError:
        return None
    base = "%USERPROFILE%" if ES_WINDOWS else "~"
    sep = "\\" if ES_WINDOWS else "/"
    return base if str(rel) == "." else f"{base}{sep}{rel}"


def _python_raw(s: str) -> str | None:
    # r"C:\" no es válido en Python (raw no puede terminar en \)
    return None if s.endswith("\\") else f'r"{s}"'


# ---------------------------------------------------------------- variantes

def secciones(p: Path) -> list[tuple[str, list[tuple[str, str | None]]]]:
    # abspath y no resolve(): resolve convierte unidades mapeadas a UNC
    p = Path(os.path.abspath(p.expanduser()))
    s = str(p)
    uri = p.as_uri()
    nombre = p.name or s

    if ES_WINDOWS:
        wsl = _unix_desde_windows(s, "/mnt/")
        sistema = [
            ("Windows", [
                ("Ruta completa", s),
                ("Con comillas", f'"{s}"'),
                ("Ruta de red (UNC)", _unc(s)),
                ("PowerShell", "'" + s.replace("'", "''") + "'"),
                ("Ruta corta 8.3", _corta(s)),
            ]),
            ("Linux · WSL", [
                ("WSL", wsl),
                # solo si cambia algo (espacios, paréntesis, etc.)
                ("WSL escapada (bash)", shlex.quote(wsl) if wsl and shlex.quote(wsl) != wsl else None),
                ("Git Bash / MSYS2", _unix_desde_windows(s, "/")),
                ("Cygwin", _unix_desde_windows(s, "/cygdrive/")),
            ]),
        ]
    else:
        sistema = [
            ("Linux · Mac", [
                ("Ruta completa", s),
                ("Escapada (terminal)", shlex.quote(s)),
                ("Con comillas", f'"{s}"'),
            ]),
        ]

    codigo = ("Código", [
        ("Python raw", _python_raw(s)),
        ("Python / JSON / JS", json.dumps(s, ensure_ascii=False)),
        ("pathlib", f'Path(r"{s}")' if _python_raw(s) else f"Path({json.dumps(s)})"),
        ("Barras /", s.replace("\\", "/")),
        ("C# verbatim", '@"' + s.replace('"', '""') + '"' if ES_WINDOWS else None),
    ])
    web = ("Web · Docs", [
        ("file:// URL", uri),
        ("Markdown", f"[{nombre}]({uri})"),
        ("HTML", f'<a href="{html.escape(uri)}">{html.escape(nombre)}</a>'),
    ])
    es_archivo = not p.is_dir()
    partes = ("Partes", [
        ("Nombre", p.name or None),
        ("Sin extensión", p.stem if es_archivo and p.suffix else None),
        ("Extensión", p.suffix or None),
        ("Carpeta contenedora", str(p.parent) if p.parent != p else None),
        ("Relativa al usuario", _relativa_usuario(p)),
    ])
    return [*sistema, codigo, web, partes]


def secciones_de(rutas: list[str]) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Igual que secciones() pero para una o varias rutas: con varias, cada valor
    son todas las rutas una por línea. Omite variantes que no aplican a todas.
    """
    por_ruta = [secciones(Path(r)) for r in rutas]
    resultado = []
    for i, (titulo, items) in enumerate(por_ruta[0]):
        filas = []
        for j, (etiqueta, _) in enumerate(items):
            valores = [secs[i][1][j][1] for secs in por_ruta]
            if all(valores):
                filas.append((etiqueta, "\n".join(valores)))
        if filas:
            resultado.append((titulo, filas))
    return resultado
