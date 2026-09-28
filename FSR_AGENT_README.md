FSR Data Finder Agent
=====================

What it is
----------

A small agent that periodically fetches public time-series data and evaluates each series with the repository's FSR function (`calculate_predictability` in `fsr.py`). The agent flags and appends "interesting" series to `fsr_agent_results.jsonl`.

Usage
-----

Run the agent with:

```bash
python fsr_data_agent.py --interval 3600 --threshold 70
```

Options
-------
- `--interval`: seconds between checks (default 3600)
- `--threshold`: FSR threshold to mark as interesting (default 70)
- `--min-delta`: minimum percent change in FSR to mark as interesting (default 10)
- `--k`: K factor passed to the FSR function (default 1.0)

Extending sources
------------------

Edit `fsr_data_agent.py` and add additional `DataSource` subclasses. The file contains `CoinGeckoSource` (crypto) and `StaticCSVSource` (raw CSV URL) examples.

Notes
-----
- The agent is intentionally simple and file-backed; replace persistence with a DB or message queue for production.
- Some public sources may rate-limit requests. Adjust `--interval` or add backoff if you expand sources.
