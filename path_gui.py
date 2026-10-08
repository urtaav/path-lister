"""
Path Lister: ventana para copiar una ruta en todas sus formas.

La lanza el menú contextual de Windows (ver install_context_menu.py):
    pythonw path_gui.py "C:\\ruta\\al\\archivo.pdf"

Si seleccionas varios archivos, Explorer abre un proceso por archivo; el
primero escucha en 127.0.0.1 unos instantes y junta las rutas de los demás
para mostrar una sola ventana.

El aspecto sigue al sistema: tema claro/oscuro y color de acento de Windows.
Para forzar un tema: variable de entorno PATHLISTER_THEME=light|dark.

Atajos: 1-9 copiar fila · Enter copiar primera · Tab / ← → cambiar pestaña · Esc cerrar
"""
from __future__ import annotations

import ctypes
import json
import os
import socket
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path

from variantes import secciones_de

PUERTO = 47653
ESPERA_AGRUPAR = 0.35  # segundos para juntar una selección múltiple
MAX_LINEAS = 3         # líneas visibles por fila con varias rutas
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "PathLister" / "config.json"

# Colores de Windows 11 (Fluent). El acento se lee del sistema.
TEMAS = {
    "dark": {
        "bg": "#202020", "fila": "#2b2b2b", "fila_hover": "#323232", "borde": "#1d1d1d",
        "separador": "#3a3a3a", "texto": "#ffffff", "secundario": "#c5c5c5", "tenue": "#9d9d9d",
        "boton_hover": "#3d3d3d", "aviso": "#fce100", "acento": "#4cc2ff", "sobre_acento": "#000000",
    },
    "light": {
        "bg": "#f3f3f3", "fila": "#fbfbfb", "fila_hover": "#f6f6f6", "borde": "#e5e5e5",
        "separador": "#e0e0e0", "texto": "#1b1b1b", "secundario": "#5d5d5d", "tenue": "#8a8a8a",
        "boton_hover": "#ececec", "aviso": "#9d5d00", "acento": "#005fb8", "sobre_acento": "#ffffff",
    },
}

# Glifos de Segoe Fluent Icons (Windows 11); si no existe la fuente se usa texto
ICONOS_FLUENT = {"archivo": "\uE8A5", "carpeta": "\uE8B7", "varios": "\uE762",
                 "copiar": "\uE8C8", "ok": "\uE73E", "check": "\uE73E"}
ICONOS_TEXTO = {"archivo": "▤", "carpeta": "▰", "varios": "▤", "copiar": "⧉", "ok": "✓", "check": "✓"}


# ------------------------------------------------------------ selección múltiple

def recolectar_rutas(argv: list[str]) -> list[str] | None:
    """Devuelve las rutas a mostrar, o None si se las pasamos a otra instancia."""
    rutas = list(argv)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", PUERTO))
    except OSError:
        srv.close()
        try:
            with socket.create_connection(("127.0.0.1", PUERTO), timeout=1) as c:
                c.sendall("\n".join(rutas).encode("utf-8"))
            return None
        except OSError:
            return rutas  # el puerto lo usa otro programa: ventana propia

    srv.listen()
    srv.settimeout(0.05)
    fin = time.monotonic() + ESPERA_AGRUPAR
    while time.monotonic() < fin:
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        with conn:
            conn.settimeout(1)
            datos = b""
            while chunk := conn.recv(65536):
                datos += chunk
        rutas += [r for r in datos.decode("utf-8").split("\n") if r]
        fin = max(fin, time.monotonic() + 0.2)
    srv.close()
    return list(dict.fromkeys(rutas))  # sin duplicados, mismo orden


# ------------------------------------------------------------ sistema

def copiar_al_portapapeles(texto: str, root: tk.Tk):
    """Win32 directo: el texto sigue en el portapapeles al cerrar la ventana."""
    if os.name == "nt":
        try:
            _copiar_win32(texto)
            return
        except OSError:
            pass
    root.clipboard_clear()
    root.clipboard_append(texto)
    root.update()


