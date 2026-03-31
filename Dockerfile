FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para pdfplumber y pandas
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements.txt primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar Flask y las dependencias del proyecto
RUN pip install --no-cache-dir Flask==3.0.0 && \
    pip install --no-cache-dir -r requirements.txt


# Todo comentado, porque ahora se pasan directamente como volumenes al contenedor
   # Copiar el código de la aplicación
   #COPY web_app.py .
   #COPY parsers/ ./parsers/
   #COPY counter.py .

   # Crear directorio para templates
   #RUN mkdir -p templates
   
   # Copiar template HTML
   #COPY templates/ ./templates/

# Exponer el puerto 5000
EXPOSE 5000

# Variable de entorno para Flask
ENV FLASK_APP=web_app.py

# Comando para ejecutar la aplicación
CMD ["python", "web_app.py"]
