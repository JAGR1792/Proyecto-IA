"""Pruebas de integración de DFS con el contrato de búsqueda del equipo."""

import pytest

from src.busqueda.base import ResultadoBusqueda
from src.busqueda.dfs import BusquedaProfundidad
from src.grafo.modelos import Arista, Coordenadas, Grafo, NivelCongestion, Nodo


@pytest.fixture
def grafo_ejemplo() -> Grafo:
    """Grafo dirigido con desvíos, ciclo y conexión directa más corta."""
    grafo = Grafo()
    for nombre in "ABCD":
        grafo.agregar_nodo(
            Nodo(
                id=nombre,
                nombre=f"Intersección {nombre}",
                coordenadas=Coordenadas(latitud=4.65, longitud=-74.06),
            )
        )
    for id_arista, origen, destino, distancia, minutos in [
        ("AB", "A", "B", 100, 2),
        ("AD", "A", "D", 50, 1),
        ("BC", "B", "C", 200, 3),
        ("CD", "C", "D", 300, 4),
        ("CA", "C", "A", 70, 1),
    ]:
        grafo.agregar_arista(
            Arista(
                id=id_arista,
                origen=origen,
                destino=destino,
                distancia=distancia,
                tiempo_estimado=minutos,
            )
        )
    return grafo


def test_dfs_encuentra_camino_no_optimo_y_metricas(grafo_ejemplo: Grafo) -> None:
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D")
    assert isinstance(resultado, ResultadoBusqueda)
    assert resultado.algoritmo == "dfs"
    assert resultado.ruta_encontrada
    assert resultado.camino == ["A", "B", "C", "D"]
    assert resultado.aristas_camino == ["AB", "BC", "CD"]
    assert resultado.nodos_explorados == 4
    assert resultado.detalle["num_aristas"] == 3
    assert resultado.costo_total == 9.0
    assert resultado.distancia_total_m == 600.0
    assert resultado.tiempo_total_min == 9.0
    assert resultado.tiempo_ejecucion_ms >= 0


@pytest.mark.parametrize(
    ("criterio", "costo"),
    [
        ("menor_tiempo", 9.0),
        ("menor_distancia", 600.0),
        ("menor_conexiones", 3.0),
    ],
)
def test_dfs_reporta_costo_sin_modificar_la_ruta(
    grafo_ejemplo: Grafo, criterio: str, costo: float
) -> None:
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D", criterio)
    assert resultado.costo_total == costo
    assert resultado.camino == ["A", "B", "C", "D"]


def test_dfs_respeta_conexiones_no_disponibles(grafo_ejemplo: Grafo) -> None:
    grafo_ejemplo.aristas[0].disponible = False
    assert BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D").camino == ["A", "D"]


def test_dfs_respeta_congestion_bloqueada(grafo_ejemplo: Grafo) -> None:
    grafo_ejemplo.aristas[0].congestion = NivelCongestion.BLOQUEADA
    assert BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D").camino == ["A", "D"]


def test_dfs_respeta_sentido_de_via(grafo_ejemplo: Grafo) -> None:
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "D", "A")
    assert not resultado.ruta_encontrada
    assert resultado.camino == []
    assert resultado.aristas_camino == []


def test_dfs_origen_igual_destino(grafo_ejemplo: Grafo) -> None:
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "B", "B")
    assert resultado.ruta_encontrada
    assert resultado.camino == ["B"]
    assert resultado.costo_total == 0.0


def test_dfs_sin_ruta(grafo_ejemplo: Grafo) -> None:
    grafo_ejemplo.aristas[0].disponible = False
    grafo_ejemplo.aristas[1].disponible = False
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D")
    assert not resultado.ruta_encontrada
    assert resultado.nodos_explorados == 1


@pytest.mark.parametrize(
    ("origen", "destino", "criterio"),
    [
        ("X", "A", "menor_tiempo"),
        ("A", "X", "menor_tiempo"),
        ("A", "D", "peso"),
    ],
)
def test_dfs_valida_entradas(
    grafo_ejemplo: Grafo, origen: str, destino: str, criterio: str
) -> None:
    with pytest.raises(ValueError):
        BusquedaProfundidad().buscar(grafo_ejemplo, origen, destino, criterio)


def test_dfs_no_dirigido() -> None:
    grafo = Grafo(dirigido=False)
    for nombre in "AB":
        grafo.agregar_nodo(
            Nodo(
                id=nombre,
                nombre=nombre,
                coordenadas=Coordenadas(latitud=4.65, longitud=-74.06),
            )
        )
    grafo.agregar_arista(Arista(id="AB", origen="A", destino="B", distancia=100, tiempo_estimado=2))
    assert BusquedaProfundidad().buscar(grafo, "B", "A").camino == ["B", "A"]


def test_dfs_parentesco_al_extraer_de_pila() -> None:
    grafo = Grafo()
    for nombre in "ABC":
        grafo.agregar_nodo(
            Nodo(
                id=nombre,
                nombre=nombre,
                coordenadas=Coordenadas(latitud=4.65, longitud=-74.06),
            )
        )
    for nombre, u, v in [("AB", "A", "B"), ("AC", "A", "C"), ("BC", "B", "C")]:
        grafo.agregar_arista(Arista(id=nombre, origen=u, destino=v, distancia=1, tiempo_estimado=1))
    assert BusquedaProfundidad().buscar(grafo, "A", "C").camino == ["A", "B", "C"]


def test_dfs_paralelas_conserva_arista_real(grafo_ejemplo: Grafo) -> None:
    grafo_ejemplo.agregar_arista(
        Arista(id="AB_alt", origen="A", destino="B", distancia=1, tiempo_estimado=1)
    )
    resultado = BusquedaProfundidad().buscar(grafo_ejemplo, "A", "D")
    assert resultado.aristas_camino == ["AB", "BC", "CD"]
