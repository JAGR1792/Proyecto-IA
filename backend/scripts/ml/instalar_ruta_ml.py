"""Inserta la ruta ML de forma idempotente en FastAPI; guarda copia de main.py."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[3]
main=root/'backend/src/api/main.py'
if not main.is_file():
    raise SystemExit('No se encuentra backend/src/api/main.py; revisa la ruta del repositorio.')
s=main.read_text(encoding='utf-8')
imp='from src.api.rutas_ml import router as ml_router'
inc='app.include_router(ml_router, prefix="/api/v1/ml", tags=["Machine Learning"])'
if imp in s and inc in s:
    print('La ruta ML ya estaba instalada; no se realizaron cambios.')
else:
    anchor='from src.api.rutas_mapa import router as mapa_router'
    inc_anchor='app.include_router(mapa_router, prefix="/api/v1/mapa", tags=["Mapa"])'
    if anchor not in s or inc_anchor not in s:
        raise SystemExit('main.py tiene otra estructura: instala manualmente el import y el include_router; no se cambió nada.')
    shutil.copy2(main, main.with_suffix('.py.antes_ml'))
    s=s.replace(anchor,anchor+'\n'+imp)
    s=s.replace(inc_anchor,inc_anchor+'\n'+inc)
    main.write_text(s,encoding='utf-8')
    print('Ruta ML registrada. Backup:',main.with_suffix('.py.antes_ml'))
