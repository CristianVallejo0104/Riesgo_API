def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_crear_activo(client):
    payload = {"ticker": "AAPL", "nombre": "Apple", "sector": "Tech", "moneda": "USD"}
    response = client.post("/activos/", json=payload)
    assert response.status_code == 201
    assert response.json()["ticker"] == "AAPL"


def test_listar_activos_vacio(client):
    response = client.get("/activos/")
    assert response.status_code == 200
    assert response.json() == []


def test_crear_portafolio(client):
    payload = {
        "nombre": "Test Portfolio",
        "tickers": ["AAPL", "JPM"],
        "pesos": {"AAPL": 0.5, "JPM": 0.5},
    }
    response = client.post("/portafolios/", json=payload)
    assert response.status_code == 201
    assert response.json()["nombre"] == "Test Portfolio"


def test_activo_no_encontrado(client):
    response = client.get("/activos/ZZZZ")
    assert response.status_code == 404