# Preguntas abiertas

> Al recibir una respuesta: anotarla aquí con la hora y quién la dio, y actualizar `PREPARACION.md`.

## 1. Mentores de Betsson: URGENTES (hacerlas ya, por orden)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿La entrega es hoy a las 20:00? ¿Qué se entrega exactamente y cómo (enlace al repo, formulario)? | |
| 2 | ¿Pueden activar Perú o Malta más adelante (aunque sea en la demo)? ¿Tienen capturas de un juego de Pragmatic en PEN y en inglés? | |
| 2b | La extensibilidad a otros proveedores, ¿cómo la evaluaréis? ¿Añadiendo un proveedor en directo, revisando el código o con un segundo proveedor funcionando? ¿Alguno recomendado? | |
| 3 | ¿Cuándo llegan las cuentas de prueba? ¿Cuántas, una por mercado? ¿Cuál es para el escenario 2? | |
| 4 | Escenario 2: ¿vale provocar el saldo insuficiente subiendo la apuesta por encima del saldo, o debe ser una cuenta a cero? | |
| 5 | Los runners de GitHub tienen IP de EE. UU.: ¿aceptáis un runner propio en España (portátil u Oracle en Madrid)? ¿Hay lista blanca para el WAF? | |
| 6 | ¿Nos pasáis el documento de "vías de investigación" (el del Drive)? | |

## 2. Mentores de Betsson: técnicas

| # | Pregunta | Respuesta |
|---|---|---|
| 7 | ¿Algún juego de Pragmatic recomendado, o alguno que evitar? | |
| 8 | ¿Podemos usar las API de Betsson (monedero o saldo) y la red de Pragmatic como **confirmación**, siempre que la prueba principal sea la pantalla? | |
| 9 | ¿Con cuánto retraso se actualiza el saldo de Betsson tras una tirada? ¿Se ve durante el juego? | |
| 10 | ¿Qué tolerancia de saldo aceptáis (redondeos, decimales)? | |
| 11 | ¿Quién recarga las cuentas si se quedan sin saldo de tanto probar? | |
| 12 | ¿Hay algún formato de informe preferido? | |
| 13 | ¿Hay límite de ejecuciones o de ritmo para no disparar el antibot? | |

| 18b | El login automatizado (Chrome visible, ritmo humano) recibe "Actualiza la página y vuelve a intentarlo en breve…"; el login manual con la misma cuenta funciona. ¿Las cuentas de prueba tienen lista blanca para automatización? ¿Hay que entrar desde una IP, red o navegador concretos? | |
| 18c | En betsson.es aparece el diálogo de límites de sesión de la DGOJ (tiempo y límite de pérdidas) antes de jugar, y mientras dura la sesión no se puede crear otra. ¿Pueden ir las cuentas de prueba sin límite? ¿Qué valores recomendáis? ¿Hay forma de cerrar la sesión al terminar cada ejecución? | |

## 3. Organización

| # | Pregunta | Respuesta |
|---|---|---|
| 14 | ¿Hay API key o créditos de algún modelo de IA? ¿Se puede usar la IA generativa de OCI? | |
| 15 | ¿Cuánto tarda en activarse la cuenta de Oracle? | |
| 16 | ¿La red del recinto tiene proxy o restricciones con las VPN? | |
| 17 | ¿El repo tiene que ser público? | |

## 4. Equipo

| # | Pregunta | Respuesta |
|---|---|---|
| 18 | Perfiles (frontend, backend, QA o automatización, IA) → asignar las áreas A–D | |
| 19 | ¿Quién pide la cuenta de Oracle? (Mayor de edad, `@uma.es`, no haberla pedido antes) | |
| 20 | ¿Qué sistema operativo tiene cada uno y quién deja su portátil como runner de CI? | |

## Respondidas
| Pregunta | Respuesta | Fuente |
|---|---|---|
| ¿Tecnología obligatoria? | Libre | PDF |
| ¿Mercados? | betsson.com (EN/EUR) y betsson.pe (ES/PEN) | PDF |
| ¿Cuentas o demo? | Cuentas de prueba con saldo, Real Play | PDF |
| ¿Entregables y criterios? | Ver `PREPARACION.md` §1 | PDF |
| ¿Se permite la VPN? | Sí, era necesaria (recomendaban Proton)… | Organización |
| …¿y ahora? | **Ya no hace falta**: crean cuentas de prueba españolas | Mentores, 15-oct |
| ¿Qué mercados? | Solo betsson.es en real (ya no Perú ni Malta), pero **adaptable a todos los mercados** (p. ej., que reconozca los soles) | Mentores, 15-oct |
| ¿Qué se valora además? | **Mucho que la solución se pueda extender a otros proveedores** | Mentores, 15-oct |
| ¿Infraestructura? | Oracle, bajo petición (`@uma.es`) | Correo de la organización, 13-oct |
