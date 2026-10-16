# Punto 5 - Amazon Redshift

Region: us-east-1

## Qué es Redshift y comparación con RDS

Redshift es el data warehouse administrado de AWS. Está pensado para análisis OLAP. Guarda los datos en formato columnar, lo que permite leer solo las columnas que usa una consulta y comprimirlas mejor, y procesa en paralelo (MPP), repartiendo el trabajo entre varios nodos.

En la versión aprovisionada, un clúster tiene un nodo líder, que recibe las consultas, arma el plan de ejecución y combina los resultados, y nodos de cómputo, divididos en slices que procesan en paralelo cada parte de los datos. En Serverless no se administran nodos: el namespace agrupa los objetos de la base de datos (tablas, esquemas, usuarios, la contraseña del admin y los roles IAM asociados) y el workgroup agrupa el cómputo (capacidad en RPU, red y security groups).

RDS es una base de datos relacional transaccional (OLTP), optimizada para muchas operaciones pequeñas y rápidas sobre filas individuales: insertar un pedido, actualizar un saldo, consultar un usuario por su ID. Redshift está optimizado para pocas consultas pesadas que agregan millones de filas. Elegiría RDS como base de datos de una aplicación de comercio, donde cada compra se registra en tiempo real. Elegiría Redshift para el área de BI de esa misma empresa, que carga periódicamente el histórico de ventas para analizar ingresos por ciudad, categoría y mes, como hicimos en las consultas del taller.

## Serverless vs aprovisionado

Usamos Serverless con la capacidad base minima (4 RPU). Un cluster aprovisionado cobra todas las horas que esté creado aunque no haga nada, y en el taller casi todo el tiempo se va configurando y no consultando. Con Serverless el cómputo solo se cobra mientras hay consultas corriendo.

La contraseña del admin se configuró con la opción "Manage admin credentials in AWS Secrets Manager", entonces Redshift la genera y la guarda en Secrets Manager. El programa solo usa el ARN del secreto, nunca la contraseña.

## Datos

Dos tablas relacionadas de ventas:

- clientes.csv (10 registros): id_cliente, nombre, ciudad, segmento (Persona o Empresa).
- pedidos.csv (20 registros): id_pedido, id_cliente, fecha, categoria, valor (en pesos).

Se relacionan por id_cliente, un cliente puede tener varios pedidos.

## Paso a paso

1. Crear un bucket de S3 (jero-redshift-taller-2026) con el acceso público bloqueado.
2. Crear el rol rol-redshift-s3 en IAM: servicio Redshift (Redshift - Customizable) con la política AmazonS3ReadOnlyAccess.
3. Crear Redshift Serverless: workgroup taller-wg con 4 RPU en la VPC default, y namespace taller-ns con la base dev, usuario admin y la contraseña administrada en Secrets Manager. Asociar rol-redshift-s3 y ponerlo como default.
4. Darle permisos a user_cli con la política de abajo (usa el ARN del workgroup y el ARN del secreto).
5. Configurar las credenciales de user_cli con `aws configure` e instalar boto3.
6. Poner los csv en la misma carpeta que el script y definir las variables de entorno:

```bash
export REDSHIFT_BUCKET="jero-redshift-taller-2026"
export REDSHIFT_SECRET_ARN='arn:aws:secretsmanager:us-east-1:<ID_CUENTA>:secret:redshift!taller-ns-admin-XXXXXX'
```

(el ARN va con comillas simples porque en zsh el ! da problemas con comillas dobles)

7. Correr `python redshift_taller.py`. El script sube los csv a S3, crea las tablas, las carga con COPY y corre las consultas usando la Data API (execute_statement para mandar el SQL, describe_statement para ver si terminó y get_statement_result para traer los resultados).
8. Borrar todo (ver abajo).

Política de user_cli:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["redshift-data:ExecuteStatement", "redshift-data:BatchExecuteStatement"],
      "Resource": "arn:aws:redshift-serverless:us-east-1:<ID_CUENTA>:workgroup/<ID_WORKGROUP>"
    },
    {
      "Effect": "Allow",
      "Action": [
        "redshift-data:DescribeStatement",
        "redshift-data:GetStatementResult",
        "redshift-data:ListStatements",
        "redshift-data:CancelStatement"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:<ID_CUENTA>:secret:redshift!taller-ns-admin-XXXXXX"
    }
  ]
}
```

El primer bloque solo deja mandar SQL al workgroup del taller, el segundo deja ver el estado y los resultados de las consultas, y el tercero deja leer únicamente el secreto de Redshift. Subir archivos a S3 ya lo cubría la política AmazonS3FullAccess que tenía user_cli.

Instrucciones de carga:

```sql
COPY clientes FROM 's3://jero-redshift-taller-2026/datos/clientes.csv'
IAM_ROLE default FORMAT AS CSV IGNOREHEADER 1;

