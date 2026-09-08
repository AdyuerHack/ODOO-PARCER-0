**Odoo Multi-Format Data Importer** is a native Odoo19 module that transforms a raw file (Excel/CSV) into clean Odoo records through an AI-assisted ETL pipeline.

The mapping engine works in a three-level cascade, from the reliable and low-cost rule-based approach to the high-level AI:

1. **Hash Mapping (Deterministic):** a dictionary of known synonyms with constant-time resolution. `"NIT" → vat`.
2. **Fuzzy Matching:** Levenshtein distance applied to column headers to handle spelling mistakes, accents, and capitalization differences. `"STREET" → street`.
3. **LLM Agent (Semantic Analysis):** only for the columns that remain unresolved after the previous two stages. The column name and a file of real values are sent to the agent, together with the Odoo fields, so it can infer the correct mapping and provide a justification.

None of this is a black box: the interface displays the original data alongside the mapped data, the level that made the decision, and its confidence score as a percentage and an associated color from green to red, allowing users to make corrections before persisting the data. For large volumes, processing is divided into queued chunks, and users can monitor the progress through a real-time monitoring dashboard.
