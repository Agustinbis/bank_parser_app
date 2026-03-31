# Bank Parser Web - Docker

Sistema web para procesar extractos bancarios en PDF y convertirlos a Excel.

## 📋 Estructura del Proyecto

```
bank-parser/
├── web_app.py              # Aplicación Flask principal
├── Dockerfile              # Configuración Docker
├── docker-compose.yml      # Orquestación Docker
├── .dockerignore          # Archivos excluidos del build
├── requirements.txt       # Dependencias Python
├── templates/
│   └── index.html         # Interfaz web
└── parsers/
    ├── __init__.py
    ├── bank_profiles.py
    ├── utils.py
    ├── galicia_parser.py
    ├── macro_parser.py
    └── municipalRosario_parser.py
```

## 🚀 Instalación y Ejecución

### Opción 1: Con Docker Compose (Recomendado)

```bash
# Construir y ejecutar en un solo comando
docker-compose up --build

# O en modo detached (segundo plano)
docker-compose up -d --build
```

### Opción 2: Solo con Docker

```bash
# Construir la imagen
docker build -t bank-parser-web .

# Ejecutar el contenedor
docker run -d -p 5001:5000 --name bank-parser bank-parser-web
```

## 🌐 Acceso a la Aplicación

Una vez iniciado el contenedor, accede a:

**http://localhost:5001**

## 📖 Uso

1. Abre tu navegador en `http://localhost:5001`
2. Selecciona el banco del menú desplegable
3. Haz clic en "Seleccionar archivo PDF" y elige tu extracto
4. Presiona "Procesar PDF"
5. El archivo Excel se descargará automáticamente

## 🛑 Detener la Aplicación

### Con Docker Compose:
```bash
docker-compose down
```

### Con Docker:
```bash
docker stop bank-parser
docker rm bank-parser
```

## 🔧 Desarrollo

Para desarrollo con auto-recarga, modifica el `docker-compose.yml`:

```yaml
environment:
  - FLASK_ENV=development
```

Y reinicia:
```bash
docker-compose restart
```

## 📝 Logs

Ver logs en tiempo real:
```bash
# Con Docker Compose
docker-compose logs -f

# Con Docker
docker logs -f bank-parser
```

## ⚙️ Variables de Entorno

- `FLASK_ENV`: `production` o `development`
- Puerto por defecto: `5001`

## 🐛 Solución de Problemas

### El puerto 5001 está ocupado
Modifica el puerto en `docker-compose.yml`:
```yaml
ports:
  - "8080:5001"  # Cambia 8080 por el puerto que prefieras
```

### Error al procesar PDF
Verifica los logs del contenedor:
```bash
docker-compose logs bank-parser
```

### PDFs protegidos con contraseña
La versión web no soporta PDFs protegidos con contraseña. Desbloquéalos antes de subirlos.

## 📦 Actualizar Dependencias

1. Modifica `requirements.txt`
2. Reconstruye la imagen:
```bash
docker-compose up --build
```

## 🔒 Seguridad

- Límite de tamaño de archivo: 16MB
- Solo acepta archivos `.pdf`
- Los archivos temporales se eliminan automáticamente después del procesamiento

## 🎨 Personalización

### Cambiar límite de tamaño de archivo

En `web_app.py`, modifica:
```python
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Tamaño en bytes
```

### Modificar interfaz

Edita `templates/index.html` y reconstruye la imagen.

## 📄 Licencia

El mismo que el proyecto original.
