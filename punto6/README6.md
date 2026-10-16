# Punto 6 - AWS Glue Data Catalog

Region: us-east-1

## Qué es Glue Data Catalog

Glue Data Catalog guarda metadatos, no datos. Por cada tabla guarda las columnas y sus tipos, en qué carpeta de S3 están los archivos, el formato (CSV, delimitador, si tiene encabezado) y algunas estadísticas como cuántos archivos hay. Los datos de verdad siguen en S3 como archivos normales.

Esto se vio en el taller: el catálogo decía que había 18 registros (es una estimación que hace con el tamaño del archivo), pero Athena contó los 20 reales porque lee el archivo directamente.

La base de datos es solo un contenedor para agrupar tablas (taller_db). La tabla es la definición del esquema y de dónde están los datos, que es lo que Athena usa para saber cómo leer los archivos. El crawler es un proceso que revisa una carpeta de S3, mira los archivos, adivina el esquema y crea o actualiza la tabla solo.

## Datos

ventas.csv con 20 registros (id_venta, fecha, ciudad, codigo_postal, producto, categoria, cantidad, precio_unitario) y ventas_nuevas.csv con 5 registros más con la misma estructura, para probar lo de agregar registros.

## Paso a paso

1. Crear el bucket jero-glue-taller-2026 con dos carpetas: ventas/ y athena-results/. Subir ventas.csv a ventas/.
2. En Glue crear la base de datos taller_db.
3. Crear el crawler ventas-crawler apuntando a s3://jero-glue-taller-2026/ventas/, con un rol nuevo (AWSGlueServiceRole-taller), destino taller_db y ejecución On demand. Correrlo con Run crawler.
4. Revisar el esquema de la tabla ventas y corregir los tipos (ver abajo).
5. En Athena poner como ubicación de resultados s3://jero-glue-taller-2026/athena-results/, escoger taller_db y correr las consultas.
6. Subir ventas_nuevas.csv a la misma carpeta ventas/ y volver a contar en Athena.
7. Editar el crawler para que en cambios de esquema solo agregue columnas nuevas (Add new columns only) y correrlo otra vez.
8. Crear la tabla manual desde Athena para comparar.
9. Borrar todo (ver abajo).

## Esquema inferido y correcciones

El crawler creó la tabla ventas como CSV con LazySimpleSerDe. Casi todo quedó bien menos dos columnas:

| columna | lo que puso el crawler | lo que se dejó | por qué |
|---|---|---|---|
| codigo_postal | bigint | string | como número se pierde el cero del inicio (050021 queda 50021) y además es un código, no algo que se sume |
| fecha | string | date | para poder filtrar por fechas sin tener que convertir en cada consulta |

Se corrigió con Edit schema y se guardó como nueva versión de la tabla.

## Consultas en Athena

Conteo:

```sql
SELECT COUNT(*) AS total_registros FROM ventas;
```

Dio 20, y escaneó 1.18 KB.

Revisar que los códigos postales quedaron con el cero:

```sql
SELECT DISTINCT ciudad, codigo_postal FROM ventas ORDER BY ciudad;
```

Filtro: ventas de Tecnologia desde el 5 de septiembre

```sql
SELECT id_venta, fecha, ciudad, producto, cantidad * precio_unitario AS total_venta
FROM ventas
WHERE categoria = 'Tecnologia' AND fecha >= DATE '2026-09-05'
ORDER BY total_venta DESC;
```

| id_venta | ciudad | producto | total_venta |
|---|---|---|---|
| 17 | Bogota | Portatil | 5200000 |
| 11 | Cali | Celular | 1900000 |
| 14 | Barranquilla | Tablet | 1200000 |
| 20 | Cali | Monitor | 780000 |
| 15 | Medellin | Mouse | 300000 |

Agrupación: ventas por ciudad

```sql
SELECT ciudad, COUNT(*) AS num_ventas, SUM(cantidad * precio_unitario) AS total_ventas
FROM ventas
GROUP BY ciudad
ORDER BY total_ventas DESC;
```

| ciudad | num_ventas | total_ventas |
|---|---|---|
| Bogota | 5 | 7830000 |
| Medellin | 6 | 5000000 |
| Barranquilla | 4 | 3350000 |
| Cali | 5 | 3290000 |

