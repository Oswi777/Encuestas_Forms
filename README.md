# BW Encuestas Pro

Plataforma de encuestas BW (Kiosko + Link) con campañas/listas versionadas.

## Incluye
- Plantillas de encuesta (JSON) con ramificación (show_if).
- Campañas/Listas (snapshot inmutable) y menú con múltiples campañas activas.
- Captura anónima con **seguimiento opcional** (Nombre + No. empleado si el usuario lo decide).
- Área (catálogo) opcional por campaña, importable por Excel.
- Turno fijo: T1/T2/T3/MIXTO/4X3.
- Kiosko: fullscreen opcional, reset 60s, cola offline.
- Dashboards y export: CSV raw + PDF ejecutivo.
- QR por campaña.

## Ejecutar en local
1) Crear venv e instalar:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```
2) Variables (opcional):
```bash
export FLASK_SECRET_KEY='dev'
export ADMIN_USERNAME='admin'
export ADMIN_PASSWORD='admin'
```
3) Correr:
```bash
flask --app wsgi:app run --debug
```
4) Abrir:
- Admin: http://localhost:5000/admin
- Menú público: http://localhost:5000/menu

## Render (prueba)
- Usa `DATABASE_URL` de Postgres.
- Arranque via `gunicorn wsgi:app`.

