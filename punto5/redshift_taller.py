import os
import time
from pathlib import Path

import boto3

# --- Configuración (ninguno de estos valores es una contraseña) ---
REGION = "us-east-1"
WORKGROUP = "taller-wg"
DATABASE = "dev"
BUCKET = os.environ["REDSHIFT_BUCKET"]          # nombre de tu bucket
SECRET_ARN = os.environ["REDSHIFT_SECRET_ARN"]  # ARN del secreto (no su valor)

CARPETA = Path(__file__).parent  # busca los CSV junto al script
ARCHIVOS = ["clientes.csv", "pedidos.csv"]

s3 = boto3.client("s3", region_name=REGION)
rsd = boto3.client("redshift-data", region_name=REGION)


def run(sql, descripcion=""):
    """Envía SQL con la Data API, espera a que termine y devuelve filas si las hay."""
    resp = rsd.execute_statement(
        WorkgroupName=WORKGROUP,
        Database=DATABASE,
        SecretArn=SECRET_ARN,  # la Data API lee el secreto; la contraseña nunca pasa por aquí
        Sql=sql,
    )
    sid = resp["Id"]

    while True:
        d = rsd.describe_statement(Id=sid)
        if d["Status"] in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1)

    if d["Status"] != "FINISHED":
        raise RuntimeError(f"{descripcion} falló: {d.get('Error')}")

    print(f"✔ {descripcion} ({d['Duration'] / 1e9:.2f} s)")

    if not d.get("HasResultSet"):
        return None

    res = rsd.get_statement_result(Id=sid)
    columnas = [c["name"] for c in res["ColumnMetadata"]]
    filas = [[list(campo.values())[0] for campo in fila] for fila in res["Records"]]
    return columnas, filas


def mostrar(resultado):
    columnas, filas = resultado
    print("   " + " | ".join(columnas))
    for fila in filas:
        print("   " + " | ".join(str(v) for v in fila))
    print()


# 1. Subir los archivos a S3
for archivo in ARCHIVOS:
    s3.upload_file(str(CARPETA / archivo), BUCKET, f"datos/{archivo}")
    print(f"✔ Subido s3://{BUCKET}/datos/{archivo}")

# 2. Crear las tablas (se borran primero para poder ejecutar el script varias veces)
run("DROP TABLE IF EXISTS pedidos", "Borrar tabla pedidos")
run("DROP TABLE IF EXISTS clientes", "Borrar tabla clientes")

run("""
CREATE TABLE clientes (
    id_cliente INT PRIMARY KEY,
    nombre     VARCHAR(60),
    ciudad     VARCHAR(40),
    segmento   VARCHAR(20)
)""", "Crear tabla clientes")

run("""
CREATE TABLE pedidos (
    id_pedido  INT PRIMARY KEY,
    id_cliente INT REFERENCES clientes(id_cliente),
    fecha      DATE,
    categoria  VARCHAR(30),
    valor      BIGINT
)""", "Crear tabla pedidos")

# 3. Cargar los datos con COPY (Redshift lee S3 usando el rol IAM por defecto)
for tabla in ["clientes", "pedidos"]:
    run(f"""
    COPY {tabla}
    FROM 's3://{BUCKET}/datos/{tabla}.csv'
    IAM_ROLE default
    FORMAT AS CSV
    IGNOREHEADER 1
    """, f"COPY {tabla}")

# 4. Verificar la carga
print()
mostrar(run("""
SELECT 'clientes' AS tabla, COUNT(*) AS registros FROM clientes
UNION ALL
SELECT 'pedidos', COUNT(*) FROM pedidos
""", "Conteo de registros"))

# 5. Consulta con FILTRO: pedidos de más de $1.000.000
mostrar(run("""
SELECT id_pedido, id_cliente, fecha, categoria, valor
FROM pedidos
WHERE valor > 1000000
ORDER BY valor DESC
""", "Consulta 1 - Filtro: pedidos mayores a $1.000.000"))

# 6. Consulta con UNIÓN + AGREGACIÓN: ventas por ciudad
mostrar(run("""
SELECT c.ciudad,
       COUNT(p.id_pedido)  AS num_pedidos,
       SUM(p.valor)        AS total_ventas,
       ROUND(AVG(p.valor)) AS ticket_promedio
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
GROUP BY c.ciudad
ORDER BY total_ventas DESC
""", "Consulta 2 - JOIN + agregación: ventas por ciudad"))

# 7. Consulta con UNIÓN + AGREGACIÓN + FILTRO: ventas por segmento y categoría
mostrar(run("""
SELECT c.segmento,
       p.categoria,
       COUNT(*)     AS num_pedidos,
       SUM(p.valor) AS total_ventas
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
GROUP BY c.segmento, p.categoria
HAVING SUM(p.valor) > 500000
ORDER BY c.segmento, total_ventas DESC
""", "Consulta 3 - JOIN + agregación + HAVING: segmento y categoría"))