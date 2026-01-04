"""
Pre-process ACM CCS RDF/XML to fix malformed namespaces and emit Turtle.
Usage:
    python scripts/pre-process.py
"""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
INPUT_RDF = ROOT / "data" / "acm-css.rdf"
FIXED_RDF = ROOT / "data" / "acm-ccs-fixed.rdf"
FIXED_TTL = ROOT / "data" / "acm-ccs.ttl"


def preprocess_rdf_xml(src_path: Path, dst_path: Path) -> None:
    if not src_path.exists():
        raise FileNotFoundError(f"Input file not found: {src_path}")

    lines = src_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        raise ValueError("Input RDF file is empty")

    # Replace the first line with clean RDF root + namespaces (fix malformed xmlns)
    lines[0] = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:skos="http://www.w3.org/2004/02/skos/core#" '
        'xmlns:skosxl="http://www.w3.org/2008/05/skos-xl#">'
    )

    txt = "\n".join(lines)

    # RDF/XML expects xml:lang, not lang
    txt = re.sub(r'\slang="([^"]+)"', r' xml:lang="\1"', txt)

    dst_path.write_text(txt, encoding="utf-8")
    print(f"[OK] Wrote fixed RDF/XML: {dst_path}")


def convert_to_turtle(rdf_xml_path: Path, ttl_path: Path) -> None:
    g = Graph()
    g.parse(str(rdf_xml_path), format="xml")  # RDF/XML
    g.serialize(destination=str(ttl_path), format="turtle")
    print(f"[OK] Wrote Turtle: {ttl_path}")


def main() -> None:
    preprocess_rdf_xml(INPUT_RDF, FIXED_RDF)
    convert_to_turtle(FIXED_RDF, FIXED_TTL)


if __name__ == "__main__":
    main()
