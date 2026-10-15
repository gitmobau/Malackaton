# S2 en real: saldo insuficiente en Big Bass Splash (betsson.es, es-ES)

Capturado el 15-oct a las 16:31 con la cuenta de prueba **sin saldo**: login asistido por una persona y sesión reutilizada por CDP. Sin traza, sin HAR y sin vídeo. Las capturas no muestran datos de la cuenta.

| Archivo | Qué es |
|---|---|
| `00_betsson_dgoj_sin_saldo.png` | Diálogo de límites de sesión de la DGOJ (web de Betsson) con saldo 0. **No trae el límite de pérdidas** y añade un aviso. |
| `01_principal_credito_0.png` | Pantalla principal del juego antes del intento: CRÉDITO 0,00 €, APUESTA 2,00 €, "¡HAGA SU APUESTA!". |
| `02_mensaje_fondos_insuficientes.png` | Tras **un** intento de tirada (tecla Espacio): ventana del juego con el mensaje. Los rodillos no se mueven y el crédito sigue en 0,00 €. |

## Textos exactos

- **Juego (canvas)**, ventana "MENSAJE":
  > Fondos insuficientes para realizar esta apuesta. Haga un depósito en su cuenta o reduzca el nivel de la apuesta.

  Botón: **ACEPTAR**, y una X para cerrar.
- **Web de Betsson**, aviso dentro del diálogo de la DGOJ, antes de abrir el juego:
  > No dispones de saldo, pero puedes crear la sesión y jugar tiradas gratuitas en caso de tenerlas disponibles.
- Etiquetas de la pantalla principal: **CRÉDITO**, **APUESTA**, "¡HAGA SU APUESTA!", "TIR. AUTO.", "COMPRE TIRADAS GRATIS 200 €".

## Saldos

- Betsson, antes del intento: **0,00 EUR**, leído del botón de saldo de la cabecera.
- Betsson, después: **0,00 EUR**, leído del total del resumen "Saldo ▾" en la página del juego.
- Juego: CRÉDITO **0,00 €** antes y después.

## Notas para el perfil

- La pantalla de inicio ("¡SALGA A PESCAR…!", con "NO VOLVER A MOSTRAR") se cierra con **Espacio**. Un clic en el canvas durante la carga no la cerró.
- La apuesta por defecto es **2,00 €**, no la mínima. Para el S1, bajarla con "−" antes de girar.