def _copiar_win32(texto: str):
    from ctypes import wintypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.SetClipboardData.restype = wintypes.HANDLE

    datos = texto.replace("\n", "\r\n").encode("utf-16-le") + b"\0\0"
    for _ in range(10):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        raise OSError("portapapeles ocupado")
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(datos))  # GMEM_MOVEABLE
        ptr = k32.GlobalLock(h)
        ctypes.memmove(ptr, datos, len(datos))
        k32.GlobalUnlock(h)
        if not u32.SetClipboardData(13, h):  # CF_UNICODETEXT
            raise OSError("SetClipboardData falló")
    finally:
        u32.CloseClipboard()


def _leer_registro(clave: str, valor: str):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
        return winreg.QueryValueEx(k, valor)[0]


def tema_del_sistema() -> dict:
    """Paleta clara u oscura según Windows, con el color de acento del usuario."""
    forzado = os.environ.get("PATHLISTER_THEME", "").lower()
    if forzado in ("light", "dark"):
        claro = forzado == "light"
    elif os.name == "nt":
        try:
            claro = _leer_registro(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                                   "AppsUseLightTheme") == 1
        except OSError:
            claro = True
    else:
        claro = True

    tema = dict(TEMAS["light" if claro else "dark"], claro=claro)
    if os.name == "nt":
        try:
            paleta = _leer_registro(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent",
                                    "AccentPalette")
            # 8 colores RGBA: claro3, claro2, claro1, base, oscuro1, oscuro2, oscuro3, ...
            i = 4 if claro else 1  # los tonos que usa Windows 11 para controles
            tema["acento"] = "#{:02x}{:02x}{:02x}".format(*paleta[i * 4:i * 4 + 3])
        except (OSError, ValueError, TypeError):
            pass
    return tema


def activar_dpi():
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def barra_titulo_nativa(root: tk.Tk, oscura: bool):
    """Barra de título oscura cuando Windows está en modo oscuro."""
    if os.name != "nt" or not oscura:
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        valor = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(valor), 4)
    except (AttributeError, OSError):
        pass


def cargar_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_config(cfg: dict):
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg), encoding="utf-8")
    except OSError:
        pass


