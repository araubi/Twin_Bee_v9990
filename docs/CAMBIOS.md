**Español** · [English](CHANGES.en.md) · [日本語](CHANGES.ja.md)

# Twin Bee V9990: cambios y detalles técnicos

## Cómo está montado

### Versión SCC (base: Twin Bee SCC Enhanced, 128 KB → 256 KB, mapper Konami SCC)

| Bancos de 8 KB | Contenido |
| --- | --- |
| 0 | Arranque de la versión SCC, con un salto añadido al cargador de la V9990. |
| 1-3 | Driver de sonido SCC y música. |
| 4 | Cargador y driver V9990, y al final `sndfast` (salida rápida al PSG y al SCC). El driver se copia a RAM a partir de D520h y sus variables van en C000h, zonas que la versión SCC no usa (ella usa C800h-C9FFh, D000h-D2FFh, D506h-D507h y D514h). |
| 5-8 | El juego, con parches pequeños: gancho de interrupción, envíos al TMS9918, registro de los objetos de tierra, límite inferior de la nave (1P y 2P), punto donde se eliminan enemigos y balas al salir por abajo, cargador de la fuente (para la X) y tabla de créditos. |
| 9-31 | Gráficos de la V9990 (tiles, mapas, sprites y paletas), comprimidos. |

### Versión PSG (base: Twin Bee original, 32 KB → 256 KB, mapper Konami)

| Bancos de 8 KB | Contenido |
| --- | --- |
| 0-3 | El juego original con los mismos parches pequeños. El INIT salta a un stub en 4010h que pone el banco 4. |
| 4 | Cargador y driver V9990. El driver se copia a RAM en C800h y sus variables van en C000h. `slotfix` (40D1h) deja puestos los bancos y el gancho H.KEYI. |
| 5-31 | Gráficos de la V9990, todos en RLE (hay sitio de sobra y la carga es más rápida). |

### Driver V9990

- Modo P1, 256x212, dos capas: B = "mapa N - paleta 1" y A = "mapa N - paleta 2". Mapas de 64x64 tiles en un anillo de 64 filas (A en 7C000h, B en 7E000h).
- **Interrupción de línea 191:** escribe la parte alta del scroll del cuadro siguiente.
- **Interrupción vertical:**
  1. Escribe la parte baja del scroll, lo primero, antes de que empiece la imagen (vital en máquinas reales como la Sony HB-F900).
  2. Paso de la música SCC (solo versión SCC).
  3. Mapa y sprites.
  4. Salta al gestor de interrupción del juego.
- Se acusa también la interrupción del TMS9918 para que la BIOS no ejecute su rutina de teclado y reloj.
- **Sprites:** cada sprite del MSX (patrón y color) se traduce a uno o varios sprites de 16 colores, con tablas por contexto (fase y jefe) en `src/sprites.py` (`COMMON` y `SPECIFIC`). Las entradas van en páginas de 256 bytes en el orden en que se envían a la V9990.
- **Pantalla del MSX:** durante la partida muestra la ventana de pausa (fase, récord, puntuaciones y vidas), actualizada unas 7 veces por segundo. Durante la demo se queda en negro.

## Cambios durante las pruebas

### Gráficos y sprites

- Campanas: la negra (la que mata) no tenía dibujo y salía como una amarilla; ahora tiene su dibujo. En la fase 3 las verdes salían con el dibujo de las negras; corregido.
- Objetos que salían blancos: el caramelo, la estrella de la fase 3 y las manos de la fase 4 ya tienen dibujo. El bote usa el de la hoja de sprites.
- Muerte de la nave (comprobada con la ROM original): el MSX alterna la nave toda en blanco con la nave estrellada. Antes, en los cuadros en blanco salía la nave con escudo; ahora sale la silueta blanca de la propia nave (también WinBee).
- Choque de la nave: la salpicadura y la abejita pequeña, las dos blancas en el arte nuevo, se mezclaban. Ahora sale primero la salpicadura y después la abejita (`SPL_HALF` en `driver.asm`).
- Los sprites repintados para una fase concreta (por ejemplo, las campanas rojas de la fase 2) se cogían de la fase 1. Ahora se usa siempre el dibujo de la propia fase.
- La nave ya no desaparece al soltar bombas, al recibir un disparo ni con la sirena (faltaban los dibujos de la nave inclinada).
- Balas enemigas por encima de todo: van en las entradas 25-31 de la tabla de sprites del juego, y el driver las envía las primeras a la V9990, que dibuja delante los primeros sprites. Ya no se esconden tras nubes ni enemigos, ni se pierden por el límite de 16 sprites por línea.
- Créditos: nueva línea **COLOR GUANTXIP**. El juego no tenía la letra X y se ha añadido a la fuente, en las filas 1-7 del carácter como el resto.

### Pantalla y scroll

