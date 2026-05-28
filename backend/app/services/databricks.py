from databricks import sql

from app.config import get_settings


CONSULTAS_PREDEFINIDAS = {
    "promedio_cierre": {
        "titulo": "Promedio de cierre por activo",
        "descripcion": "Promedio, mínimo y máximo del precio de cierre por ticker.",
        "sql": """
            SELECT
                ticker,
                COUNT(*) AS registros,
                ROUND(AVG(close), 2) AS cierre_promedio,
                ROUND(MIN(close), 2) AS cierre_minimo,
                ROUND(MAX(close), 2) AS cierre_maximo
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY cierre_promedio DESC
        """,
    },
    "desviacion_cierre": {
        "titulo": "Desviación estándar del cierre",
        "descripcion": "Volatilidad simple de precios medida como desviación estándar del cierre.",
        "sql": """
            SELECT
                ticker,
                ROUND(STDDEV(close), 4) AS desviacion_cierre,
                ROUND(AVG(close), 2) AS cierre_promedio,
                COUNT(*) AS registros
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY desviacion_cierre DESC
        """,
    },
    "minimos_maximos": {
        "titulo": "Mínimos y máximos históricos",
        "descripcion": "Rango completo observado para cada activo dentro de la tabla cloud.",
        "sql": """
            SELECT
                ticker,
                ROUND(MIN(close), 2) AS minimo,
                ROUND(MAX(close), 2) AS maximo,
                ROUND(MAX(close) - MIN(close), 2) AS rango
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY rango DESC
        """,
    },
    "top_5_ultimo_cierre": {
        "titulo": "Top 5 por último cierre",
        "descripcion": "Activos con mayor precio en la fecha más reciente disponible.",
        "sql": """
            WITH ultimos AS (
                SELECT ticker, MAX(fecha) AS fecha
                FROM risklab_prices
                GROUP BY ticker
            )
            SELECT
                p.ticker,
                p.fecha,
                ROUND(p.close, 2) AS ultimo_cierre
            FROM risklab_prices p
            INNER JOIN ultimos u
                ON p.ticker = u.ticker AND p.fecha = u.fecha
            ORDER BY ultimo_cierre DESC
            LIMIT 5
        """,
    },
    "menor_fluctuacion_mes": {
        "titulo": "Menor fluctuación en el último mes",
        "descripcion": "Activos con menor rango porcentual aproximado en los últimos 30 días.",
        "sql": """
            SELECT
                ticker,
                ROUND((MAX(close) - MIN(close)) / AVG(close) * 100, 2) AS fluctuacion_pct,
                ROUND(MIN(close), 2) AS minimo_30d,
                ROUND(MAX(close), 2) AS maximo_30d
            FROM risklab_prices
            WHERE fecha >= DATE_SUB((SELECT MAX(fecha) FROM risklab_prices), 30)
            GROUP BY ticker
            ORDER BY fluctuacion_pct ASC
            LIMIT 5
        """,
    },
    "mayor_volumen_promedio": {
        "titulo": "Mayor volumen promedio",
        "descripcion": "Ranking de liquidez aproximada por volumen negociado promedio.",
        "sql": """
            SELECT
                ticker,
                ROUND(AVG(volume), 0) AS volumen_promedio,
                ROUND(MAX(volume), 0) AS volumen_maximo
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY volumen_promedio DESC
            LIMIT 10
        """,
    },
    "rendimiento_periodo": {
        "titulo": "Rendimiento del periodo",
        "descripcion": "Variación porcentual entre el primer y último cierre disponible.",
        "sql": """
            WITH ordenado AS (
                SELECT
                    ticker,
                    fecha,
                    close,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fecha ASC) AS rn_asc,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fecha DESC) AS rn_desc
                FROM risklab_prices
            ),
            extremos AS (
                SELECT
                    ticker,
                    MAX(CASE WHEN rn_asc = 1 THEN close END) AS cierre_inicial,
                    MAX(CASE WHEN rn_desc = 1 THEN close END) AS cierre_final
                FROM ordenado
                GROUP BY ticker
            )
            SELECT
                ticker,
                ROUND(cierre_inicial, 2) AS cierre_inicial,
                ROUND(cierre_final, 2) AS cierre_final,
                ROUND((cierre_final / cierre_inicial - 1) * 100, 2) AS rendimiento_pct
            FROM extremos
            ORDER BY rendimiento_pct DESC
        """,
    },
    "ultimo_mes_retorno": {
        "titulo": "Retorno acumulado del último mes",
        "descripcion": "Cambio entre el primer y último cierre dentro de los últimos 30 días.",
        "sql": """
            WITH base AS (
                SELECT *
                FROM risklab_prices
                WHERE fecha >= DATE_SUB((SELECT MAX(fecha) FROM risklab_prices), 30)
            ),
            ordenado AS (
                SELECT
                    ticker,
                    fecha,
                    close,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fecha ASC) AS rn_asc,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fecha DESC) AS rn_desc
                FROM base
            ),
            extremos AS (
                SELECT
                    ticker,
                    MAX(CASE WHEN rn_asc = 1 THEN close END) AS cierre_inicial,
                    MAX(CASE WHEN rn_desc = 1 THEN close END) AS cierre_final
                FROM ordenado
                GROUP BY ticker
            )
            SELECT
                ticker,
                ROUND((cierre_final / cierre_inicial - 1) * 100, 2) AS retorno_30d_pct,
                ROUND(cierre_inicial, 2) AS cierre_inicial_30d,
                ROUND(cierre_final, 2) AS cierre_final_30d
            FROM extremos
            ORDER BY retorno_30d_pct DESC
        """,
    },
    "dias_disponibles": {
        "titulo": "Cobertura de datos por activo",
        "descripcion": "Cantidad de observaciones y rango de fechas disponible por ticker.",
        "sql": """
            SELECT
                ticker,
                COUNT(*) AS dias_disponibles,
                MIN(fecha) AS fecha_inicial,
                MAX(fecha) AS fecha_final
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY dias_disponibles DESC, ticker
        """,
    },
    "brecha_high_low": {
        "titulo": "Rango intradía promedio",
        "descripcion": "Promedio de la brecha high-low diaria como aproximación de fluctuación intradía.",
        "sql": """
            SELECT
                ticker,
                ROUND(AVG(high - low), 3) AS rango_intradia_promedio,
                ROUND(AVG((high - low) / close) * 100, 3) AS rango_intradia_pct
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY rango_intradia_pct ASC
        """,
    },
}


