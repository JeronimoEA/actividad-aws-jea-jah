import boto3

# Endpoint del clúster (no es un secreto, pero no subas capturas con tu ID de cuenta)
ENDPOINT = "https://db-neptune-taller-test.cluster-cwrm6ucw8121.us-east-1.neptune.amazonaws.com:8182"

# boto3 firma cada petición con IAM (SigV4) usando las credenciales de 'aws configure'
client = boto3.client("neptunedata", endpoint_url=ENDPOINT, region_name="us-east-1")

def q(cypher):
    return client.execute_open_cypher_query(openCypherQuery=cypher)["results"]

# 0. Probar conexión
print("Estado:", client.get_engine_status()["status"])

# 1. Limpiar el grafo (para poder ejecutar el script varias veces sin duplicar)
q("MATCH (n) DETACH DELETE n")

# 2. Insertar 10 vértices y 15 relaciones
q("""
CREATE
  (ana:Estudiante {nombre:'Ana'}),
  (luis:Estudiante {nombre:'Luis'}),
  (sara:Estudiante {nombre:'Sara'}),
  (juan:Estudiante {nombre:'Juan'}),
  (mia:Estudiante {nombre:'Mia'}),
  (bi:Curso {nombre:'BI'}),
  (ing:Curso {nombre:'Ing Datos'}),
  (est:Curso {nombre:'Estadistica'}),
  (gomez:Profesor {nombre:'Gomez'}),
  (ruiz:Profesor {nombre:'Ruiz'}),

  (ana)-[:INSCRITO]->(bi),
  (ana)-[:INSCRITO]->(ing),
  (luis)-[:INSCRITO]->(bi),
  (luis)-[:INSCRITO]->(est),
  (sara)-[:INSCRITO]->(ing),
  (juan)-[:INSCRITO]->(est),
  (mia)-[:INSCRITO]->(bi),
  (mia)-[:INSCRITO]->(ing),

  (gomez)-[:DICTA]->(bi),
  (gomez)-[:DICTA]->(ing),
  (ruiz)-[:DICTA]->(est),

  (ana)-[:AMIGO_DE]->(luis),
  (luis)-[:AMIGO_DE]->(juan),
  (juan)-[:AMIGO_DE]->(sara),
  (sara)-[:AMIGO_DE]->(mia)
""")

# 3. Verificar conteos
print("Vértices:", q("MATCH (n) RETURN count(n) AS total"))
print("Relaciones:", q("MATCH ()-[r]->() RETURN count(r) AS total"))

# 4. Consulta 1: ¿Con quién comparte curso Ana?
print("\nConsulta 1 - Compañeros de Ana:")
for r in q("""
MATCH (:Estudiante {nombre:'Ana'})-[:INSCRITO]->(c:Curso)<-[:INSCRITO]-(otro:Estudiante)
RETURN otro.nombre AS companero, c.nombre AS curso
"""):
    print(" ", r)

# 5. Consulta 2: ¿Qué profesores les dictan a los amigos de Luis?
print("\nConsulta 2 - Profesores de los amigos de Luis:")
for r in q("""
MATCH (:Estudiante {nombre:'Luis'})-[:AMIGO_DE]->(amigo)-[:INSCRITO]->(c)<-[:DICTA]-(p:Profesor)
RETURN amigo.nombre AS amigo, c.nombre AS curso, p.nombre AS profesor
"""):
    print(" ", r)

# 6. Consulta 3: ¿A quién llega Ana por cadenas de amistad de 2 a 3 saltos?
print("\nConsulta 3 - Amigos de amigos de Ana:")
for r in q("""
MATCH (:Estudiante {nombre:'Ana'})-[:AMIGO_DE*2..3]->(x:Estudiante)
RETURN DISTINCT x.nombre AS alcanzable
"""):
    print(" ", r)