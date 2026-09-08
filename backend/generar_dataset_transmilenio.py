#!/usr/bin/env python
"""Script para generar dataset TransMilenio real desde GTFS oficial.

Uso:
    python generar_dataset_transmilenio.py --real      # Descarga GTFS real (requiere internet)
    python generar_dataset_transmilenio.py --sintetico # Dataset 6 nodos ejemplo PDF
"""

import argparse
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from grafo.repositorio import RepositorioGrafo, ExcepcionRepositorio


def main():
    parser = argparse.ArgumentParser(description="Generar dataset TransMilenio")
    parser.add_argument("--real", action="store_true", help="Descargar y procesar GTFS oficial")
    parser.add_argument("--sintetico", action="store_true", help="Dataset 6 nodos ejemplo PDF")
    parser.add_argument("--datos", default="datos", help="Directorio de datos")
    args = parser.parse_args()

    if not args.real and not args.sintetico:
        print("Especifique --real o --sintetico")
        parser.print_help()
        return 1

    repo = RepositorioGrafo(args.datos)

    try:
        if args.real:
            print(">>> GENERANDO DATASET TRANSMILENIO REAL (GTFS OFICIAL) <<<")
            print("Esto descargará ~50-100MB y puede tardar varios minutos...")
            grafo = repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=True, descargar_geo=True)
        else:
            print(">>> GENERANDO DATASET SINTÉTICO (6 NODOS EJEMPLO PDF) <<<")
            grafo = repo.generar_dataset_inicial_transmilenio(usar_gtfs_real=False)

        print(f"\n[OK] Grafo generado:")
        print(f"  Nodos: {len(grafo.nodos)}")
        print(f"  Aristas: {len(grafo.aristas)}")
        print(f"  Dirigido: {grafo.dirigido}")

        # Validar
        from grafo.validadores import validar_grafo_completo, calcular_estadisticas
        valido, errores = validar_grafo_completo(grafo)
        stats = calcular_estadisticas(grafo)

        print(f"\n[OK] Validacion: {'PASO' if valido else 'CON ERRORES'}")
        if errores:
            for e in errores[:10]:
                print(f"  - {e}")

        print(f"\n[OK] Estadisticas:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

        return 0

    except ExcepcionRepositorio as e:
        print(f"Error del repositorio: {e}")
        return 1
    except Exception as e:
        print(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())