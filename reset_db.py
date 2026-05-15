import os
import sys

# Cambiar al directorio de la app
os.chdir('c:\\Users\\Fran\\Desktop\\tienda_tejidos')
sys.path.insert(0, '.')

# Eliminar BD
db_path = "instance/tienda.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"✓ BD eliminada: {db_path}")

# Reinicializar
from app import app, init_db
with app.app_context():
    init_db()
    print("✓ BD recreada correctamente")
    print("✓ Catálogo inicial cargado")
