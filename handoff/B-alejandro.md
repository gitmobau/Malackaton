# Traspaso del área B (Alejandro): ojos sobre el juego y proveedores

## Estado actualizado (15-oct, tarde, portátil de Alejandro). Manda sobre el resto del documento
- Fusionado `main` con los contratos de C (`betsson/core`). Se borraron las copias provisionales: B importa todo de `core`.
- `ProfileSpec` (en `profiles/base.py`) cumple `core.ProviderProfile`. `profiles/registry.py` tiene `Registry`/`REGISTRY`, que cumple `core.ProviderRegistry`: `resolve()` nunca lanza (proveedor desconocido → `generic-vision`) y `ensure_recognized()` lanza `ProviderUIChanged`. GameEyes ya no lo hace.
- `game/factory.py`: `make_game_eyes(handle, profile, market)` cumple `core.GameEyesFactory` y usa el `GameHandle` de A (`capture()` RGB y `canvas`).
- `game/money_reader.py`: **único** punto que usa `parse_money` y `detect_currency` de A. Si `betsson.market` no está, todo sale inconclusive y se registra un aviso.
- Nuevo `set_bet("min" | "above_balance")` con plantillas −/+ (comprueba que la apuesta se mueve en el sentido pedido). `read_win()` devuelve 0 si el perfil declara `win_hidden_when_zero` y no se ve ninguna etiqueta de ganancia.
- **S1 completo probado en vivo en la demo**: apuesta mínima 0,10 €; 100.000,00 − 0,10 + 0 = 99.999,90, leído en pantalla.
- Revisión de `python-reviewer`: 5 HIGH corregidos y varios MEDIUM. Pendientes: esperas sin ritmo en los bucles de captura (solo las limita el coste de la captura), `resolve()` si un perfil no carga, y desplazar el canvas a la vista antes de pulsar.
- Pendiente de lo de siempre: S2 con la cuenta sin saldo (texto real de saldo insuficiente) y prueba en Real Play dentro de betsson.es.
- Tests: `pytest betsson` da 57 en verde y 1 omitido; la suite completa del repo, sin `real`, también en verde.

Rama `feat/B-vision`. Punto de traspaso del 15-oct, hacia las 13:00, al migrar del portátil de Maiki al de Alejandro.
**No está fusionado con `main`.** La rama sale de `7ce859c`, anterior al PR #1. Ver "Siguientes pasos", punto 1.

## Hecho y probado (40 tests en verde y 1 omitido: `pytest betsson`)
- `betsson/profiles/base.py`: `ProviderProfile` (pydantic, inmutable) con `Rect` en fracciones, `IntroScreen` y `SpinEndSignal`. Es una **copia provisional** del contrato acordado con C (ver Decisiones).
- `betsson/profiles/registry.py`: descubre cada carpeta `betsson/profiles/<x>/profile.py` que exponga `PROFILE`. `resolve(url, frame)` devuelve el perfil con mayor `detect()` (umbral 0,5) y, si ninguno llega, `generic-vision`.
- `betsson/profiles/pragmatic/`: perfil y `assets/` (`spin.png` del botón en juego e `intro_continue.png` del botón de la presentación).
- `betsson/profiles/generic_vision/`: respaldo para proveedores desconocidos (solo etiquetas habituales, pista y tecla Espacio).
- `betsson/vision/`:
  - `ocr.py`: RapidOCR v3, compatible con la v1, con caché por contenido del frame.
  - `anchors.py`: importe por **etiqueta visible** (en la misma caja, a la derecha o debajo; nunca toma como valor otra etiqueta; la zona del perfil solo desempata).
  - `template.py`: plantilla multiescala sobre bordes engrosados.
  - `diff.py`: proporción de píxeles que cambian.
- `betsson/game/`:
  - `eyes.py` (`GameEyes`): `read_balance`, `read_bet`, `read_win`, `read_amount`, `spin`, `wait_spin_end`, `read_message`, `dismiss_intro`, `ensure_recognized` (lanza `ProviderUIChanged`), `locate_spin` y `screenshot(name)`.
  - `sources.py`: `PlaywrightCanvasSource` (canvas real) y `FileFrameSource` (tests).
  - `contracts.py`: `Money`, `Reading`, `SpinEnd`, `Message` y `ProviderUIChanged`. Copia provisional de `core`.
  - `capture_demo.py`: captura de la demo pública.
- Tests:
  - `betsson/profiles/tests/test_contract.py`: **test de contrato** para cualquier perfil. Incluye que ningún nombre de proveedor aparezca fuera de su carpeta.
  - `betsson/vision/tests/test_engine.py`: anclas, diff y plantilla con datos sintéticos.
  - `betsson/profiles/pragmatic/tests/test_fixtures.py`: **OCR real sobre las capturas**. Lee CRÉDITO 100.000,00 € y APUESTA 2,00 € en 4 capturas, encuentra el botón de girar dentro de su pista y devuelve "inconclusive" en la pantalla de carga.
- Probado en vivo con la demo: `dismiss_intro()` cierra las dos pantallas de inicio (carga y presentación) y la tecla Espacio gira.

## En qué punto exacto quedó
- Calibración del fin de tirada en la demo. Las burbujas animan **siempre**: en reposo la diferencia entre frames está entre 0,03 y 0,07 y girando entre 0,17 y 0,45, con unos 1,5–2 s por captura de Playwright. Ya está aplicado al perfil: `diff_threshold=0.12` y `stable_frames=2`.
- **Falta comprobar en vivo** `GameEyes.spin()` y `wait_spin_end()` con esos umbrales. Solo lo hizo un script de sondeo, que no está en el repo.
- `capture_demo.py` se quedó sin tiempo (timeout de 500 s), porque usa su propio umbral de 0,004 (`_STABLE_THRESHOLD`) y con las burbujas nunca ve el juego quieto. **Arreglo pendiente**: que use `profile.spin_end.diff_threshold`. Por eso no hay `manifest.json`.

