#!/usr/bin/env python
"""Script para generar dataset de red vial para taxis en Chapinero.

Uso:
    python generar_dataset.py --osm       # Descarga red vial OpenStreetMap (OSMnx)
    python generar_dataset.py --sintetico # Dataset 6 nodos ejemplo PDF
"""

import argparse
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from grafo.repositorio import ExcepcionRepositorio, RepositorioGrafo


def main():
    parser = argparse.ArgumentParser(description="Generar dataset de taxis (Chapinero)")
    parser.add_argument("--osm", action="store_true", help="Descargar red vial desde OpenStreetMap (OSMnx)")
    parser.add_argument("--lugar", default="Universidad Sergio Arboleda, Bogotá, Colombia", help="Lugar para OSM (geocodificación)")
    parser.add_argument("--radio", type=int, default=1500, help="Radio en metros para descarga OSM")
    parser.add_argument("--tipo-red", default="drive", help="Tipo de red OSM: drive, walk, bike, all")
    parser.add_argument("--sintetico", action="store_true", help="Dataset 6 nodos ejemplo PDF")
    parser.add_argument("--datos", default="datos", help="Directorio de datos")
    args = parser.parse_args()

    if not args.osm and not args.sintetico:
        print("Especifique --osm o --sintetico")
        parser.print_help()
        return 1

    repo = RepositorioGrafo(args.datos)

    try:
        if args.osm:
            print(">>> GENERANDO DATASET OPENSTREETMAP (OSMnx) <<<")
            print(f"Lugar: {args.lugar} | Radio: {args.radio}m | Red: {args.tipo_red}")
            grafo = repo.generar_dataset_osm(
                lugar=args.lugar,
                radio_metros=args.radio,
                tipo_red=args.tipo_red,
            )
        else:
            print(">>> GENERANDO DATASET SINTÉTICO (6 NODOS EJEMPLO PDF) <<<")
            grafo = repo.generar_dataset_sintetico_pdf()

        print("\n[OK] Grafo generado:")
        print(f"  Nodos: {len(grafo.nodos)}")
        print(f"  Aristas: {len(grafo.aristas)}")
        print(f"  Dirigido: {grafo.dirigido}")

        # Validar
        from grafo.validadores import calcular_estadisticas, validar_grafo_completo
        valido, errores = validar_grafo_completo(grafo)
        stats = calcular_estadisticas(grafo)

        print(f"\n[OK] Validacion: {'PASO' if valido else 'CON ERRORES'}")
        if errores:
            for e in errores[:10]:
                print(f"  - {e}")

        print("\n[OK] Estadisticas:")
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
