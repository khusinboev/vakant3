"""Multi-source vacancy ingestion: adapters fetch, the runner stores into ``vacancies``.

Layout: ``base`` (contracts), ``sources/`` (one adapter per site), ``text``,
``regions``, ``dedup``, ``quality``, ``repo`` (all SQL), ``runner`` (the loop).
"""
