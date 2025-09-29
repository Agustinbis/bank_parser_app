import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Any
import pandas as pd
import traceback

from parsers import get_parser

DEFAULT_PDF_FOLDER = Path(__file__).resolve().parent / "pdfs"

INVALID_SHEET_CHARS = r'[:\\/?*\[\]]'

def sanitize_sheet_name(name: str, max_len: int = 31) -> str:
    import re
    sheet = re.sub(INVALID_SHEET_CHARS, "_", str(name)).strip()
    return (sheet or "Hoja")[:max_len]

def write_multi_sheet_excel(dfs: dict[str, pd.DataFrame], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path) as writer:
        for name, df in dfs.items():
            sheet = sanitize_sheet_name(name)
            df.to_excel(writer, sheet_name=sheet, index=False)

def write_single_sheet_excel(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_path, index=False)

def process_all_pdfs(pdf_folder: str, parse_func):
    folder = Path(pdf_folder)
    if not folder.exists() or not folder.is_dir():
        messagebox.showerror("Error", f"Carpeta inválida:\n{pdf_folder}")
        return

    pdf_paths = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    report = []

    for pdf_path in pdf_paths:
        salida = folder / f"{pdf_path.stem}_validado.xlsx"

        # 1) Skip sin resultados pegados
        if salida.exists():
            report.append(f"⏭️ Saltado: {pdf_path.name}")
            continue

        try:
            # 2) Llamada al parser y DEBUG solo aquí
            result: Any = parse_func(str(pdf_path))
            print(f"🔍 [DEBUG-main] parse() devolvió: {result!r}  (type={type(result)})")

            # 3) Resultado tipo dict → multi-hoja
            if isinstance(result, dict):
                if not result:
                    raise ValueError("El parser devolvió un dict vacío (sin cuentas detectadas).")
                for k, v in result.items():
                    if not isinstance(v, pd.DataFrame):
                        raise TypeError(f"Valor no-DataFrame para la hoja '{k}': {type(v)}")

                write_multi_sheet_excel(result, salida)
                report.append(f"✅ Procesado (multi-hoja): {pdf_path.name}")

            # 4) Resultado tipo DataFrame → single sheet
            elif isinstance(result, pd.DataFrame):
                write_single_sheet_excel(result, salida)
                report.append(f"✅ Procesado: {pdf_path.name}")

            # 5) Cualquier otro tipo → error
            else:
                raise TypeError(
                    f"Tipo de retorno no soportado: {type(result)}. "
                    "Esperaba dict[str, DataFrame] o DataFrame."
                )

        except Exception as e:
            # 1) imprime en consola la traza completa
            print(f"⚠️ [DEBUG-main] Error procesando {pdf_path.name}:")
            traceback.print_exc()

            # 2) prepara un string más legible
            msg = str(e)
            if msg == "1":
                msg = "Error interno genérico ‘1’ (ver consola para detalles)"

            report.append(f"❌ Error en {pdf_path.name}: {msg}")
            report.append(f"❌ {type(e).__name__} en {pdf_path.name}: {msg}")

    messagebox.showinfo("Resultados", "\n".join(report) or "No se encontraron PDFs.")

def on_start(root, banco_var, dropdown):
    banco = banco_var.get()
    try:
        parser_module = get_parser(banco)
    except ValueError as err:
        messagebox.showerror("Banco no soportado", str(err))
        return

    root.destroy()
    process_all_pdfs(str(DEFAULT_PDF_FOLDER), parser_module.parse)

def main():
    root = tk.Tk()
    root.title("Bank Parser")

    tk.Label(root, text="Seleccioná el banco:").pack(padx=10, pady=(10, 0))

    bancos = list(get_parser.__globals__['_parsers'].keys())
    banco_var = tk.StringVar(value=bancos[0])
    tk.OptionMenu(root, banco_var, *bancos).pack(padx=10, pady=5)

    tk.Button(
        root,
        text="Procesar PDFs",
        command=lambda: on_start(root, banco_var, bancos)
    ).pack(padx=10, pady=(5, 10))

    root.mainloop()

if __name__ == "__main__":
    main()