COPY pedidos FROM 's3://jero-redshift-taller-2026/datos/pedidos.csv'
IAM_ROLE default FORMAT AS CSV IGNOREHEADER 1;
```

Se cargaron 10 clientes y 20 pedidos.

## Consultas y resultados

1. Filtro: pedidos de más de $1.000.000

```sql
SELECT id_pedido, id_cliente, fecha, categoria, valor
FROM pedidos
WHERE valor > 1000000
ORDER BY valor DESC;
```

| id_pedido | id_cliente | fecha | categoria | valor |
|---|---|---|---|---|
| 108 | 2 | 2026-07-20 | Tecnologia | 3400000 |
| 104 | 4 | 2026-07-10 | Tecnologia | 2890000 |
| 118 | 8 | 2026-08-21 | Tecnologia | 2150000 |
| 111 | 9 | 2026-08-01 | Tecnologia | 1750000 |
| 101 | 1 | 2026-07-03 | Tecnologia | 1250000 |
| 114 | 3 | 2026-08-09 | Tecnologia | 1100000 |

Responde cuáles son los pedidos grandes. Son 6 de 20 y todos son de Tecnologia, y los 3 más grandes son de clientes tipo Empresa.

2. Join + agregación: ventas por ciudad

```sql
SELECT c.ciudad, COUNT(p.id_pedido) AS num_pedidos,
       SUM(p.valor) AS total_ventas, ROUND(AVG(p.valor)) AS ticket_promedio
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
GROUP BY c.ciudad
ORDER BY total_ventas DESC;
```

| ciudad | num_pedidos | total_ventas | ticket_promedio |
|---|---|---|---|
| Bogota | 7 | 7330000 | 1047142 |
| Medellin | 6 | 5990000 | 998333 |
| Cali | 4 | 4190000 | 1047500 |
| Barranquilla | 3 | 1343000 | 447666 |

Responde qué ciudad vende más y cuánto vale un pedido típico. Bogotá es la que más vende (casi 39% del total), sobre todo por un cliente empresa. Cali tiene pocos pedidos pero un ticket igual de alto que Bogotá, y Barranquilla es la más baja en todo.

3. Join + agregación + HAVING: ventas por segmento y categoría (solo las que pasan de $500.000)

```sql
SELECT c.segmento, p.categoria, COUNT(*) AS num_pedidos, SUM(p.valor) AS total_ventas
FROM pedidos p
JOIN clientes c ON c.id_cliente = p.id_cliente
GROUP BY c.segmento, p.categoria
HAVING SUM(p.valor) > 500000
ORDER BY c.segmento, total_ventas DESC;
```

| segmento | categoria | num_pedidos | total_ventas |
|---|---|---|---|
| Empresa | Tecnologia | 4 | 10190000 |
| Empresa | Oficina | 4 | 2520000 |
| Empresa | Hogar | 1 | 540000 |
| Persona | Tecnologia | 4 | 4090000 |
| Persona | Hogar | 5 | 1340000 |

Empresa - Tecnologia es más de la mitad de las ventas (54%) con solo 4 pedidos. Las personas compran más seguido cosas de Hogar pero de poco valor. Persona - Oficina no aparece porque solo suma $173.000.

Algo que se notó: el primer comando y los COPY se demoraron entre 10 y 27 segundos, y las consultas menos de 2. Es porque Serverless se tiene que "despertar" con la primera instrucción.

## Costos

Serverless es la que cuesta menos para esta práctica: el cómputo solo se cobra durante los segundos en que hay consultas activas, mientras que el aprovisionado cobraría todas las horas que el clúster estuviera creado.

En Serverless, el cómputo se cobra en RPU-horas, medidas por segundo con un mínimo de 60 segundos cada vez que se activa. Con 4 RPU en us-east-1 son aproximadamente $1.50 por hora de cómputo activo. El almacenamiento se cobra aparte por GB-mes, y con 30 registros es practicamente $0. El secreto cuesta unos $0.40 al mes (prorrateado). En total la práctica costó menos de $0.50.

¿Qué recursos podrían seguir generando cargos después de ejecutar las consultas? El almacenamiento del namespace mientras exista, los snapshots o puntos de recuperación que se conserven, el secreto en Secrets Manager mientras no se borre, los archivos en el bucket de S3, y el cómputo si alguna sesión queda activa (por ejemplo, Query Editor v2 abierto ejecutando algo).

## Eliminación

1. Se borró el workgroup taller-wg.
2. Se borró el namespace taller-ns sin snapshot final (con eso se borra el secreto también, se revisó en Secrets Manager).
3. Se revisó que no quedaran snapshots.
4. Se vació y borró el bucket.
5. Se borró el rol rol-redshift-s3 y se quitó la política de user_cli.
6. Se revisó Billing.
