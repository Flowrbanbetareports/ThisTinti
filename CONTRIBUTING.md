# Contributing and company forks

ThisTinti is released under Apache License 2.0. Technical teams can fork the
repository and adapt parsers, rules, integrations, branding and deployment.

Before proposing or distributing a change:

1. create a dedicated branch;
2. install `requirements-dev.txt`;
3. add tests for the changed behavior;
4. run Ruff, Bandit, the full test suite and the local distribution smoke;
5. update OpenAPI, SBOM, notices and release notes when applicable;
6. never commit real company documents, secrets or production databases.

Useful entry points are documented in `docs/CUSTOMIZATION_GUIDE.md`. Changes that
affect economic conclusions must remain explainable and supervised until they
have passed a real, approved validation dataset.
