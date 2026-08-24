# Plan de Pruebas Manuales - Puntos Osaka (HU-008)

Este documento detalla los pasos para verificar **manualmente** en el entorno de pruebas de Odoo cada una de las correcciones implementadas (R1 a R7).

**Módulos:** `pgm_osaka_loyalty` (v19.0.2.2.0) · `pgm_extended_fields_osaka`  
**Quién ejecuta:** QA / tú en la BD de test  
**Evidencia:** pantallazo por cada validación (form y PDF cuando aplique)

### Criterio de negocio (confirmado por Ana — flete / mixtos)

Los puntos Osaka **solo** se acumulan por productos que estén en las **reglas condicionales** del programa (ej. categorías Pastillas / Pastillas de freno / Pastillas cerámica).  
El **envío (flete) no está en esas reglas**, por lo tanto:

| Caso | Resultado esperado |
|------|--------------------|
| Solo flete | **0 puntos** |
| Mixto: producto **de la regla** + flete | Puntos **solo** por el producto de la regla; **0 por el flete** |
| Mixto: producto **fuera** de las reglas + flete | **0 puntos** (si no hay otra regla que aplique) |
| SO con productos + factura **solo** del envío (parcial) | **0 puntos** (no prorratear puntos del producto al cobrar el flete) |

> **Código (v19.0.2.2.0):** la emisión usa ratio `productos_en_factura / productos_en_SO` (excluye `is_delivery`). Facturar solo flete → ratio 0.

---

## Preparación del Entorno

1. Asegúrate de que los módulos `pgm_osaka_loyalty` (v19.0.2.2.0) y `pgm_extended_fields_osaka` estén **actualizados** en tu base de datos de test.
2. Utiliza un cliente de prueba inscrito en **Puntos Osaka** y, si aplica, **Amigos Osaka** (ej. CORREA MEJIA u otro limpio).
3. Anota los saldos iniciales de ambas tarjetas **antes** de empezar:

| Programa        | Saldo inicial | Fecha/hora |
|-----------------|---------------|------------|
| Puntos Osaka    |               |            |
| Amigos Osaka    |               |            |

4. Para cada caso marca al final: **OK / FAIL / BLOQUEADO** + notas.

---

## R1 y R5: Layout Visual del Resumen (palabras cortadas y ubicación)

**Objetivo:** Validar que el resumen se ve completo, no recorta palabras, y se posiciona debajo del bloque de totales.

**Pasos:**

1. Crea un Pedido de Venta (SO) para el cliente de prueba con al menos un producto.
2. Confirma el pedido y crea la Factura.
3. En la vista formulario de la factura, desliza hacia la sección de totales.
4. **Validación Visual (Formulario):**
   - El bloque **"Resumen de Lealtad Osaka"** debe aparecer **debajo** de los Subtotales/Totales y no apretado a la derecha de la columna de impuestos.
   - Las palabras ("Saldo Anterior", "Puntos Ganados", "Nuevo Saldo", "A vencer este mes") **no** deben estar cortadas u ocultas.
   - Los labels nativos de Odoo (Subtotal, Total, etc.) tampoco deben verse cortados ("Subtot…", "Tot…").
5. Publica/Confirma la factura (`Publicar` / `action_post`).
6. Imprime la Factura en PDF.
7. **Validación Visual (PDF):**
   - El resumen debe renderizarse **debajo** de la sección "Total" en una fila limpia.
   - La tabla no debe desbordarse de la página ni clipar texto.

**Resultado esperado:** Contenido del resumen intacto (lo que el cliente calificó “10/10”) + layout sin cortes.

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| Form: resumen debajo de totales | | |
| Form: labels completos | | |
| PDF: resumen bajo Total | | |
| PDF: sin desborde | | |

> **Tip QA:** Odoo suele tener otros módulos que inyectan contenido en `account.move` (localización, EDI, retenciones). Verifica que el cuadro Osaka no colisione ni rompa esos bloques.

---

## R2: Campo "A vencer este mes" de solo lectura

**Objetivo:** Confirmar que nadie puede editar manualmente los puntos próximos a vencer.

