# parsers/municipalRosario_parser.py

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

# Regex permisivo para distintos formatos de cuenta
ACCOUNT_RE = re.compile(r"\b\d{1,3}[-/]\d{1,12}[-/]\d{1,3}\b")

def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()

def extract_account_key(header_text: str) -> tuple[str | None, str | None]:
    t = normalize_spaces(header_text.upper())
    m = ACCOUNT_RE.search(t)
    if not m:
        return None, None
    acct = m.group(0)
    if any(tok in t for tok in ("DÓLARES", "DOLARES", "USD")):
        return f"{acct}|USD", f"DÓLARES – {acct}"
    return f"{acct}|ARS", f"PESOS   – {acct}"

profile     = BANK_PROFILES["MUNICIPALROS"]
layout      = profile["layout"]
flags       = profile["flags"]
excluir     = profile["excluir_si_contiene"]
default_idx = profile["buscar_desde_pagina"]

def convert_amount(txt: str) -> float:
    if not txt:
        return 0.0

    txt = txt.replace(".", "").replace(",", ".").strip()

    # Detectar guion al final o flotante
    negativo = False
    if txt.endswith("-"):
        negativo = True
        txt = txt[:-1].strip()
    elif "-" in txt and txt.count("-") == 1:
        txt = txt.replace("-", "").strip()
        negativo = True

    try:
        val = float(txt)
        return -val if negativo else val
    except ValueError:
        return 0.0