## Agregar registros y actualizar el catálogo

Al subir ventas_nuevas.csv a la misma carpeta, Athena ya contaba 25 registros sin correr el crawler, porque la tabla apunta a la carpeta y lee todos los archivos que haya ahi.

Antes de volver a correr el crawler se cambió su configuración a "Add new columns only", porque con la configuración por defecto puede volver a cambiar los tipos y dañar las correcciones (por ejemplo volver a poner codigo_postal como bigint). Despues de correrlo el esquema siguió igual con las correcciones y el número de archivos subió a 2.

Ventas por ciudad con los registros nuevos:

| ciudad | num_ventas | total_ventas |
|---|---|---|
| Bogota | 6 | 8470000 |
| Barranquilla | 5 | 6100000 |
| Medellin | 8 | 5530000 |
| Cali | 6 | 3890000 |

Barranquilla subió al segundo lugar por un portatil nuevo de $2.750.000.

O sea el crawler solo hace falta cuando cambia la estructura de los datos (columnas o particiones nuevas), no cuando llegan más archivos con el mismo formato.

## Crawler vs tabla manual

La tabla manual se creó desde Athena:

```sql
CREATE EXTERNAL TABLE ventas_manual (
  id_venta BIGINT,
  fecha DATE,
  ciudad STRING,
  codigo_postal STRING,
  producto STRING,
  categoria STRING,
  cantidad BIGINT,
  precio_unitario BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LOCATION 's3://jero-glue-taller-2026/ventas/'
TBLPROPERTIES ('skip.header.line.count' = '1');
```

Leyó los mismos 25 registros y apareció en Glue al lado de la otra tabla, o sea que crear la tabla desde Athena también la guarda en el catálogo.

El crawler es automático y sirve cuando no conoces el esquema o tienes muchas tablas que cambian, pero se puede equivocar en los tipos, se cobra cada vez que corre y si no lo configuras bien te puede sobrescribir las correcciones. La tabla manual te deja poner los tipos correctos desde el inicio y no cuesta nada, pero toca saber el esquema y actualizarla a mano si cambian los datos. Para este caso con un solo archivo que ya conocíamos, la tabla manual hubiera sido suficiente.

## Credenciales

Este punto no necesita ninguna credencial de aplicación. Solo se usó S3, Glue y Athena, y todo funciona con permisos IAM: el crawler usa su rol para leer S3 y escribir en el catálogo, y Athena usa los permisos del usuario. Como no hay ninguna base de datos con usuario y contraseña, no hay nada que guardar en Secrets Manager. Solo haría falta si se usara una conexión de Glue a una base de datos externa, por ejemplo por JDBC a RDS.

## Costos

El crawler se cobra por DPU-hora (unos $0.44), por segundo pero con mínimo de 10 minutos cada vez que corre. Lo corrimos 2 veces, entonces unos $0.15. El catálogo es gratis hasta un millón de objetos, entonces $0. S3 cobra por GB-mes y por solicitudes, y con unos pocos KB es practicamente $0. Athena cobra por datos escaneados (unos $5 por TB) con un mínimo de 10 MB por consulta, y las consultas que crean tablas no se cobran. Hicimos unas 10 consultas, que serían menos de $0.01. En total menos de $0.25.

El volumen de datos examinados es lo que define el costo de Athena: si escaneas el doble, pagas el doble. Con CSV Athena tiene que leer el archivo completo aunque uses una sola columna. Con datos grandes se baja el costo usando formatos como Parquet (que solo lee las columnas que necesitas), particionando por fecha o ciudad, y no usando SELECT *. En el taller cada consulta escaneó como 1 o 2 KB, entonces siempre se cobró el mínimo de 10 MB. En el crawler, más archivos y carpetas significa que se demora más y cuesta más.

## Eliminación

1. Se borraron las tablas ventas y ventas_manual.
2. Se borró la base de datos taller_db.
3. Se borró el crawler.
4. Se vació y borró el bucket (con los resultados de Athena).
5. Se borró el rol AWSGlueServiceRole-taller y su política.
6. Se revisó Billing.