## Siguientes pasos, en orden
1. `git fetch origin && git merge origin/main` (PR #1: esqueleto, `pytest.ini` y `conftest.py`). Posible conflicto add/add en `betsson/__init__.py`: el nuestro está vacío, así que quedarse con el de `main`. Registrar el marcador `unit` si `pytest.ini` no lo tiene.
2. Cuando C suba `betsson/core/`: cambiar `betsson/game/contracts.py` y `Rect`/`IntroScreen`/`SpinEndSignal`/`AmountField` de `base.py` por imports de `core`, y borrar las copias.
3. Cuando A suba `parse_money(texto, mercado)`: pasarlo a `GameEyes(parse_money=lambda t: parse_money(t, market))` y quitar `parse_eur_es` del test.
4. Arreglar el umbral de `capture_demo.py` y capturar una **ganancia** (WIN o GANANCIA visible) para probar `read_win()`. En estas capturas no salió ninguna ganancia.
5. Test de `spin()` y `wait_spin_end()` con `FileFrameSource` (secuencia reposo → `10_girando.png` → `11_fin_tras_girar.png` repetida).
6. **Escenario 2 con la cuenta de prueba sin saldo** (login de A): capturar el mensaje real de saldo insuficiente y ajustar `insufficient_texts` del perfil, que ahora son textos supuestos.
7. Con la cuenta con saldo: validar el perfil dentro de betsson.es en Real Play (moneda, pantallas de inicio y apuesta mínima).
8. Test de resistencia: capturas desplazadas, reescaladas y recoloreadas.
9. Revisión con el agente `python-reviewer` y PR a `main`.

## Decisiones tomadas
- La interfaz `ProviderProfile` se propuso a C y C la aceptó:
  - `Money` en `core/money.py`; `parse_money` es de A.
  - `Reading`, `SpinEnd` y `Message` como modelos pydantic inmutables en `core`.
  - `ProviderRegistry` como Protocol en `core` e implementación en B.
  - `PROVIDER_UI_CHANGED` y `ProviderUIChanged(reason)` en `core`.
  - `GameEyes` con los métodos de arriba más `screenshot(name)`.
- Si no hay perfil reconocido, `resolve()` devuelve `generic-vision`, y `GameEyes.ensure_recognized()` lanza `ProviderUIChanged` si ni siquiera ve las etiquetas de saldo y apuesta. **Pendiente de confirmar con C**: C pidió que `resolve()` lance directamente la excepción.
- Lo dudoso devuelve `money=None` con `reason="inconclusive: …"`.
- La plantilla de girar está recortada del juego y no de la intro: la de la intro solo puntuaba 0,50 por el cambio de fondo.
- Python 3.14: `rapidocr-onnxruntime` no se instala. Se usa `rapidocr>=3` con `onnxruntime` (ya está en `requirements.txt` de `main`). Ojo: la CI de PR corre con Python 3.12.
- Hay dos cuentas de prueba: una con saldo (S1) y otra sin saldo (S2). Sus credenciales nunca entran en el código de B: el login es de A y van en `.env` y en GitHub Secrets.

## Problemas abiertos
- Hora de actualización del CRÉDITO: en `10_girando.png` se ve 99.998,00 € y en `11_fin_tras_girar.png` 99.996,00 €, pero son de la 2.ª tirada del sondeo. Hay que confirmar cuándo descuenta Pragmatic la apuesta en pantalla (¿al empezar?) para la regla del saldo de C.
- `read_win()` no está probado con capturas reales (no hubo ninguna ganancia).
- El botón de girar cambia a STOP (cuadrado rojo) durante la tirada. Es una señal visible extra de que la tirada empezó y aún no se usa.

## Comandos para reproducir
```powershell
# venv compartido (o el de tu portátil con requirements.txt)
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\DevCache\ms-playwright"
python -m pytest betsson -q                                   # todos los tests de B (unos 35 s, el OCR carga el modelo)
python -m pytest betsson/profiles/tests/test_contract.py -q   # solo el contrato
python -m betsson.game.capture_demo --profile pragmatic --spins 6 --channel chrome   # capturas (ventana visible); arreglar antes el umbral
```

## De dónde salen las capturas de `fixtures/pragmatic/`
Demo **pública** de Pragmatic Play, Big Bass Splash (`vs10txbigbass`), con `lang=es` y `cur=EUR`, sin registro ni cuenta. La URL está en `PROFILE.demo_url`. Se capturaron el 15-oct desde España, a 1366×768 y DPR 1, solo el canvas.
No contienen datos de ninguna cuenta: el saldo es el ficticio de la demo (100.000 €).
- `00_carga`, `01_inicio`: pantalla de carga de Reel Kingdom ("Powered by Pragmatic Play").
- `02_reposo`, `04_fin_1`, `06_fin_2`, `08_fin_3`: juego en reposo (CRÉDITO 100.000,00 €, APUESTA 2,00 €). Las "fin_N" son reposo, porque esa ejecución no llegó a girar.
- `10_girando`: tirada en curso ("¡BUENA SUERTE!", botón en STOP, CRÉDITO 99.998,00 €).
- `11_fin_tras_girar`: tras la tirada ("¡TIRE PARA GANAR!", CRÉDITO 99.996,00 €).
- La presentación con el botón de flechas solo está recortada en `betsson/profiles/pragmatic/assets/intro_continue.png`.
