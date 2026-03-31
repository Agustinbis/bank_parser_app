# 📝 Guía: Cómo Agregar un Nuevo Parser de Banco

## 🎯 Resumen Rápido

Para agregar un nuevo banco **sin reconstruir el contenedor Docker**:

1. Crea el archivo `parsers/nuevo_banco_parser.py`
2. (Opcional) Actualiza `parsers/bank_profiles.py` si usas perfiles
3. Refresca la página web - ¡el nuevo banco aparecerá automáticamente!

---

## 📂 Carpeta Expuesta

La carpeta **`./parsers`** está montada como volumen en el contenedor:

```yaml
volumes:
  - ./parsers:/app/parsers:ro
```

Esto significa que cualquier cambio en `./parsers/` se refleja **inmediatamente** en el contenedor sin necesidad de rebuild.

---

## ✍️ Pasos Detallados

### 1️⃣ Crear el Archivo del Parser

**Nombre del archivo:** `parsers/NOMBRE_BANCO_parser.py`

**Ejemplo:** `parsers/santander_parser.py`

```python
# parsers/santander_parser.py

import pandas as pd
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parsea extractos del Banco Santander.
    
    Args:
        pdf_path: Ruta al archivo PDF
        
    Returns:
        DataFrame con columnas: Fecha, Descripción, Débito, Crédito, Saldo
    """
    
    # Tu lógica de parsing aquí
    movimientos = []
    
    with open_pdf(pdf_path) as pdf:
        for page in pdf.pages:
            # Extraer datos de cada página
            # ...
            pass
    
    df = pd.DataFrame(movimientos)
    
    # Calcular saldos y verificar
    df = calcular_saldos(df, es_layout_invertido=False)
    reportar_inconsistencias(df)
    
    return df
```

**⚠️ IMPORTANTE:** El archivo **debe** terminar en `_parser.py` y contener una función `parse(pdf_path: str)`.

---

### 2️⃣ (Opcional) Actualizar Perfiles

Si tu parser usa `bank_profiles.py`, añade la configuración:

```python
# parsers/bank_profiles.py

BANK_PROFILES = {
    # ... bancos existentes ...
    
    "SANTANDER": {
        "layout": {
            "date_x":    (0, 60),
            "desc_x":    (60, 280),
            "debit_x":   (360, 440),
            "credit_x":  (440, 520),
            "balance_x": (520, 680)
        },
        "flags": {
            "es_layout_invertido": False,
            "usa_referencia": False,
            "omite_totales": False,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "TOTAL", "SALDO DISPONIBLE"
        ],
        "buscar_desde_pagina": 1
    }
}
```

---

### 3️⃣ Verificar la Detección Automática

El sistema detecta automáticamente todos los archivos `*_parser.py` gracias a este código en `parsers/__init__.py`:

```python
for finder, name, ispkg in pkgutil.iter_modules([Path(__file__).parent]):
    if name.endswith("_parser"):
        key = name.replace("_parser", "")
        module = importlib.import_module(f"parsers.{name}")
        _parsers[key] = f"parsers.{name}"
```

**Conversión automática de nombres:**
- `santander_parser.py` → aparece como **"santander"** en el menú
- `macro_parser.py` → aparece como **"macro"**
- `hsbc_parser.py` → aparece como **"hsbc"**

---

### 4️⃣ Probar el Nuevo Parser

1. **Guarda** el archivo en la carpeta `parsers/`
2. **Refresca** la página web (`http://localhost:5001`)
3. El nuevo banco aparecerá en el menú desplegable

**No necesitas:**
- ❌ Reconstruir el contenedor
- ❌ Reiniciar Docker
- ❌ Modificar `web_app.py`
- ❌ Modificar `index.html`

---

## 🔄 Recarga Dinámica

La aplicación recarga los parsers automáticamente en cada petición:

```python
@app.route('/')
def index():
    import importlib
    import parsers
    importlib.reload(parsers)  # 🔄 Recarga dinámica
    
    from parsers import get_parser
    bancos = sorted(list(get_parser.__globals__['_parsers'].keys()))
    return render_template('index.html', bancos=bancos)
```

---

## 📋 Plantilla Completa de Parser

