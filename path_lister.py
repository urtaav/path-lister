from pathlib import Path
import argparse
import sys


def path_variants(p: Path) -> dict:
    """
    Devuelve todas las representaciones útiles de una ruta.
    """
    abs_path = p.resolve()
    s = str(abs_path)

    variants = {}

    # 1) Tal cual (nativo del SO)
    variants["native"] = s

    # 2) Escapada para Python string normal (backslashes dobles)
    variants["python_str"] = s.replace("\\", "\\\\")

    # 3) Raw string para Python  (r"C:\...")
    if "\\" in s:
        variants["python_raw"] = f'r"{s}"'
    else:
        variants["python_raw"] = f'r"{s}"'  # también válido en Linux

    # 4) Forward slashes (funciona en Python en Windows y Linux)
    variants["forward_slash"] = s.replace("\\", "/")

    # 5) file:// URL (útil para HTML, VS Code, etc.)
    variants["file_url"] = abs_path.as_uri()

    # 6) WSL / Git Bash (si es Windows)
    if len(s) >= 3 and s[1] == ":":
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/")
        variants["wsl"] = f"/mnt/{drive}{rest}"
    else:
        # Si es Linux, ofrecer también el estilo Windows (aproximado)
        variants["wsl"] = s  # ya es Unix-like

    # 7) Solo el nombre
    variants["name"] = p.name

    return variants


def list_folder(root: Path, recursive: bool = False, only_dirs: bool = False,
                only_files: bool = False, pattern: str = "*"):
    """Genera entradas de la carpeta según filtros."""
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    for p in sorted(iterator):
        if only_dirs and not p.is_dir():
            continue
        if only_files and not p.is_file():
            continue
        yield p


def print_entry(p: Path, mode: str = "table"):
    """Imprime una entrada con todas sus variantes."""
    v = path_variants(p)
    kind = "DIR " if p.is_dir() else "FILE"

    if mode == "table":
        print(f"\n[{kind}] {v['name']}")
        print(f"  native         : {v['native']}")
        print(f"  python_str     : \"{v['python_str']}\"")
        print(f"  python_raw     : {v['python_raw']}")
        print(f"  forward_slash  : {v['forward_slash']}")
        print(f"  file_url       : {v['file_url']}")
        print(f"  wsl            : {v['wsl']}")
    elif mode == "native":
        print(v["native"])
    elif mode == "python_str":
        print(f'"{v["python_str"]}"')
    elif mode == "python_raw":
        print(v["python_raw"])
    elif mode == "forward_slash":
        print(v["forward_slash"])
    elif mode == "file_url":
        print(v["file_url"])
    elif mode == "wsl":
        print(v["wsl"])
    elif mode == "csv":
        # Todo en una línea separado por ;
        print(";".join([
            v["native"], v["python_str"], v["python_raw"],
            v["forward_slash"], v["file_url"], v["wsl"]
        ]))
    else:
        print(v["native"])


def main():
    parser = argparse.ArgumentParser(
        description="Lista una carpeta mostrando TODAS las variantes de ruta."
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Carpeta a listar (por defecto: actual)"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="Listar recursivamente"
    )
    parser.add_argument(
        "-d", "--dirs-only", action="store_true",
        help="Solo carpetas"
    )
    parser.add_argument(
        "-f", "--files-only", action="store_true",
        help="Solo archivos"
    )
    parser.add_argument(
        "-p", "--pattern", default="*",
        help="Patrón glob (ej. '*.pdf')"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["table", "native", "python_str", "python_raw",
                 "forward_slash", "file_url", "wsl", "csv"],
        default="table",
        help="Formato de salida (default: table)"
    )

    args = parser.parse_args()

    root = Path(args.folder)
    if not root.exists():
        print(f"[ERROR] No existe: {root}", file=sys.stderr)
        sys.exit(1)

    print(f"# Carpeta raíz: {root.resolve()}")
    print(f"# Modo: {args.mode}")

    count = 0
    for p in list_folder(
        root,
        recursive=args.recursive,
        only_dirs=args.dirs_only,
        only_files=args.files_only,
        pattern=args.pattern
    ):
        print_entry(p, mode=args.mode)
        count += 1

    print(f"\n# Total: {count} entradas")


if __name__ == "__main__":
    main()