# Data Dictionary — GridPulse

## Merged Outage Records (primary analysis table)

| Column          | Type     | Description                                      | Notes                          |
|-----------------|----------|--------------------------------------------------|--------------------------------|
| fips            | int      | County FIPS code                                 |                                |
| state           | str      | State name                                       |                                |
| county          | str      | County name                                      |                                |
| start_time      | datetime | Start of outage event (normalized to UTC)        | Timezone assumption: UTC       |
| duration        | float    | Duration in hours                                |                                |
| min_customers   | float    | Minimum customers affected during event          | Zero is valid (no customers)   |
| max_customers   | float    | Maximum customers affected                       |                                |
| mean_customers  | float    | Mean customers affected                          | Primary magnitude feature      |

## Distinctions

- **Zero outages**: mean_customers == 0 (valid observation of no/low impact).
- **Missing**: NaN in count fields or start_time (invalid; rejected).

## Source

Derived from OpenEI Event-correlated Outage Dataset (CC BY 4.0).  
See `data/provenance/manifest.json` for exact retrieval metadata.