def tamano_legible(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024


def primera_fuente(disponibles: set[str], *opciones: str) -> str:
    return next((f for f in opciones if f in disponibles), "TkDefaultFont")


# ------------------------------------------------------------ interfaz

class App:
    ANCHO = 600

    def __init__(self, root: tk.Tk, rutas: list[str]):
        self.root = root
        self.rutas = rutas
        self.c = tema_del_sistema()
        self.cfg = cargar_config()
        self.secciones = secciones_de(rutas)
        self.titulos = [t for t, _ in self.secciones]
        self.tab = self.cfg.get("pestana") if self.cfg.get("pestana") in self.titulos else self.titulos[0]
        self.cerrar_al_copiar = bool(self.cfg.get("cerrar_al_copiar", False))
        self.filas: list[tuple[str, str, tk.Label]] = []
        self._aviso_id = None

        # Escala de píxeles según DPI (tk ya escala las fuentes por sí solo)
        self.s = float(root.tk.call("tk", "scaling")) / (96 / 72)

        familias = set(tkfont.families(root))
        sans = primera_fuente(familias, "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Ubuntu", "Helvetica")
        negrita = primera_fuente(familias, "Segoe UI Semibold", sans)
        mono = primera_fuente(familias, "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono")
        self.ic = ICONOS_FLUENT if "Segoe Fluent Icons" in familias else ICONOS_TEXTO
        ic_fam = "Segoe Fluent Icons" if self.ic is ICONOS_FLUENT else sans
        self.f = {
            "titulo": (negrita, 10),
            "sub": (sans, 8),
            "tab": (sans, 9),
            "tab_on": (negrita, 9),
            "etiqueta": (sans, 8),
            "valor": (mono, 9),
            "icono": (ic_fam, 10),
            "icono_g": (ic_fam, 16),
            "check": (ic_fam, 7),
            "pie": (sans, 8),
        }

        root.title("Path Lister")
        root.configure(bg=self.c["bg"])
        root.resizable(False, False)
        self._icono_ventana()

        m = self.px(12)
        self._cabecera(m)
        self.barra_tabs = tk.Frame(root, bg=self.c["bg"])
        self.barra_tabs.pack(fill="x", padx=m - self.px(6))
        self.lista = tk.Frame(root, bg=self.c["bg"])
        self.lista.pack(fill="both", expand=True, padx=m, pady=(self.px(6), self.px(8)))
        self._pie(m)

        self._pintar_tabs()
        self._pintar_lista()
        self._atajos()

    def px(self, n: float) -> int:
        return int(round(n * self.s))

    def _icono_ventana(self):
        """Icono simple del color de acento en vez de la pluma de Python."""
        img = tk.PhotoImage(width=32, height=32)
        img.put(self.c["acento"], to=(5, 2, 25, 30))      # hoja
        img.put(self.c["bg"], to=(19, 2, 25, 8))          # esquina doblada
        for y in (12, 17, 22):                            # renglones = "ruta"
            img.put(self.c["sobre_acento"], to=(9, y, 21, y + 2))
        self.root.iconphoto(True, img)
        self._img = img  # que no la borre el recolector

    # ---------------------------------------------------- cabecera

    def _cabecera(self, m: int):
        c = self.c
        cab = tk.Frame(self.root, bg=c["bg"])
        cab.pack(fill="x", padx=m, pady=(self.px(10), self.px(6)))

        varios = len(self.rutas) > 1
        p = Path(os.path.abspath(self.rutas[0]))
        existe = p.exists()
        tipo = "varios" if varios else ("carpeta" if p.is_dir() else "archivo")

        tk.Label(cab, text=self.ic[tipo], font=self.f["icono_g"], fg=c["acento"], bg=c["bg"]).pack(
            side="left", anchor="n", padx=(0, self.px(10)), pady=(self.px(2), 0))

        textos = tk.Frame(cab, bg=c["bg"])
        textos.pack(side="left", fill="x", expand=True)

        if varios:
            titulo = f"{len(self.rutas)} elementos"
            carpetas = {str(Path(os.path.abspath(r)).parent) for r in self.rutas}
            sub = carpetas.pop() if len(carpetas) == 1 else f"en {len(carpetas)} carpetas"
            meta, color = "cada opción copia todas las rutas", c["secundario"]
        else:
            titulo = p.name or str(p)
            sub = str(p.parent) if p.parent != p else ""
            if existe:
                meta, color = self._meta(p), c["secundario"]
            else:
                meta, color = "La ruta no existe (las opciones se calculan igual)", c["aviso"]

        ancho_txt = self.px(self.ANCHO - 70)
        tk.Label(textos, text=titulo, font=self.f["titulo"], fg=c["texto"], bg=c["bg"],
                 anchor="w", justify="left", wraplength=ancho_txt).pack(fill="x")
        for texto, fg in ((sub, c["secundario"]), (meta, color)):
            if texto:
                tk.Label(textos, text=texto, font=self.f["sub"], fg=fg, bg=c["bg"],
                         anchor="w", justify="left", wraplength=ancho_txt).pack(fill="x")

    def _meta(self, p: Path) -> str:
        try:
            st = p.stat()
        except OSError:
            return ""
        fecha = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
        if p.is_dir():
            return f"Carpeta · {fecha}"
        ext = p.suffix[1:].upper() or "Archivo"
        return f"{ext} · {tamano_legible(st.st_size)} · {fecha}"

    # ---------------------------------------------------- pestañas (estilo SelectorBar)

    def _pintar_tabs(self):
        c = self.c
        for w in self.barra_tabs.winfo_children():
            w.destroy()
        for titulo in self.titulos:
            activa = titulo == self.tab
            caja = tk.Frame(self.barra_tabs, bg=c["bg"], cursor="hand2")
            caja.pack(side="left")
            lbl = tk.Label(caja, text=titulo, font=self.f["tab_on" if activa else "tab"],
                           fg=c["texto"] if activa else c["secundario"], bg=c["bg"],
                           padx=self.px(6), pady=self.px(2))
            lbl.pack()
            # indicador corto y centrado, como en Windows 11
            barra = tk.Frame(caja, bg=c["acento"] if activa else c["bg"],
                             width=self.px(16), height=self.px(3))
            barra.pack()
            for w in (caja, lbl, barra):
                w.bind("<Button-1>", lambda e, t=titulo: self.ir_a(t))
                if not activa:
                    w.bind("<Enter>", lambda e, l=lbl: l.configure(fg=c["texto"]))
                    w.bind("<Leave>", lambda e, l=lbl: l.configure(fg=c["secundario"]))

    def ir_a(self, titulo: str):
        if titulo == self.tab:
            return
        self.tab = titulo
        self.cfg["pestana"] = titulo
        guardar_config(self.cfg)
        self._pintar_tabs()
        self._pintar_lista()
        self._mantener_en_pantalla()

    def mover_tab(self, paso: int):
        i = self.titulos.index(self.tab)
        self.ir_a(self.titulos[(i + paso) % len(self.titulos)])

    # ---------------------------------------------------- filas (estilo Configuración)

    def _pintar_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        self.filas = []
        items = dict(self.secciones)[self.tab]
        for i, (etiqueta, valor) in enumerate(items):
            self._fila(i, etiqueta, valor)

    def _fila(self, i: int, etiqueta: str, valor: str):
        c = self.c
        fila = tk.Frame(self.lista, bg=c["fila"], cursor="hand2",
                        highlightthickness=1, highlightbackground=c["borde"], highlightcolor=c["borde"])
        fila.pack(fill="x", pady=(0, self.px(2)))
        fila.columnconfigure(0, weight=1)

        atajo = f"  ·  {i + 1}" if i < 9 else ""
        lbl = tk.Label(fila, text=etiqueta + atajo, font=self.f["etiqueta"], fg=c["tenue"],
                       bg=c["fila"], anchor="w")
        lbl.grid(row=0, column=0, sticky="ew", padx=(self.px(10), 0), pady=(self.px(5), 0))

        lineas = valor.split("\n")
        visible = "\n".join(lineas[:MAX_LINEAS])
        if len(lineas) > MAX_LINEAS:
            visible += f"\n… y {len(lineas) - MAX_LINEAS} más"
        val = tk.Label(fila, text=visible, font=self.f["valor"], fg=c["texto"], bg=c["fila"],
                       anchor="w", justify="left", wraplength=self.px(self.ANCHO - 80))
        val.grid(row=1, column=0, sticky="ew", padx=(self.px(10), 0), pady=(0, self.px(5)))

        boton = tk.Label(fila, text=self.ic["copiar"], font=self.f["icono"], fg=c["secundario"],
                         bg=c["fila"], width=3, pady=self.px(4))
        boton.grid(row=0, column=1, rowspan=2, padx=self.px(4))

        partes = (fila, lbl, val)

        def entrar(_):
            for w in partes:
                w.configure(bg=c["fila_hover"])
            boton.configure(bg=c["boton_hover"])

        def salir(_):
            for w in (*partes, boton):
                w.configure(bg=c["fila"])

        for w in (*partes, boton):
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", salir)
            w.bind("<Button-1>", lambda e, n=i: self.copiar(n))
        self.filas.append((etiqueta, valor, boton))

    # ---------------------------------------------------- copiar

    def copiar(self, n: int):
        if n >= len(self.filas):
            return
        etiqueta, valor, boton = self.filas[n]
        copiar_al_portapapeles(valor, self.root)

        boton.configure(text=self.ic["ok"], fg=self.c["acento"])
        self.root.after(1200, lambda: boton.winfo_exists()
                        and boton.configure(text=self.ic["copiar"], fg=self.c["secundario"]))
        self.avisar(f"Copiado: {etiqueta}")
        if self.cerrar_al_copiar:
            self.root.after(300, self.root.destroy)

    # ---------------------------------------------------- pie

    def _pie(self, m: int):
        c = self.c
        pie = tk.Frame(self.root, bg=c["bg"])
        pie.pack(fill="x", side="bottom", padx=m, pady=self.px(6))
        tk.Frame(self.root, bg=c["separador"], height=1).pack(fill="x", side="bottom")

        # Casilla estilo Windows 11: cuadro con borde, relleno de acento al marcar
        lado = self.px(16)
        self.check = tk.Canvas(pie, width=lado, height=lado, bg=c["bg"], highlightthickness=0, cursor="hand2")
        self.check.pack(side="left")
        txt = tk.Label(pie, text="Cerrar al copiar", font=self.f["pie"], fg=c["texto"],
                       bg=c["bg"], cursor="hand2")
        txt.pack(side="left", padx=(self.px(6), 0))
        for w in (self.check, txt):
            w.bind("<Button-1>", lambda e: self.alternar_cerrar())
        self._pintar_check()

        self.ayuda = "1–9 copiar · Tab cambiar · Esc cerrar"
        self.estado = tk.Label(pie, text=self.ayuda, font=self.f["pie"], fg=c["tenue"], bg=c["bg"])
        self.estado.pack(side="right")

    def _pintar_check(self):
        c, lado = self.c, self.px(16)
        self.check.delete("all")
        if self.cerrar_al_copiar:
            self.check.create_rectangle(1, 1, lado - 1, lado - 1, fill=c["acento"], outline=c["acento"])
            self.check.create_text(lado / 2, lado / 2, text=self.ic["check"],
                                   fill=c["sobre_acento"], font=self.f["check"])
        else:
            self.check.create_rectangle(1, 1, lado - 1, lado - 1, fill=c["fila"], outline=c["tenue"])

    def alternar_cerrar(self):
        self.cerrar_al_copiar = not self.cerrar_al_copiar
        self.cfg["cerrar_al_copiar"] = self.cerrar_al_copiar
        guardar_config(self.cfg)
        self._pintar_check()

    def avisar(self, texto: str):
        self.estado.configure(text=texto, fg=self.c["acento"])
        if self._aviso_id:
            self.root.after_cancel(self._aviso_id)
        self._aviso_id = self.root.after(
            1800, lambda: self.estado.configure(text=self.ayuda, fg=self.c["tenue"]))

    # ---------------------------------------------------- teclado y posición

    def _atajos(self):
        r = self.root
        r.bind("<Escape>", lambda e: r.destroy())
        r.bind("<Return>", lambda e: self.copiar(0))
        r.bind("<Tab>", lambda e: (self.mover_tab(1), "break")[1])
        r.bind("<Shift-Tab>", lambda e: (self.mover_tab(-1), "break")[1])
        r.bind("<Right>", lambda e: self.mover_tab(1))
        r.bind("<Left>", lambda e: self.mover_tab(-1))
        for d in range(1, 10):
            r.bind(str(d), lambda e, n=d - 1: self.copiar(n))
            r.bind(f"<KP_{d}>", lambda e, n=d - 1: self.copiar(n))

    def _tamano(self) -> tuple[int, int]:
        self.root.update_idletasks()
        return max(self.root.winfo_reqwidth(), self.px(self.ANCHO)), self.root.winfo_reqheight()

    def colocar_junto_al_cursor(self):
        r = self.root
        w, h = self._tamano()
        x, y = r.winfo_pointerxy()
        x = min(max(0, x - w // 3), r.winfo_screenwidth() - w - self.px(8))
        y = min(max(0, y - self.px(30)), r.winfo_screenheight() - h - self.px(60))
        r.geometry(f"{w}x{h}+{x}+{y}")

    def _mantener_en_pantalla(self):
        """Al cambiar de pestaña cambia la altura: ajusta sin mover la ventana."""
        r = self.root
        w, h = self._tamano()
        y = min(r.winfo_y(), r.winfo_screenheight() - h - self.px(60))
        r.geometry(f"{w}x{h}+{r.winfo_x()}+{max(0, y)}")


def main():
    if len(sys.argv) < 2:
        print("Uso: path_gui.py <ruta> [<ruta> ...]")
        sys.exit(1)

    rutas = recolectar_rutas(sys.argv[1:])
    if rutas is None:
        return  # otra instancia mostrará estas rutas

    activar_dpi()
    root = tk.Tk()
    root.withdraw()
    app = App(root, rutas)
    app.colocar_junto_al_cursor()
    barra_titulo_nativa(root, oscura=not app.c["claro"])
    root.deiconify()
    root.attributes("-topmost", True)
    root.after(50, root.focus_force)
    root.mainloop()


if __name__ == "__main__":
    main()
