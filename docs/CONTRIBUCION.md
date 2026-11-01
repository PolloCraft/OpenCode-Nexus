# Contribuir

Las contribuciones se agradecen en diagnóstico, robustez, accesibilidad, documentación y
soporte de hardware. Hay una línea editorial que conviene leer antes de abrir un PR.

## Qué no se acepta

**Nuevas funciones cuya finalidad sea eludir los límites de uso de los servicios
implicados.** Lo concreto:

- rotación de IP o de pool de proxies cuyo objeto sea reiniciar una cuota;
- síntesis de cabeceras de identidad del cliente oficial para parecer la app autorizada;
- enrutado de tráfico entre cuentas o modelos según cuotas restantes;
- borrado de sesiones o de identificadores para esquivar controles de cuenta;
- adaptación de clientes para usar modelos “gratuitos” fuera de su aplicación oficial.

Motivo: los límites los evalúa el servidor del proveedor y eludirlos incumple sus términos.
No es una discusión técnica: aunque el código funcione, no se fusiona. La evidencia de esa
política es que `Nexus/oplire/src/identity.rs` y `quota.rs` se excluyen de las releases
aunque el proyecto los tenga (ver [`HISTORIAL.md`](HISTORIAL.md)).

Sí se acepta, en cambio: **reparaciones reales de runtime** (por ejemplo detectar que
`bin/opencode.exe` es el aviso de un *postinstall* roto y no un PE `MZ`, y reinstalarlo),
mejoras de diagnóstico, respaldo/restauración, accesibilidad, empaquetado y documentación.

## Configuración de desarrollo

```bat
git clone https://github.com/PolloCraft/OpenCode-Nexus.git
cd OpenCode-Nexus
python Nexus\nexus_app.py
```

Requisitos de cada motor en [`INSTALACION.md`](INSTALACION.md). Para trabajar sin permisos de
administrador, deja *IP / WARP* y la edición de registro en manos del usuario final: usa las
rutas de respaldo y comprueba que la app degrada con elegancia cuando un binario no está.

## Convenciones del proyecto

| Regla | Por qué |
| --- | --- |
| La GUI **solo** stdlib de Python (Tkinter, `urllib`); cero dependencias externas | La suite debe funcionar en cualquier Windows con Python limpio |
| Toda la lógica de motor vive en `modules/*_ops.py`; `nexus_app.py` no llama a `subprocess` directamente | Separación probada: la GUI y los menús de consola comparten operaciones |
| **Respaldar antes de escribir** cualquier JSON/`config`/`.env` del usuario | Es la política histórica del proyecto (`backup_file`, respaldos de sesión) |
| Iconos solo con glifos BMP, nunca emoji | Tk no renderiza emoji y muestra “tofu” |
| Salida de procesos siempre en la caja `LogBox` de la página, vía cola de UI | Evita data races entre hilos de subproceso y el hilo de Tk |
| Refrescar solo la página activa; `F5` para refrescar todo | El refresco global de 1 s se notaba en ventanas grandes |
| No tocar `Nexus/claude/`, `Nexus/antigravity/`, `target/`, `node_modules/` | Son workspaces de upstream; están en `.gitignore` |
| La versión solo en `modules/common.py::APP_VERSION` | Antes había cuatro cadenas distintas y *Acerca de* mostraba dos a la vez |
| `chcp 65001` y salidas ASCII en los `.bat`/menús de consola | Windows con codepage 850 rompe acentos |

## Flujo de trabajo

1. Abre un **Issue** describiendo el fallo o la mejora, con la salida de
   *Mantenimiento → Diagnóstico → Comprobar todo* y de la página *Sistema* si es un problema
   de entorno.
2. Ramas desde `main`: `fix/<algo>`, `feat/<algo>`, `docs/<algo>`.
3. `python -m py_compile` sobre los `.py` tocados y arranque manual de las páginas afectadas.
4. PR pequeño, con el *antes/después* en la descripción.

## Etiquetado de releases

`vMAJOR.MINOR.PATCH` sobre `main`, con:

- notas que digan qué cambió realmente (se comprueba comparando árboles, no “de memoria”);
- un `.zip` reconstruido **sin artefactos ni `.git/` de terceros**;
- `*-SHA256SUMS.txt`.

El `MANIFEST.txt` de cada paquete consigna qué se excluyó y por qué; mantenlo al día si
cambias las reglas de empaquetado.

## Reportar incidencias de seguridad

No abras un Issue público para algo que exponga credenciales, rutas de sesión o el
funcionamiento interno del proxy: escribe al maintainer a través de
[GitHub](https://github.com/PolloCraft). La suite maneja archivos con datos de cuenta
(`antigravity-accounts.json`, `~/.fcc/.env`, `%APPDATA%\oplire\config.json`): cualquier fallo
que los filtre es prioridad máxima.
