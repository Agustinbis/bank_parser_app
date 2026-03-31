import pandas as pd
import pdfplumber
import sys
from PyPDF2 import PdfReader
import os

# ✅ Parámetro para definir el layout contable

def calcular_saldos(
    df: pd.DataFrame,
    es_layout_invertido: bool = False,
    saldo_arranca_en_fila_1: bool = False
) -> pd.DataFrame:
    """
    Agrega:
      - Saldo Calculado
      - Diferencia (Saldo — Saldo Calculado)
    Maneja DataFrames vacíos o con una sola fila sin fallar.
    """

    # 1) Validar columnas necesarias
    for col in ("Saldo", "Crédito", "Débito"):
        if col not in df.columns:
            raise KeyError(f"Falta columna '{col}' en el DataFrame")

    # 2) Si df está vacío, devolvemos columnas vacías
    if df.empty:
        df["Saldo Calculado"] = []
        df["Diferencia"]      = []
        return df

    # 3) Si sólo tiene una fila, copiamos el saldo y marcamos diferencia 0
    if len(df) == 1:
        df["Saldo Calculado"] = df["Saldo"]
        df["Diferencia"]      = 0.0
        return df

    # 4) Determinar fila de inicio y saldo base
    if saldo_arranca_en_fila_1:
        idx_inicio = 0
        saldo0 = round(df.loc[0, "Saldo"], 2)
    else:
        fila0 = df.loc[0, ["Saldo", "Crédito", "Débito"]]
        idx_inicio = 1 if (fila0 == 0).all() else 0
        saldo0 = round(df.loc[idx_inicio, "Saldo"], 2)

    # 🧭 Trazabilidad resumida
    print(f"\n🧮 [SALDOS] Inicio en fila {idx_inicio} | Saldo base = {saldo0} | Layout invertido = {es_layout_invertido}")

    # 5) Construir lista de Saldo Calculado
    saldos = []
    for i in range(len(df)):
        if i < idx_inicio:
            saldos.append(None)
        elif i == idx_inicio:
            saldos.append(saldo0)
        else:
            prev    = saldos[-1]
            credito = df.loc[i, "Crédito"]
            debito  = df.loc[i, "Débito"]
            nuevo   = prev + credito - debito if es_layout_invertido else prev + debito - credito
            saldos.append(round(nuevo, 2))

    # 6) Asignar columnas
    df["Saldo Calculado"] = saldos
    df["Diferencia"]      = df["Saldo"] - df["Saldo Calculado"]

    return df


def reportar_inconsistencias(df: pd.DataFrame) -> None:
    """
    Imprime en consola las filas donde la diferencia absoluta
    entre Saldo y Saldo Calculado supere 0.01.
    """
    inconsistencias = df[df["Diferencia"].abs() > 0.01]
    if not inconsistencias.empty:
        print("\n⚠️ Inconsistencias detectadas:")
        print(
            inconsistencias[["Fecha", "Descripción", "Saldo",
                             "Saldo Calculado", "Diferencia"]]
        )
    else:
        print("\n✅ Todos los saldos coinciden con los movimientos.")

# Cache en memoria: contraseña para PDFs cifrados
_cached_pdf_password = None

def open_pdf(pdf_path: str, password: str = None):
    """
    Abre un PDF con pdfplumber.
    
    VERSIÓN WEB: Si el PDF está cifrado, intenta usar:
    1. La contraseña proporcionada como parámetro
    2. La contraseña en la variable de entorno PDF_PASSWORD
    3. La contraseña cacheada en memoria
    
    Args:
        pdf_path: Ruta al archivo PDF
        password: Contraseña del PDF (opcional, solo si está cifrado)
    
    Returns:
        Objeto pdfplumber PDF
        
    Raises:
        RuntimeError: Si el PDF está cifrado y no se proporcionó contraseña válida
    """
    global _cached_pdf_password

    full_path = os.path.abspath(pdf_path)
    print(f"🔍 [DEBUG] open_pdf invocado para: {full_path}")

    reader = PdfReader(full_path)
    
    # Verificar si está cifrado
    if getattr(reader, "is_encrypted", False):
        print("🔒 PDF cifrado detectado")
        
        # Lista de contraseñas a probar (en orden de prioridad)
        passwords_to_try = []
        
        # 1. Contraseña proporcionada directamente
        if password:
            passwords_to_try.append(password)
            
        # 2. Contraseña desde variable de entorno (desde el formulario web)
        env_password = os.environ.get('PDF_PASSWORD')
        if env_password and env_password not in passwords_to_try:
            passwords_to_try.append(env_password)
            
        # 3. Contraseña cacheada
        if _cached_pdf_password and _cached_pdf_password not in passwords_to_try:
            passwords_to_try.append(_cached_pdf_password)

        # Intentar con cada contraseña
        for idx, pwd in enumerate(passwords_to_try):
            try:
                test_reader = PdfReader(full_path)
                test_reader.decrypt(pwd)
                pdf = pdfplumber.open(full_path, password=pwd)
                print(f"   ✅ Abierto con contraseña (intento {idx + 1})")
                _cached_pdf_password = pwd  # Cachear para próximos usos
                return pdf
            except Exception as e:
                print(f"   ⚠️ Contraseña {idx + 1} inválida: {e}")
                continue
        
        # No hay contraseña válida disponible
        raise RuntimeError(
            "Este PDF está protegido con contraseña. "
            "La contraseña proporcionada es incorrecta o no se proporcionó ninguna contraseña. "
            "Por favor, verifique la contraseña e intente nuevamente."
        )

    # No está cifrado
    pdf = pdfplumber.open(full_path)
    print(f"   ✅ Abierto sin cifrar: {full_path}")
    return pdf
