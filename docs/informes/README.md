# Informes de validación (betsson.es, Big Bass Splash · Pragmatic Play)

Informes reales generados por el comprobador, con sus capturas. Se abren en el navegador
(`report.html`); los datos en bruto están en cada `results.json`.

| Informe | Resultado | Qué demuestra |
|---|---|---|
| [`pass-20261015/report.html`](pass-20261015/report.html) | **S1 PASS 11/11 · S2 PASS 7/7** | Los dos escenarios en real: tirada completada con la regla del saldo cuadrando en el juego y en Betsson, y saldo insuficiente con el mensaje en español y los saldos sin cambios. Detalle en [`pass-20261015/README.md`](pass-20261015/README.md). |
| [`fallo-provocado-20261015/report.html`](fallo-provocado-20261015/report.html) | **S1 FAIL** (provocado) | Requisito del mentor: rompemos a propósito la regla del saldo y el test lo detecta; después se revierte y vuelve a verde. Detalle en [`fallo-provocado-20261015/README.md`](fallo-provocado-20261015/README.md). |

## Cómo leerlos
- **Portada** (`report.html` de cada carpeta): una tarjeta por escenario con su resultado y sus avisos, y una matriz comprobación × escenario. Pasa el ratón por cada resultado para ver el motivo.
- **Informe de escenario** (`es/S1/report.html`, `es/S2/report.html`): galería «Lo que vio el comprobador» (cada lectura con su captura, el texto OCR, el valor, la confianza y si se vio la moneda) y la tabla de comprobaciones con motivo, esperado, observado y evidencias.
- **Resultados**: `PASS` = verificado en pantalla. `FAIL` = error real de integración. `INCONCLUSIVE` = no se pudo verificar con seguridad (cuenta como FAIL, nunca como PASS). `PROVIDER_UI_CHANGED` = el perfil del proveedor ya no reconoce el juego (aviso de mantenimiento, no fallo de Betsson).

## Privacidad
- Las capturas son de cuentas de **prueba**. El nombre del titular, que aparece en el desplegable de saldo de Betsson, está **tapado** en estas copias.
- No hay trazas de red, HAR ni vídeo (con la sesión iniciada, la web descarga el perfil del cliente). Tampoco credenciales ni tokens.
- El login fue **asistido por una persona** (autorizado por los mentores) y el informe lo indica. El resto de la ejecución es automática.
