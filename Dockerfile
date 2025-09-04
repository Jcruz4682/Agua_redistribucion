FROM jupyter/scipy-notebook:latest

WORKDIR /app

COPY requirements.txt .
COPY dashboard_agua.py .
COPY Datos_qgis ./Datos_qgis


RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "dashboard_agua.py", "--server.port=8501", "--server.address=0.0.0.0"]
