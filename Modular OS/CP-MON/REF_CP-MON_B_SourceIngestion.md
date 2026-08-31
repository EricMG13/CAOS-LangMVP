# REF_CP-MON_B — Source Ingestion
Read only the case's user-uploaded, immutable source set. Classify each uploaded document, preserve its source digest and evidence locators, and output RawSignalQueue. If required current information is absent, report the gap and request another upload; do not run an external acquisition connector.