**Pasos:**

1. Navega a las Tarjetas de Lealtad (ruta típica: **Ventas → Puntos Osaka / Tarjetas de lealtad**, o el menú de Fidelidad/Loyalty de tu instancia).
2. Abre la tarjeta de tu cliente de prueba (programa Osaka).
3. Entra en modo edición (o intenta modificar campos).
4. Intenta alterar el valor del campo **"A vencer este mes"**.
5. **Validación:** El campo debe estar en gris / solo lectura y **no** permitir ingreso de texto/números.

**Resultado esperado:** Solo el sistema actualiza ese valor (sync/FIFO al facturar o por cron).

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| Campo no editable | | |

---

## R3: Puntos al facturar flete (solo envío vs mixto)

**Objetivo (criterio Ana):** el flete **nunca** genera puntos. Solo generan puntos los productos clasificados en las reglas del programa (ej. pastillas).

Antes de probar: abre el programa **Puntos Osaka** → reglas condicionales y anota qué categorías/productos sí dan puntos. Usa un producto de esas categorías en R3-B1 y uno que **no** esté en las reglas en R3-B2.

### Prueba A: Solo envío → 0 puntos

Incluye dos variantes:
- SO **solo** flete, o
- SO con productos + flete pero factura **solo** la línea de envío (caso INV/2026/00108 / S00603).

1. Anota saldo actual Puntos + Amigos.
2. Crea la SO según la variante.
3. Confirma, crea la Factura **solo del envío** (si aplica) y publícala.
4. **Validación:** 0 puntos emitidos; "Puntos Ganados" = 0.

| Check | OK/FAIL | Saldo antes | Saldo después | Evidencia |
|-------|---------|-------------|---------------|-----------|
| 0 puntos Puntos Osaka | | | | |
| 0 puntos Amigos Osaka | | | | |

**Si falla:** anota si la línea tiene `is_delivery` y si la SO tiene `coupon_point_ids` con puntos > 0.

### Prueba B1: Mixto — producto **de la regla** + flete

1. Crea SO con un producto que **sí** está en las reglas (ej. pastillas / categoría configurada) **y** una línea de envío.
2. Anota: precio producto, precio flete, puntos que **deberían** salir solo por el producto (según la regla, ej. 1 punto por unidad pagada).
3. Confirma, factura y publica.
4. **Validación:**
   - Los puntos ganados deben corresponder **solo** al producto de la regla.
   - El flete **no** debe aumentar los puntos.
   - **FAIL** si el flete “infló” el awarded respecto a lo que da solo el producto.

| Dato | Valor |
|------|-------|
| Producto (categoría / SKU) | |
| Precio producto | |
| Precio flete | |
| Puntos esperados (solo producto) | |
| Puntos ganados reales | |
| ¿El flete infló los puntos? (Sí = FAIL) | |

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| Puntos solo por producto de regla | | |
| Flete no aporta puntos | | |

### Prueba B2: Mixto — producto **fuera** de las reglas + flete → 0 puntos

1. Crea SO con un producto que **no** aparece en las reglas condicionales del programa **y** una línea de envío.
2. Confirma, factura y publica.
3. **Validación:** **0 puntos** en Puntos Osaka / Amigos Osaka (ni por el producto ni por el flete).

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| 0 puntos (producto fuera de regla + flete) | | |

---

## R4: Resumen "Snapshot" (foto estática)

**Objetivo:** Validar que, una vez confirmada la factura, el cuadro de puntos queda congelado y no cambia con movimientos posteriores.

**Pasos:**

1. Toma una factura **confirmada** reciente (ideal: la mixta de R3-B1 o la de R1).
2. Apunta los valores del resumen Osaka:

| Campo | Valor al validar |
|-------|------------------|
| Saldo Anterior | |
| Puntos Ganados | |
| Puntos Utilizados | |
| Nuevo Saldo | |
| A vencer este mes | |