```python
# parsers/NOMBRE_BANCO_parser.py

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parsea extractos de NOMBRE_BANCO.
    
    Returns:
        DataFrame con columnas requeridas o dict[str, DataFrame] para multi-hoja
    """
    print(f"\n🔍 [DEBUG] Parseando {pdf_path}")
    
    movimientos = []
    
    with open_pdf(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            
            # Agrupar por línea
            line_map = defaultdict(list)
            for w in words:
                y = round(w['top'])
                line_map[y].append(w)
            
            # Procesar cada línea
            for y in sorted(line_map):
                line = sorted(line_map[y], key=lambda w: w['x0'])
                
                # Tu lógica de extracción aquí
                fecha = None
                descripcion = ""
                debito = 0.0
                credito = 0.0
                saldo = 0.0
                
                for w in line:
                    x0 = w['x0']
                    text = w['text'].strip()
                    
                    # Mapear según posición X
                    if x0 < 60:
                        fecha = text
                    elif x0 < 300:
                        descripcion += text + " "
                    # ... etc
                
                if fecha:
                    movimientos.append({
                        "Fecha": fecha,
                        "Descripción": descripcion.strip(),
                        "Débito": debito,
                        "Crédito": credito,
                        "Saldo": saldo
                    })
    
    df = pd.DataFrame(movimientos)
    
    if df.empty:
        print("⚠️ No se extrajeron movimientos")
        return df
    
    # Convertir tipos
    for col in ("Débito", "Crédito", "Saldo"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", dayfirst=True, errors="coerce").dt.date
    
    # Calcular saldos
    df = calcular_saldos(df, es_layout_invertido=False)
    reportar_inconsistencias(df)
    
    print(f"✅ Procesadas {len(df)} filas")
    
    return df
```

---

## 🎨 Interfaz Web - Cambios Automáticos

**No necesitas modificar el HTML.** El template usa Jinja2 para generar el menú dinámicamente:

```html
<select id="banco" name="banco" required>
    {% for banco in bancos %}
    <option value="{{ banco }}">{{ banco }}</option>
    {% endfor %}
</select>
```

Los bancos se cargan automáticamente desde `_parsers`.

---

## 🐛 Solución de Problemas

### El nuevo banco no aparece

1. **Verifica el nombre del archivo:** Debe terminar en `_parser.py`
2. **Refresca la página** (Ctrl + F5)
3. **Revisa los logs:**
   ```bash
   docker-compose logs -f
   ```

### Error al procesar

Verifica que tu función `parse()` devuelva:
- `pd.DataFrame` (una sola hoja), o
- `dict[str, pd.DataFrame]` (múltiples hojas)

### Parser no se detecta después de editar

Si editaste un parser existente y no se actualizan los cambios:
```bash
docker-compose restart
```

---

## 📊 Ejemplo: Parser Multi-Hoja

Si un banco tiene múltiples cuentas (como Macro):

```python
def parse(pdf_path: str) -> dict[str, pd.DataFrame]:
    """Devuelve un dict con una hoja por cuenta."""
    
    cuentas = {
        "Cuenta Corriente - 123/456/7": df_corriente,
        "Caja de Ahorro - 789/012/3": df_ahorro,
    }
    
    return cuentas
```

---

## ✅ Checklist de Nuevo Parser

- [ ] Archivo `parsers/NOMBRE_parser.py` creado
- [ ] Función `parse(pdf_path: str)` implementada
- [ ] Devuelve `DataFrame` o `dict[str, DataFrame]`
- [ ] Columnas: `Fecha`, `Descripción`, `Débito`, `Crédito`, `Saldo`
- [ ] (Opcional) Perfil en `bank_profiles.py`
- [ ] Página web refrescada
- [ ] Nuevo banco aparece en el menú
- [ ] Parser probado con PDF real

---

## 🚀 Resumen

**Carpeta expuesta:** `./parsers`

**Para agregar un banco:**
1. Crear `parsers/nuevo_banco_parser.py`
2. Refrescar página web

**Modificaciones en la interfaz:** ❌ Ninguna (todo automático)

La interfaz detecta y muestra automáticamente todos los bancos disponibles sin necesidad de editar código HTML o Python adicional.
