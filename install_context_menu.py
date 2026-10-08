"""
Agrega/quita la opción "Ver rutas (Path Lister)" al menú contextual de Windows.

Usa HKEY_CURRENT_USER, no requiere permisos de administrador.

    python install_context_menu.py            # instalar
    python install_context_menu.py --uninstall

En Windows 11 aparece en "Mostrar más opciones" (o Shift + clic derecho).
"""
from pathlib import Path
import sys
import winreg

NOMBRE_CLAVE = "PathLister"
TEXTO_MENU = "Ver rutas (Path Lister)"

# Archivos, carpetas y fondo de carpeta (clic derecho en espacio vacío)
DESTINOS = {
    r"Software\Classes\*\shell": "%1",
    r"Software\Classes\Directory\shell": "%1",
    r"Software\Classes\Directory\Background\shell": "%V",
}


def pythonw() -> str:
    exe = Path(sys.executable)
    candidato = exe.with_name("pythonw.exe")
    return str(candidato if candidato.exists() else exe)


def instalar():
    script = Path(__file__).resolve().with_name("path_gui.py")
    for base, arg in DESTINOS.items():
        ruta = f"{base}\\{NOMBRE_CLAVE}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ruta) as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, TEXTO_MENU)
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, "shell32.dll,134")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ruta + r"\command") as k:
            comando = f'"{pythonw()}" "{script}" "{arg}"'
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, comando)
        print(f"OK  HKCU\\{ruta}")
    print("Instalado.")


def desinstalar():
    for base in DESTINOS:
        ruta = f"{base}\\{NOMBRE_CLAVE}"
        for sub in (ruta + r"\command", ruta):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except FileNotFoundError:
                pass
        print(f"Eliminado HKCU\\{ruta}")
    print("Desinstalado.")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        desinstalar()
    else:
        instalar()
