# Pre-process Script

## Overview

The `pre-process.py` script pre-processes ACM CCS RDF/XML files to fix malformed namespaces and converts them to Turtle format. This is a necessary step before importing the RDF data into Neo4j.

## Purpose

The script performs two main operations:
1. **Fixes malformed RDF/XML**: Corrects namespace declarations and language attributes in the source RDF/XML file
2. **Converts to Turtle**: Transforms the fixed RDF/XML into Turtle (TTL) format, which is more efficient for parsing and importing

## Input Files

- **Source**: `data/acm-css.rdf` - The original RDF/XML file (may contain malformed namespaces)

## Output Files

- **Fixed RDF/XML**: `data/acm-ccs-fixed.rdf` - The corrected RDF/XML file with proper namespaces
- **Turtle**: `data/acm-ccs.ttl` - The final Turtle format file ready for Neo4j import

## What It Does

### 1. Namespace Fixing

The script fixes common issues in the RDF/XML file:
- Replaces the first line with a clean RDF root element containing proper namespace declarations:
  - `xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"`
  - `xmlns:skos="http://www.w3.org/2004/02/skos/core#"`
  - `xmlns:skosxl="http://www.w3.org/2008/05/skos-xl#"`

### 2. Language Attribute Correction

- Converts `lang="..."` attributes to `xml:lang="..."` (required by RDF/XML specification)

### 3. Format Conversion

- Parses the fixed RDF/XML file using RDFLib
- Serializes it to Turtle format, which is more compact and easier to parse

## Usage

```bash
python scripts/pre-process.py
```

## Requirements

- Python >=3.10
- `rdflib` library (installed via `requirements.txt`)

## Error Handling

The script will raise errors if:
- The input file `data/acm-css.rdf` does not exist
- The input file is empty

## Output Messages

- `[OK] Wrote fixed RDF/XML: <path>` - Successfully created the fixed RDF/XML file
- `[OK] Wrote Turtle: <path>` - Successfully created the Turtle file
