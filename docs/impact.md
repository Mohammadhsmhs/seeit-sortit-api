# Impact: What Smart Prioritisation Changes

Councils typically triage reports manually, or on a first-come-first-served basis. The priority scoring system in this API changes that in a few meaningful ways.

## Equity, not just volume

Deprivation weighting means a pothole in Barking gets scored higher than the same pothole in Richmond — not because one councillor shouted louder, but because the data shows residents there have fewer alternatives and less capacity to absorb the disruption.

## Safety issues jump the queue automatically

A broken streetlight in a high-crime borough scores with a 0.5 crime weight. That's the system recognising that a dark street in Hackney is a different kind of problem than one in Sutton — without anyone having to make that call manually.

## The city's live pulse feeds in

When TfL is reporting heavy road disruption, pothole scores rise across the board. The council's repair queue responds to what's actually happening on the streets that day, not just what was submitted this week.

## Scale and cost awareness built in

Baseline repair costs mean a £50 graffiti job doesn't crowd out a £500 streetlight repair just because it scored higher on severity. The queue reflects what's worth doing urgently relative to effort.

## The net effect

A council using this shifts from reactive (loudest complainant wins) to genuinely needs-based prioritisation — at scale, across thousands of reports, with no manual triage required.

---

## How the data is combined

Each report produces a `priority_score` from four signals:

```
priority_score = (vlm_severity × context_multiplier × population_density) / baseline_cost
```

| Signal | Source | What it represents |
|---|---|---|
| `vlm_severity` | Vision LLM (1–5) | How serious the issue looks in the image |
| `context_multiplier` | Crime + deprivation + TfL (0.5–2.0) | How urgent the local context makes it |
| `population_density` | ONS density data (people/km²) | How many people are affected |
| `baseline_cost` | Fixed repair cost lookup (£) | Normalises by effort required to fix |
| `location_resolution` | postcodes.io (lat/lon → LSOA + borough) | Maps GPS coordinates to the local area context signals are drawn from |

The `context_multiplier` is itself a weighted blend of three data sources, and the weights shift depending on the issue type:

| Issue type | Crime | Deprivation | TfL disruption | Baseline cost |
|---|---|---|---|---|
| Pothole | 20% | 30% | **50%** | £200 |
| Graffiti | 40% | 40% | 20% | £50 |
| Broken streetlight | **50%** | 30% | 20% | £500 |
| Fly-tipping | 30% | **50%** | 20% | £150 |
| Other | 30% | 40% | 30% | £100 |

### Data sources

| Data | Provider | Granularity | Update frequency |
|---|---|---|---|
| Crime totals | London Datastore — MPS dataset `exy3m` | Borough and LSOA | Built into DB at deploy time |
| Deprivation (IMD 2019) | London Datastore — MHCLG dataset `2l15g` | Borough and LSOA | Built into DB at deploy time |
| Road disruptions | TfL Unified API (`api.tfl.gov.uk`) | London-wide count | Live, per request |
| Population density | `density.csv` — source not documented | Borough | Built into DB at deploy time |
| Issue taxonomy | Local YAML config | Issue type | On app restart |
| LSOA resolution | postcodes.io (`api.postcodes.io`) | Lat/lon → LSOA | Live, per request |

### Priority bands

The final score and VLM severity together determine the output band:

| Band | Condition |
|---|---|
| HIGH | Severity ≥ 4, or priority score ≥ 500 |
| MEDIUM | Severity ≥ 3, or priority score ≥ 200 |
| LOW | Everything else |
