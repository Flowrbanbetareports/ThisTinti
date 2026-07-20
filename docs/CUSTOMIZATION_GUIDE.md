# Company customization guide

ThisTinti is deliberately modular so an internal or external technical team can
adapt it without replacing the whole product.

## Common extension points

- `app/parsers/`: add document formats or supplier-specific extraction.
- `app/services/rules.py`: deterministic anomaly rules.
- `app/services/matching.py` and `line_matching.py`: document and line matching.
- `app/services/intelligence.py`: Proof Graph, Sentinel, risk and conformance.
- `app/static/`: browser interface and company branding.
- `app/schemas.py`: API contracts.
- `migrations/`: server/PostgreSQL schema evolution.
- `app/local_schema.py`: Local Edition SQLite schema evolution.

## Safe adaptation sequence

1. fork the repository and preserve the upstream tag used as the base;
2. reproduce the existing tests and local smoke before changing code;
3. add anonymized examples representing the company's document flow;
4. implement one narrow change at a time;
5. add regression tests and explainable evidence for every economic conclusion;
6. run a supervised pilot before enabling any automation;
7. rebuild installer, portable archive, SBOM and checksums.

## Integration options

A company can use the REST API, add import/export adapters, run the server edition
with PostgreSQL for multiple users, or keep the single-workstation Local Edition.
The Apache 2.0 license permits internal modifications and redistribution subject
to its conditions and notices.

## Boundaries

A company fork becomes the responsibility of the company or supplier maintaining
that fork. Upstream test results do not certify custom code, infrastructure,
security configuration or compliance.