- **Parpadeos de pantalla completa.** Había dos causas:
  - El corte de la línea 192 se hacía apagando la pantalla (R#8), y ese bit solo se lee al empezar cada cuadro: si la interrupción llegaba tarde se perdía un cuadro entero. Ahora no hay corte: las 20 líneas de abajo son parte del juego (límite de la nave en C300h; enemigos y balas se eliminan desde Y = D4h).
  - La interrupción del TMS9918 hacía que la BIOS ejecutara su rutina, retrasando hasta 1,5 ms la de la V9990. Ahora el driver la anula.
- Al empezar una fase, al salir de la pausa o al cambiar de fase, el mapa se redibuja en la mitad del anillo que no se ve, en 4 cuadros, y se cambia de golpe cuando está terminado.
- Scroll parado (jefes): el desplazamiento fino seguía contando aunque el juego no avanzara y el fondo iba adelante y atrás ("moonwalker"). Ahora se calcula desde el último paso real del scroll. Corregido también un golpe del fondo cada ~4 s con el scroll parado.
- **Pantalla temblando en la HB-F900:** en una versión de pruebas la música se hacía antes que el scroll, y la parte baja del scroll se escribía unos 3 ms después de la interrupción, con la imagen ya empezada. Ahora se escribe a unos 0,3 ms y la música va justo después.
- Logo y menú: el driver copiaba toda la pantalla del MSX en cada cuadro. Ahora copia como mucho 64 caracteres por cuadro y van a la misma velocidad que la versión SCC.

### Jefes

- El mapa cambiaba al de la fase siguiente al aparecer el jefe (en el jefe 5, a un mapa inexistente). Ahora el jefe se pelea sobre el final del mapa de su fase.
- La pantalla de islas de cada jefe está dibujada dos veces en el arte (al final de un mapa y al principio del siguiente), con diferencias y paletas distintas, y al vencer al jefe se veían tiles o colores que cambiaban (reportes de DTensoMSX). Ahora el conversor pone en los dos sitios la misma imagen, con colores que tienen las dos fases, y elige para cada jefe el dibujo que pierde menos colores (faro del jefe 2, rocas marrones del jefe 1).
- Bajo la pantalla de islas se deja la franja de costa del mapa, también en el mapa siguiente (antes se cambiaba por mar y se veía un parpadeo antes del jefe; reporte de Xavi Sorinas).
- Fila de encima de la pantalla del jefe: el conversor añade a cada mapa, tras la última fila, la que hay encima de la pantalla de islas en el mapa siguiente. Así se ve lo mismo durante el jefe y después (ondas dobles del jefe 5, acantilado de arriba a la derecha).
- Los jefes que entran por arriba empiezan con Y = D1h, y al morir el juego aparca sus sprites en Y = D0h; el MSX no los muestra, pero la V9990 tiene 20 líneas más. Ahora los sprites con Y entre D0h y DFh no se dibujan.
- Final del jefe 5: el juego vuelve el scroll de la posición 1760 a la 26, y el fondo bajaba 5 líneas ("bailecito"). Ahora un salto así no mueve el fondo.
- Arte de la fase 4: en "mapa - paleta 2" los acantilados de la última pantalla de islas estaban una fila más arriba que en "paleta 1"; el conversor lo corrige.
- Música tras morir en un jefe: suena la de la fase. Es del juego original (la versión SCC sin GFX9000 hace lo mismo).

### Música SCC

- Canales que se perdían al empezar las músicas (reporte de Xavi Sorinas): el reproductor SCC trabaja con interrupciones habilitadas y sus bancos puestos; si la interrupción de la V9990 llegaba entonces, el driver volvía a poner los bancos del juego. Ahora:
  - el paso de la música se hace al principio de cada cuadro, justo después de escribir el scroll;
  - si la interrupción llega dentro del reproductor, el driver no toca nada;
  - los redibujados se reparten en varios cuadros para no retrasar la música.
  En 30 s de partida la música da 1798 pasos, los mismos que la versión SCC sin GFX9000.
- Sonido en pausa: la versión SCC original hace exactamente las mismas escrituras al PSG y al SCC durante la pausa.

### Rendimiento (versión SCC)

Partida completa en openMSX, en cuadros de lógica por segundo:

| | Antes | Ahora | SCC sin GFX9000 | Original (PSG) |
| --- | --- | --- | --- | --- |
| Fases 1-5 | 25,6-27,0 | 28,9-30,0 | 26,2-27,2 | 29,9-30,7 |
| Jefes 1 y 4 | 20,5-21,3 | 24,7-25,9 | 21,4-21,7 | 30,0 |
| Jefes 2, 3 y 5 | 24,9-26,5 | 28,8-29,5 | 23,8-25,6 | 30,0 |
| **Total** | **25,0** | **28,6** | **25,3** | **30,0** |

- **Reproductor SCC:** de 3,1 ms a 2,0 ms por paso. La salida al PSG y al SCC está reescrita (`src/sndfast.asm`): escribe directamente en los puertos del PSG en vez de llamar a la BIOS (WRTPSG) y abre la ventana del SCC una sola vez. Escribe lo mismo que antes, comprobado registro a registro.
- **Sprites:** de 5,3 ms a 3,9 ms por cuadro de lógica: las entradas vacías se saltan antes y los datos van ya en el orden de envío.
- La versión PSG va a 30,0, igual que el original.

### Compresión

- Los gráficos van en RLE, que se descomprime rápido, salvo los bloques que hace falta comprimir más (LZ) para que quepan en la versión SCC (12 de 42). La carga inicial tarda unos 2,2 s.
