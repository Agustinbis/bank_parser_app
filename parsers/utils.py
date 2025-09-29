import pandas as pd
import pdfplumber
import sys
from PyPDF2 import PdfReader
import tkinter as tk
from tkinter import simpledialog, messagebox
import os

# Tkinter es obligatorio
try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
except ImportError:
    raise ImportError(
        "Tkinter no está disponible. Instalá el módulo 'python3-tk' "
        "o ejecutá en un entorno donde Tkinter esté presente."
    )


# ✅ Parámetro para definir el layout contable

def calcular_saldos(
    df: pd.DataFrame,
    es_layout_invertido: bool = False,
    saldo_arranca_en_fila_1: bool = False
) -> pd.DataFrame:
    """
    Agrega:
      - Saldo Calculado
      - Diferencia (Saldo – Saldo Calculado)
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

# Cache en memoria: ruta_pdf → contraseña. Vacia al reiniciar la app.
_cached_pdf_password = None

def ask_password(pdf_path: str) -> str:
    root = tk.Tk(); root.withdraw()
    pwd = simpledialog.askstring(
        "Clave PDF",
        f"Ingrese clave para:\n{pdf_path}",
        show="*"
    )
    root.destroy()
    if not pwd:
        messagebox.showerror("Error", "No se ingresó clave. Operación cancelada.")
        raise RuntimeError("Clave de PDF no proporcionada.")
    return pwd

def open_pdf(pdf_path: str):
    """
    Abre un PDF con pdfplumber. Si está cifrado:
      1) Usa la _cached_pdf_password si existe.
      2) Si no existe o falla, pide nueva y la guarda en _cached_pdf_password.
    Esa clave vive solo mientras dure la sesión de Python.
    """
    global _cached_pdf_password

    full_path = os.path.abspath(pdf_path)
    print(f"🔍 [DEBUG] open_pdf invocado para: {full_path}")

    reader = PdfReader(full_path)
    if getattr(reader, "is_encrypted", False):
        print("🔒 PDF cifrado detectado")

        # 1) Si ya tenemos una clave en memoria, probamos con ella
        if _cached_pdf_password is not None:
            try:
                reader.decrypt(_cached_pdf_password)
                pdf = pdfplumber.open(full_path, password=_cached_pdf_password)
                print("   ✅ Abierto con clave cacheada")
                return pdf
            except Exception as e:
                print(f"   ⚠️ Clave cacheada inválida: {e}")
                _cached_pdf_password = None

        # 2) Si no hay clave cacheada o la anterior falló, pedimos una nueva
        nueva = ask_password(full_path)
        try:
            reader.decrypt(nueva)
            pdf = pdfplumber.open(full_path, password=nueva)
            print("   ✅ Abierto con nueva clave, ahora cacheada")
            _cached_pdf_password = nueva
            return pdf
        except Exception as e:
            print(f"   ❌ La clave ingresada sigue siendo inválida: {e}")
            messagebox.showerror("Error", "Contraseña incorrecta. Operación cancelada.")
            raise RuntimeError("Clave de PDF inválida.")

    # No está cifrado
    pdf = pdfplumber.open(full_path)
    print(f"   ✅ Abierto sin cifrar: {full_path}")
    return pdf



