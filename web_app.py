from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
from pathlib import Path
import traceback
import pandas as pd
import counter
from parsers import get_parser

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_sheet_name(name: str, max_len: int = 31) -> str:
    import re
    INVALID_SHEET_CHARS = r'[:\\/?*\[\]]'
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

@app.route('/')
def index():
    # Recargar parsers dinámicamente en cada petición
    import importlib
    import parsers
    importlib.reload(parsers)

    from parsers import get_parser
    bancos = sorted(list(get_parser.__globals__['_parsers'].keys()))
    return render_template('index.html', bancos=bancos)

@app.route('/check-pdf', methods=['POST'])
def check_pdf():
    """Endpoint para verificar si un PDF está protegido antes de procesarlo."""
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se encontró archivo PDF'}), 400

    file = request.files['pdf_file']

    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no permitido. Solo PDF.'}), 400

    # Guardar archivo temporal
    filename = secure_filename(file.filename)
    temp_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(temp_pdf)

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(temp_pdf)
        is_encrypted = getattr(reader, "is_encrypted", False)

        return jsonify({
            'encrypted': is_encrypted,
            'message': '🔒 Este PDF está protegido con contraseña' if is_encrypted else '✅ PDF sin protección'
        })
    except Exception as e:
        return jsonify({'error': f'Error al verificar PDF: {str(e)}'}), 500
    finally:
        # Limpiar archivo temporal
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except:
            pass

@app.route('/process', methods=['POST'])
def process_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se encontró archivo PDF'}), 400

    file = request.files['pdf_file']
    banco = request.form.get('banco')
    password = request.form.get('password', '').strip()  # Obtener contraseña opcional

    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    if not banco:
        return jsonify({'error': 'No se seleccionó ningún banco'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no permitido. Solo PDF.'}), 400

    try:
        # Recargar parsers dinámicamente para detectar nuevos bancos
        import importlib
        import parsers
        importlib.reload(parsers)
        from parsers import get_parser as get_parser_reload

        # Obtener parser
        parser_module = get_parser_reload(banco)
    except ValueError as err:
        return jsonify({'error': str(err)}), 400

    # Guardar archivo temporal
    filename = secure_filename(file.filename)
    temp_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(temp_pdf)

    # Guardar contraseña en variable de entorno temporal para que utils.py la use
    if password:
        os.environ['PDF_PASSWORD'] = password

    try:
        # Procesar PDF
        result = parser_module.parse(temp_pdf)

        # Generar nombre de salida
        base_name = Path(filename).stem
        output_filename = f"{base_name}_validado.xlsx"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        # Guardar Excel según el tipo de resultado
        if isinstance(result, dict):
            if not result:
                return jsonify({'error': 'El parser no detectó ninguna cuenta o movimiento'}), 400

            for k, v in result.items():
                if not isinstance(v, pd.DataFrame):
                    return jsonify({'error': f'Error interno: valor no-DataFrame para hoja {k}'}), 500

            write_multi_sheet_excel(result, Path(output_path))

        elif isinstance(result, pd.DataFrame):
            if result.empty:
                return jsonify({'error': 'No se extrajeron movimientos del PDF'}), 400

            write_single_sheet_excel(result, Path(output_path))

        else:
            return jsonify({'error': f'Tipo de retorno no soportado: {type(result).__name__}'}), 500

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ip = ip.split(",")[0].strip()
        counter.increment(banco, ip=ip)

        # Retornar archivo
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"⚠️ Error procesando PDF:")
        traceback.print_exc()
        error_msg = str(e) if str(e) else "Error interno al procesar el PDF"
        return jsonify({'error': error_msg}), 500

    finally:
        # Limpiar archivo temporal y contraseña
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            # Limpiar contraseña del entorno
            if 'PDF_PASSWORD' in os.environ:
                del os.environ['PDF_PASSWORD']
        except:
            pass

@app.route("/admin/stats")
def admin_stats():
    stats = counter.get_stats()
    return render_template("admin_stats.html", stats=stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