def parse(pdf_path: str) -> dict[str, pd.DataFrame]:
    """Parsea extractos de MUNICIPALROS y devuelve dict hoja → DataFrame."""
    print(f"\n🔍 [DEBUG-parse] Inicio parse(): {pdf_path}")

    banco = "MUNICIPALROS"
    profile = BANK_PROFILES.get(banco)
    if not profile:
        print(f"❌ No se encontró perfil para banco '{banco}'")
        return {}

    layout     = profile.get("layout", {})
    flags      = profile.get("flags", {})
    excluir    = profile.get("excluir_si_contiene", [])
    default_idx = profile.get("buscar_desde_pagina", 0)

    # Validar flags como booleanos reales
    es_invertido = flags.get("es_layout_invertido", False)
    if isinstance(es_invertido, str):
        es_invertido = es_invertido.lower() == "true"

    arranca_en_1 = flags.get("saldo_arranca_en_fila_1", False)
    if isinstance(arranca_en_1, str):
        arranca_en_1 = arranca_en_1.lower() == "true"

    print(f"✅ Perfil cargado para banco: {banco}")
    print(f"   → Layout invertido: {es_invertido}")
    print(f"   → Saldo arranca en fila 1: {arranca_en_1}")

    cuentas        = defaultdict(list)
    # display_names  = {}
    # cuenta_key     = None
    # account_states = {}
    en_detalle = False
    header_found = False

    resultados_por_hoja = {}
    hoja_actual = None
    movimientos_actuales = []


    with open_pdf(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        start_idx   = default_idx
        movimientos=[]
        start_idx = default_idx
        
        for i, page in enumerate(pdf.pages[:5]):
            txt = (page.extract_text() or "").upper()
            if "HOJA NRO" in txt:
                start_idx = i
                print(f"📄 Primera aparición de HOJA NRO en página {i}")
                
                break
        
        for idx in range(start_idx, total_pages):
            page    = pdf.pages[idx]
            cropped = page.within_bbox((0, 150, page.width, page.height))
            solo_diagnostico = (idx == 0)
            words   = cropped.extract_words(use_text_flow=False)
            if not words:
                continue
               
            line_map = defaultdict(list)
            for w in words:
                y = round(w["top"]/10)*10 # ← agrupamiento tolerante
                line_map[y].append(w)

            for y in sorted(line_map):
                line   = sorted(line_map[y], key=lambda w: w["x0"])
                '''
                for w in line:
                    print(f"   x0={w['x0']:.1f} → '{w['text']}'")'''

                texts  = [w["text"] for w in line]
                joined = " ".join(texts).upper().strip()
                
                '''
                #Eliminar
                cols = {
                    "Fecha": None, "Descripción": "", "Referencia": "",
                    "Débito": None, "Crédito": None, "Saldo": None
                }
            
                if solo_diagnostico:
                    print(f"\n🔎 Línea detectada en página {idx}, y={y}")
                    print(f"   → Texto unido: {joined}")

                '''

                # Iniciar detalle
                if not en_detalle:
                    if "DETALLE" in joined and "MOVIMIENTO" in joined:
                        en_detalle = True
                        #print(f"🔓 Activado en_detalle por DETALLE MOVIMIENTO en página {idx}")
                    elif "FECHA" in joined and "SALDO" in joined:
                        en_detalle = True
                        header_found = True
                        #print(f"🔓 Activado en_detalle por FECHA SALDO en página {idx}")
                    continue


                if "FECHA" in joined and "SALDO" in joined:
                    header_found = True
                    continue

                if any(tok in joined for tok in (excluir + [
                    "SALDO INICIAL", "SALDO FINAL", "TOTAL COBRADO",
                    "INFORMACIÓN DE SUS CUENTAS", "CLAVE BANCARIA UNIFORME"
                ])):
                    continue

                # Mapear columnas
                cols = {
                    "Fecha": None, "Descripción": "", "Referencia": "",
                    "Débito": None, "Crédito": None, "Saldo": None
                }
                '''
                #agregado. Eliminar
                if solo_diagnostico:
                    print(f"   → Fecha: '{cols['Fecha']}' | Débito: '{cols['Débito']}' | Crédito: '{cols['Crédito']}' | Saldo: '{cols['Saldo']}'")
                '''
                for w in line:
                    x0, txt = w["x0"], w["text"].strip()
                    if layout["date_x"][0] <= x0 < layout["date_x"][1]:
                        cols["Fecha"] = txt
                    elif layout["desc_x"][0] <= x0 < layout["desc_x"][1]:
                        cols["Descripción"] += (" " + txt) if cols["Descripción"] else txt
                    elif layout["ref_x"][0] <= x0 < layout["ref_x"][1]:
                        cols["Referencia"] += (" " + txt) if cols["Referencia"] else txt
                    elif layout["debit_x"][0] <= x0 < layout["debit_x"][1]:
                        cols["Débito"] = txt
                    elif layout["credit_x"][0] <= x0 < layout["credit_x"][1]:
                        cols["Crédito"] = txt
                    elif layout["balance_x"][0] <= x0 < layout["balance_x"][1]:
                        cols["Saldo"] = txt

                # Validar línea
                fecha = cols["Fecha"].strip() if cols["Fecha"] else ""
                date_pattern = re.compile(r"^\d{2}/\d{2}/(?:\d{2}|\d{4})$")
                if (
                    not fecha
                    or not date_pattern.match(fecha)
                    or all(cols[k] in (None, "") for k in ("Débito", "Crédito", "Saldo"))
                ):
                    continue
                
                '''
                #Bloque validacion
                if (
                    not fecha
                    or not date_pattern.match(fecha)
                    or all(cols[k] in (None, "") for k in ("Débito", "Crédito", "Saldo"))
                ):
                    if solo_diagnostico:
                        print("   ⚠️ Línea descartada por validación")
                    continue
                else:
                    if solo_diagnostico:
                        print("   ✅ Línea válida, se va a cargar")
                    '''

                movimientos.append({
                    "Fecha":       fecha,
                    "Descripción": cols["Descripción"],
                    "Referencia":  cols["Referencia"],
                    "Débito":      convert_amount(cols["Débito"]),
                    "Crédito":     convert_amount(cols["Crédito"]),
                    "Saldo":       convert_amount(cols["Saldo"])
                })
                #print(f"✅ Movimiento cargado → Fecha: {fecha} | Desc: {cols['Descripción']} | Débito: {cols['Débito']} | Crédito: {cols['Crédito']} | Saldo: {cols['Saldo']}")

    df = pd.DataFrame(movimientos)
    if not df.empty:
        for col in ("Débito", "Crédito", "Saldo"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", dayfirst=True, errors="coerce").dt.date
        df = calcular_saldos(df, es_layout_invertido=es_invertido, saldo_arranca_en_fila_1=arranca_en_1)
        reportar_inconsistencias(df)

    print(f"\n📊 [DEBUG] MUNICIPALROS → {len(df)} filas procesadas")
    return {"ResumenMunicipal": df}

