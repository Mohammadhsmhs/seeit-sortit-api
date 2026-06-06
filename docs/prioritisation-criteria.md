# Ticket Prioritisation Criteria

Tickets are scored using a two-layer model:

```
priority = severity × context_multiplier
```

---

## Layer 1 — Severity

Set by the `/analyse-report` agent from the submitted image and description. Scale 1–5.

| Severity | Meaning |
|---|---|
| 5 | Immediate danger — e.g. deep pothole on road, live electrical hazard |
| 4 | Safety risk, not immediate — e.g. broken streetlight, large fly-tip blocking access |
| 3 | Functional problem — e.g. graffiti on public building, pavement crack |
| 2 | Nuisance — e.g. minor graffiti, litter |
| 1 | Cosmetic only |

---

## Layer 2 — Context Multiplier

A weighted blend of four sub-scores, applied after severity is set. Weights vary by ticket category (e.g. potholes weight Safety and Exposure heavily; fly-tipping weights Vulnerability/Need and Demand).

### 1. Exposure — how many people does this affect?
- Footfall and busyness at the location (PTAL as open proxy)
- Whether it is on a high street, busy road, or residential backstreet

### 2. Vulnerability / Need — are the affected people at higher risk?
- Deprivation index of the LSOA (Indices of Deprivation 2019)
- Elderly and disabled population density (LSOA Atlas)
- Proximity to a school, care home, or hospital (LAEI receptor summaries)

### 3. Safety — is there an existing danger signal at this location?
- Crime rate at LSOA or ward level (MPS Recorded Crime, 24-month rolling)
- Road collision history (STATS19)
- Air quality and sensitive receptors nearby (LAEI 2022)

### 4. Asset Criticality — how important is the infrastructure?
- Whether the location is on a classified road or TfL network
- Whether it falls within a high street or town centre boundary

---

## Priority Bands

| Priority | Typical profile |
|---|---|
| **HIGH** | Severity ≥ 4, OR severity 3 with high exposure + a safety signal (e.g. pothole near a collision cluster in a deprived LSOA) |
| **MEDIUM** | Severity 3, average context — functional problem in a typical area with no amplifying signals |
| **LOW** | Severity ≤ 2, OR severity 3 with low exposure and no safety signals (e.g. graffiti on a quiet residential wall) |

---

## Data Sources

| Sub-score | Dataset | File | Currency |
|---|---|---|---|
| Exposure | PTAL | `data/london/24rz6/24rz6__LSOA2011 AvPTAI2015.csv` | 2015 |
| Vulnerability / Need | Indices of Deprivation | `data/london/2l15g/2l15g__ID 2019 for London.xlsx` | 2019 |
| Vulnerability / Need | LSOA Atlas | `data/london/2n8zy/2n8zy__lsoa-data.csv` | Mixed |
| Vulnerability / Need | LAEI receptors | `data/london/e758q/e758q__Dec2022_SchoolsSummary_LAEI2019.xlsx` | 2022 |
| Safety | MPS Crime (LSOA) | `data/london/exy3m/exy3m__MPS LSOA Level Crime (most recent 24 months).csv` | Monthly |
| Safety | MPS Crime (Ward) | `data/london/exy3m/exy3m__MPS Ward Level Crime (most recent 24 months).csv` | Monthly |
| Safety | Air quality | `data/london/2kdpj/` (per-borough zips) | 2022 |

---

## Status

- Severity scoring: implemented in `/analyse-report` agent
- Context multiplier: not yet built — next step after `/analyse-report` is stable
