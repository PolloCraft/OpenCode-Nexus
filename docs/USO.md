# Uso de NEXUS Suite

Recorrido por las **13 páginas** de la interfaz. Todo lo que aquí se describe es lo que la
aplicación hace con tus archivos: **respalda antes de tocar** y muestra el resultado en la
caja de registro de cada página.

## Cómo navegar

- **Barra lateral** izquierda con las 13 páginas; la página activa queda resaltada.
- **F5** refresca todo; además hay un refresco automático de 1 s solo de la página visible.
- Las **píldoras de cabecera** (OPLIRE · WARP · OPENCODE · PLUGIN · CLAUDE) indican si cada
  motor está localizado y activo. No son un semáforo de “funciona o no”: señalan detección.
- La insignia **ADMIN** aparece cuando la ventana corre con privilegios elevados; el botón
  **Elevar a Admin** relanza la suite para poder operar la red y el registro.
- Al achicar la ventana, el contenido reflowea: botones que no caben pasan a fila propia,
  el subtítulo se oculta bajo 980 px y las píldoras bajo 1040 px.

---

## 1. Inicio

Panel de estado y siete acciones rápidas (rotar/reconectar red, levantar OpenCode local,
levantar el servidor FCC, abrir la consola de administración del dashboard y saltos directos a
las páginas más usadas). Es la pantalla “no me acuerdo de qué estaba haciendo”.

## 2. IP / WARP

Gestión del túnel y de la configuración de red que la suite respalda antes de modificar.

| Acción | Qué hace realmente |
| --- | --- |
| **Estado** | Lee adaptadores, modo DHCP/estático, IP, DNS y estado de WARP |
| **Reconectar** | Renueva el túnel WARP existente |
| **Desconectar WARP** | Cierra el túnel y devuelve la conectividad directa |
| **Restaurar IP original** | Repone la configuración de red desde el respaldo guardado por la suite |

⚠️ Cualquier operación de red puede dejarte sin conectividad hasta que restaures. La suite
guarda respaldo previo, pero **verifica en *Caché* que el respaldo existe** antes de operar, y
ten permisos de administrador.

## 3. Servidor

Tres pestañas internas:

- **Proxy / Dashboard** — arrancar o detener el servidor local del motor (puerto `8080`),
  consultar el estado de la API, abrir el dashboard en el navegador y verificar si proxy y
  daemon están vivos. También inspeccionar sesiones (estado/listado/reparación) y consultar
  la configuración activa.
- **OpenCode Local** — ciclo de vida de `opencode serve`, con detección del binario real.
- **Escritorio (config)** — activar o restaurar la modificación que apunta la configuración de
  OpenCode Desktop al servidor local. El estado se guarda en
  `%LOCALAPPDATA%\oplire\bypass_state.json` y la acción **Restaurar** devuelve el fichero a su
  estado original.

> Usa esta última pestaña solo si entiendes qué hace con tu configuración de OpenCode Desktop.
> No es un mecanismo para sortear límites de uso: los límites los evalúa el servidor del
> proveedor y la suite no ofrece ninguna función orientada a eludirlos.

## 4. Caché

- **Escaneo** de la carpeta de trabajo de OpenCode y su consumo.
- **Limpieza** de artefactos locales. Los archivos de Antigravity están **protegidos siempre**:
  no se borran ni siquiera pidiéndolo.
- **Respaldo de sesiones** — crear, restaurar, eliminar y actualizar copias en
  `%LOCALAPPDATA%\Nexus\backups\sessions\< marca-de-tiempo >`. Esta es la red de seguridad
  de todo lo demás: si una operación de red o de configuración sale mal, desde aquí vuelves atrás.

## 5. Mantenimiento

Tres pestañas de reparación e inventario:

- **Diagnóstico** — `doctor` del motor, sondas de versión de Python/Node/npm/Rust/uv y
  **Comprobar todo**, que resume qué binarios existen y cuáles faltan.
- **Instalar / Reparar** — instaladores y reparaciones de dependencias, incluidos los casos en
  que el paquete de OpenCode quedó con un binario inválido por un *postinstall* roto.
- **PATH / Variables** — editor de `PATH` y de las variables de entorno documentadas en
  `ENV_HELP` (fija, elimina y muestra la que defina cada motor). Escribe en `HKCU\Environment`
  y notifica el cambio a los procesos nuevos.

## 6. AG Cuentas

Administración de las cuentas que el plugin de Antigravity tiene registradas en
`antigravity-accounts.json`: refrescar listado, marcar cuenta activa, añadir, **Cuotas en vivo**
(lee el estado que reporta el propio plugin), verificar una o todas, diagnóstico, eliminar y
restablecimiento del conjunto con respaldo previo.

## 7. AG Plugin

Instalar/actualizar el plugin desde npm, activarlo o desactivarlo en `opencode.json`,
**Comprobar config** (¿está la sección `plugin`?), aplicar el parche de compatibilidad de
rutas, desactivar la auto-actualización y **Reparar plugin**. También entrada de la API key de
Google (`GOOGLE_GENERATIVE_AI_API_KEY`), que se guarda en el entorno del usuario.

## 8. AG Modelos

Alta y baja de modelos del catálogo del plugin en tu configuración de OpenCode, con
respaldo automático del fichero antes de escribir.

## 9. Claude

Integración con el motor **Free Claude Code** (proyecto AGPL de terceros, sin afiliación con
Anthropic):

- Arrancar/detener el servidor local (`127.0.0.1:8082`) y abrir su consola de administración.
- Sincronizar y actualizar el entorno `uv`; instalar el motor desde su upstream.
- Editar `~/.fcc/.env`: modelo y proveedor entre los 20 soportados, con copia `.bak-< marca >`
  automática.

## 10. Claude Agentes

Un botón por cada uno de los 10 agentes que expone FCC (`claude`, `codex`, `opencode`, `cline`,
`aider`, `hermes`, `dsh`, `grok`, `muse`, `pi`) con una insignia de disponibilidad. La insignia
refleja si la suite detecta el binario del agente en tu sistema; las notas de instalación de
cada agente están en `claude_ops.AGENT_HINTS`.

## 11. Claude Doctor

Autodiagnóstico del módulo: estado del proyecto, del entorno `uv`, del archivo `.env` y del
servidor, con acciones de reparación.

## 12. Sistema

Auditoría del equipo: CPU, GPU, RAM, adaptadores de red e inventario de dependencias
(`dependency_audit()`). Sirve para saber qué falta antes de abrir un Issue.

## 13. Acerca de

Versión de la aplicación (`APP_VERSION`, la única fuente real), autores, enlaces a los tres
upstream y sus licencias.

---

## Atajos y detalles útiles

| Cosa | Detalle |
| --- | --- |
| Refrescar todo | `F5` |
| Abrir el dashboard | *Servidor → Abrir dashboard* (navegador predeterminado) |
| Consolas CMD con el entorno de la suite | *Mantenimiento → Consolas* |
| Accesos a carpetas de trabajo | *Mantenimiento → Carpetas* |
| Búsqueda rápida de archivos | integración opcional con *Everything* (registro de contexto) |

## Buena práctica antes de experimentar

1. **Caché → Respaldos → Crear respaldo**.
2. Truca una sola cosa por vez y observa la caja de registro de la página.
3. Si algo queda raro, **Restaurar** desde la propia página o desde *Caché*.