class DatabricksService:
    def __init__(self):
        self.settings = get_settings()

    def configurado(self) -> bool:
        return bool(
            self.settings.databricks_server_hostname
            and self.settings.databricks_http_path
            and self.settings.databricks_token
        )

    def _connect(self):
        if not self.configurado():
            raise RuntimeError("Credenciales de Databricks no configuradas en backend/.env")

        return sql.connect(
            server_hostname=self.settings.databricks_server_hostname,
            http_path=self.settings.databricks_http_path,
            access_token=self.settings.databricks_token,
        )

    def probar_conexion(self) -> dict:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 AS conectado")
                row = cursor.fetchone()
        return {
            "conectado": bool(row and row.conectado == 1),
            "warehouse": self.settings.databricks_http_path,
        }

    def resumen_precios(self) -> list[dict]:
        query = """
            SELECT
                ticker,
                COUNT(*) AS registros,
                MIN(fecha) AS fecha_inicial,
                MAX(fecha) AS fecha_final,
                ROUND(AVG(close), 2) AS precio_promedio,
                ROUND(MIN(close), 2) AS precio_minimo,
                ROUND(MAX(close), 2) AS precio_maximo
            FROM risklab_prices
            GROUP BY ticker
            ORDER BY ticker
        """
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return [
            {
                "ticker": row.ticker,
                "registros": int(row.registros),
                "fecha_inicial": str(row.fecha_inicial),
                "fecha_final": str(row.fecha_final),
                "precio_promedio": float(row.precio_promedio),
                "precio_minimo": float(row.precio_minimo),
                "precio_maximo": float(row.precio_maximo),
            }
            for row in rows
        ]

    def consultas_predefinidas(self) -> list[dict]:
        return [
            {
                "id": consulta_id,
                "titulo": datos["titulo"],
                "descripcion": datos["descripcion"],
                "sql": datos["sql"].strip(),
            }
            for consulta_id, datos in CONSULTAS_PREDEFINIDAS.items()
        ]

    def ejecutar_consulta(self, consulta_id: str) -> dict:
        if consulta_id not in CONSULTAS_PREDEFINIDAS:
            raise ValueError(f"Consulta predefinida no existe: {consulta_id}")

        consulta = CONSULTAS_PREDEFINIDAS[consulta_id]
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(consulta["sql"])
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()

        resultados = []
        for row in rows:
            item = {}
            for col, value in zip(columns, row):
                item[col] = str(value) if hasattr(value, "isoformat") else value
            resultados.append(item)

        return {
            "id": consulta_id,
            "titulo": consulta["titulo"],
            "descripcion": consulta["descripcion"],
            "sql": consulta["sql"].strip(),
            "resultados": resultados,
        }
