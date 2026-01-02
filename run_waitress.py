import os
from dotenv import load_dotenv
from waitress import serve
from django.core.wsgi import get_wsgi_application
 
# Load .env
load_dotenv()
 
# Set settings Django
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "data_materials.settings"  # GANTI sesuai nama project
)
 
application = get_wsgi_application()
 
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", 8050))
 
display_host = "localhost" if host == "0.0.0.0" else host
url = f"http://{display_host}:{port}"
 
print(f"\nServer Django berjalan! Silakan kunjungi: {url}\n")
 
serve(
    application,
    host=host,
    port=port,
    threads=4
)