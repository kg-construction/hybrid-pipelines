import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
from rdflib import Graph, Namespace, URIRef, Literal

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

ROOT = Path(__file__).resolve().parents[1]
RDF_PATH = ROOT / "data" / "acm-ccs.ttl"

RDF_FORMAT = "turtle"
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

BATCH_SIZE = 500


def neo4j_exec(driver, query, params=None):
    with driver.session() as sess:
        return sess.run(query, params or {}).consume()


def main():
    if not RDF_PATH.exists():
        raise FileNotFoundError(f"RDF not found: {RDF_PATH}")

    g = Graph()
    g.parse(str(RDF_PATH), format=RDF_FORMAT)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        try:
            neo4j_exec(driver, "CREATE CONSTRAINT concept_uri IF NOT EXISTS FOR (c:Concept) REQUIRE c.uri IS UNIQUE")
            print("[OK] Constraint :Concept(uri) unique")
        except Exception as e:
            print("[WARN] Could not create constraint (version/syntax). Continuing.")
            print("       Reason:", str(e))

        pref = {}
        for s, _, o in g.triples((None, SKOS.prefLabel, None)):
            if isinstance(s, URIRef) and isinstance(o, Literal):
                # Prioriza inglês, mas pega qualquer se não tiver @en
                lang = (o.language or "").lower()
                val = str(o)
                if s not in pref or (lang == "en" and pref[s][0] != "en"):
                    pref[s] = (lang, val)

        subjects = set()
        for s, _, _ in g.triples((None, SKOS.prefLabel, None)):
            if isinstance(s, URIRef):
                subjects.add(str(s))
        for s, _, o in g.triples((None, SKOS.broader, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                subjects.add(str(s))
                subjects.add(str(o))
        for s, _, o in g.triples((None, SKOS.narrower, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                subjects.add(str(s))
                subjects.add(str(o))

        subjects = list(subjects)
        print(f"[INFO] Total concept URIs to MERGE: {len(subjects)}")

        merge_nodes_cypher = """
        UNWIND $rows AS row
        MERGE (c:Concept {uri: row.uri})
        SET c.prefLabel = coalesce(row.prefLabel, c.prefLabel)
        """

        rows = []
        for uri in subjects:
            pl = None
            if URIRef(uri) in pref:
                pl = pref[URIRef(uri)][1]
            rows.append({"uri": uri, "prefLabel": pl})

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i+BATCH_SIZE]
            neo4j_exec(driver, merge_nodes_cypher, {"rows": batch})
        print("[OK] Nodes merged")

        broader_pairs = []
        for s, _, o in g.triples((None, SKOS.broader, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                broader_pairs.append({"child": str(s), "parent": str(o)})

        narrower_pairs = []
        for s, _, o in g.triples((None, SKOS.narrower, None)):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                narrower_pairs.append({"parent": str(s), "child": str(o)})

        print(f"[INFO] broader edges: {len(broader_pairs)} | narrower edges: {len(narrower_pairs)}")

        create_broader_cypher = """
        UNWIND $pairs AS p
        MATCH (child:Concept {uri: p.child})
        MATCH (parent:Concept {uri: p.parent})
        MERGE (child)-[:SKOS_BROADER]->(parent)
        """

        create_narrower_cypher = """
        UNWIND $pairs AS p
        MATCH (parent:Concept {uri: p.parent})
        MATCH (child:Concept {uri: p.child})
        MERGE (parent)-[:SKOS_NARROWER]->(child)
        """

        for i in range(0, len(broader_pairs), BATCH_SIZE):
            neo4j_exec(driver, create_broader_cypher, {"pairs": broader_pairs[i:i+BATCH_SIZE]})
        print("[OK] SKOS_BROADER edges created")

        for i in range(0, len(narrower_pairs), BATCH_SIZE):
            neo4j_exec(driver, create_narrower_cypher, {"pairs": narrower_pairs[i:i+BATCH_SIZE]})
        print("[OK] SKOS_NARROWER edges created")

        print("\n[DONE] Now your shortest-path step can run.")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