3. Crea y publica una **nueva factura** para el mismo cliente (que sume puntos al saldo global de la tarjeta).
4. Regresa y visualiza la **primera** factura (form y, si puedes, PDF).
5. **Validación:** El cuadro de la primera factura debe mantenerse **igual** a la tabla del paso 2 (no “salta” al saldo live nuevo).
6. *(Opcional)* Cancela la primera factura. El resumen de esa factura cancelada debe **seguir** conservando la foto del momento en que se validó.

> **Nota:** Facturas **antiguas** publicadas **antes** del update del módulo pueden no tener snapshot (siguen “live”). Anótalas como **legado**, no como FAIL del fix.

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| Foto intacta tras nueva factura | | |
| (Opcional) Foto intacta tras cancelar | | |

---

## R6: Descripción "Facturación" siempre fija (re-confirmaciones)

**Objetivo:** Al anular y re-confirmar una factura, el historial nuevo dice **"Facturación …"** y no "Reactivación por re-confirmación".

**Pasos:**

1. Utiliza una factura confirmada con puntos Osaka (ej. la segunda de R4).
2. Cancela la factura (debe generar línea de reversión negativa en la tarjeta).
3. Pasa la factura a **Borrador** (si el flujo de tu instancia lo permite tras cancelar).
4. Vuelve a **Publicar/Confirmar** la factura.
5. Accede a la Tarjeta de Lealtad → pestaña **Líneas del historial**.
6. **Validación:** La **nueva** línea de otorgamiento debe decir **"Facturación [Nombre de la Factura]"**.  
   **No** debe aparecer "Reactivación por re-confirmación" en esa emisión nueva.

> Líneas **viejas** que ya digan "Reactivación…" pueden existir: son legado, no FAIL.

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| Nueva emisión = Facturación INV/... | | |
| Sin texto Reactivación en la nueva línea | | |

---

## R7: Ocultar "Validez de puntos" y saldo real

**Objetivo:** Confirmar que se retiró el filtro visual confuso (3 días / 3 meses / etc.) y que el saldo mostrado es el contable real.

**Pasos:**

1. Abre el formulario de la Tarjeta de Lealtad (programa Osaka).
2. **Validación 1:** El desplegable **"Validez de puntos"** (ej. "Solo últimos 3 días") **ya no** debe verse en el formulario.
3. **Validación 2:** El saldo mostrado (Balance / Puntos) debe coincidir con la matemática del historial:  
   `Emitido − Utilizado − Vencidos` (aprox. suma de columnas del historial).
4. *(Recomendado)* Abre el **programa** Puntos Osaka / Amigos Osaka y verifica el campo **"Validez de Puntos (Meses)"** = **6** (caducidad real).
5. *(Opcional)* En Ajustes → Ventas, revisa los días de gracia de vencimiento por factura impaga (`dias_vencimiento_factura`).

| Check | OK/FAIL | Evidencia |
|-------|---------|-----------|
| "Validez de puntos" oculta en tarjeta | | |
| Saldo = issued − used − vencidos | | |
| Programa: validez meses = 6 | | |

---

## Orden sugerido (1 sesión)

1. Preparación (update + saldos iniciales)  
2. **R2** + **R7** (rápido UI tarjeta/programa)  
3. **R1 + R5** (factura con producto de regla: form + PDF)  
4. **R3-A** solo flete → **R3-B1** mixto con pastilla/regla → **R3-B2** mixto fuera de regla  
5. **R4** snapshot (+ opcional cancel)  
6. **R6** cancel → borrador → re-publicar  

---

## Matriz de cierre

| ID | Caso | Resultado | Fecha | Tester | Notas / link evidencia |
|----|------|-----------|-------|--------|-------------------------|
| R1+R5 | Layout form + PDF | | | | |
| R2 | A vencer readonly | | | | |
| R3-A | Solo flete = 0 pts | | | | |
| R3-B1 | Mixto: producto de regla + flete (pts solo producto) | | | | |
| R3-B2 | Mixto: producto fuera de regla + flete = 0 pts | | | | |
| R4 | Snapshot | | | | |
| R6 | Descripción Facturación | | | | |
| R7 | Ocultar validez + saldo real | | | | |

**Criterio para devolver al cliente:** R1–R2, R3-A, R3-B1, R3-B2, R4, R5, R6, R7 en **OK**.
