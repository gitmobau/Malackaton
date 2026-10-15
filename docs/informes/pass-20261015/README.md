# Informe en PASS · 15-oct-2026

Portada: [`report.html`](report.html) · S1: [`es/S1/report.html`](es/S1/report.html) · S2: [`es/S2/report.html`](es/S2/report.html)

| Escenario | Run original | Resultado |
|---|---|---|
| S1, tirada completada | `demo-20261015-1746` | **PASS 11/11** |
| S2, saldo insuficiente | `demo-20261015-1811` | **PASS 7/7** |

Mercado `es` (betsson.es, EUR, español), juego Big Bass Splash (perfil `pragmatic` detectado por imagen).

## S1
- Login asistido por una persona y juego abierto en Real Play (Betsson pidió los límites de sesión de la DGOJ).
- Apuesta visible 0,10 €. La tirada empieza y termina (señal visual) y la ganancia es 0.
- Regla del saldo: `después = antes − apuesta + ganancia`. Cuadra en el juego (CRÉDITO) y en Betsson.
- Moneda vista en pantalla: EUR, la del mercado.

## S2
- Cuenta sin saldo (0,00 €). Al pulsar girar aparece la ventana «MENSAJE»: «Fondos insuficientes para realizar esta apuesta…» (en español).
- Rodillos quietos y saldos del juego y de Betsson sin cambios (0,00 € → 0,00 €).

## Avisos que verás y qué significan
- **Login asistido por una persona**: transparencia; lo demás es automático.
- **Ojos del juego: …**: notas de cómo se localizaron los controles. Por ejemplo, «se usó la pista de zona» cuando la plantilla del botón no se encontró. No cambian el veredicto.
- **«El juego del proveedor ha cambiado desde la última ejecución» en S2**: es un **falso aviso** conocido. La huella de S2 se comparó con la de S1, que tiene otro saldo en la franja de controles (99,70 € frente a 0,00 €). Se corrige guardando la huella por escenario. No cambia el veredicto.

## Privacidad
El nombre del titular de la cuenta de prueba (desplegable de saldo de Betsson) está tapado en `es/S1/betsson_balance.png` y `es/S2/betsson_balance.png`. Imágenes optimizadas a 256 colores para el repo.
