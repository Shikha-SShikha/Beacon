# Attribution & Metered Usage Tracking — Phase 1 Implementation

## What Was Implemented

### ✅ Core Components

#### 1. **Attribution Service** (`api/services/attribution_service.py`)
- `log_search_attribution()` — Log when articles appear in search results
- `log_collection_view()` — Log when users browse collections
- `get_usage_stats()` — Retrieve metered usage statistics
- **Domain Mapping**: Automatic mapping of journal codes to research domains
  - BJ, REDOX, CELREP, BIOPHA, GENDIS, CLNVES, AJPS, CTARC → Biomedical
  - ESR → Energy & Engineering
  - PLAS → Policy & Leadership

#### 2. **Enhanced Data Model** (`api/models.py`)
Added to `SearchResult`:
- `article_id` — e.g., "BJ_100850"
- `journal_code` — e.g., "BJ"
- `domain` — e.g., "Biomedical"
- `access_level` — "FULL_TEXT" | "SNIPPET_ONLY" | "OPEN_ACCESS"

#### 3. **Search Attribution Logging** (`api/routers/search.py`)
- Every search result is automatically logged
- Captures: institution, article, journal, domain, access level, query, rank
- Non-blocking (doesn't slow down searches)

#### 4. **Analytics Endpoints** (`api/routers/analytics.py`)
Two new endpoints for viewing metered usage:

**Global Usage:**
```
GET /analytics/usage
```
Returns total usage across all institutions.

**Per-Institution Usage:**
```
GET /analytics/usage/{institution_id}
```
Returns usage statistics for a specific institution.

Response format:
```json
{
  "by_domain": {
    "Biomedical": 42,
    "Energy & Engineering": 15,
    "Policy & Leadership": 8
  },
  "by_journal": {
    "BJ": 25,
    "REDOX": 17,
    "ESR": 15,
    "PLAS": 8
  },
  "by_access_level": {
    "FULL_TEXT": 45,
    "SNIPPET_ONLY": 15,
    "OPEN_ACCESS": 5
  },
  "total_accesses": 65
}
```

---

## Attribution Log Format

All attributions are stored in `.tmp/attribution.jsonl` (append-only, one JSON object per line):

### Search Result Event
```json
{
  "timestamp": "2026-05-09T16:56:58.540618+00:00",
  "event_type": "search_result",
  "institution_id": "uni_edinburgh",
  "article_id": "BJ_100850",
  "journal_code": "BJ",
  "domain": "Biomedical",
  "access_level": "FULL_TEXT",
  "query": "protein folding",
  "rank": 1,
  "session_id": "test-session-001"
}
```

### Collection View Event
```json
{
  "timestamp": "2026-05-09T16:56:58.541110+00:00",
  "event_type": "collection_view",
  "institution_id": "uni_edinburgh",
  "domain": "Biomedical",
  "journals": ["BJ", "REDOX", "CELREP"],
  "action": "browse",
  "session_id": "test-session-001"
}
```

---

## Testing Results

### ✅ Journal Code Extraction
```
BJ_100850    → Code: BJ     Domain: Biomedical
ESR-102001   → Code: ESR    Domain: Energy & Engineering
PLAS-100213  → Code: PLAS   Domain: Policy & Leadership
REDOX-104080 → Code: REDOX  Domain: Biomedical
```

### ✅ Usage Analytics
```
Uni Edinburgh:
  - Total accesses: 2
  - Biomedical: 2
  - BJ: 1, REDOX: 1

TU Berlin:
  - Total accesses: 1
  - ESR: 1

Global:
  - Total accesses: 3
  - Biomedical: 2, Energy & Engineering: 1
```

---

## How It Works

### Search Flow (with Attribution)
1. User searches → `POST /search`
2. Backend retrieves articles
3. For each result:
   - Extract `journal_code` from `source` (e.g., "BJ_100850" → "BJ")
   - Map `journal_code` to `domain` (e.g., "BJ" → "Biomedical")
   - Call `log_search_attribution()`
   - Append log entry to `.tmp/attribution.jsonl`
   - Include `article_id`, `journal_code`, `domain`, `access_level` in response
4. Return SearchResult with attribution metadata

### Usage Reporting Flow
1. Admin requests `GET /analytics/usage/uni_edinburgh`
2. Backend reads all attribution logs
3. Filters to matching institution
4. Aggregates by domain, journal, access_level
5. Returns summary statistics

---

## Key Features

✅ **Reliable**: Server-side logging (can't be bypassed by client)  
✅ **Lightweight**: JSONL format (append-only, no database)  
✅ **Extensible**: Easy to add new event types  
✅ **Non-blocking**: Logging doesn't affect search latency  
✅ **Auditable**: Complete timestamp trail for compliance  
✅ **Flexible**: Domain + Journal + Institution + Access Level breakdown  

---

## Next Steps (Phase 2 & 3)

### Phase 2: Client-Side Interaction Tracking
- Track when user **clicks** an article
- Track when user **expands** or **downloads** content
- Send to `POST /track/article-view`

### Phase 3: Reporting & Billing
- Dashboard showing usage trends
- Monthly billing reports per institution
- Export attribution logs to CSV/JSON
- Real-time cost calculation

---

## Files Changed

| File | Change |
|------|--------|
| `api/models.py` | Added attribution fields to SearchResult |
| `api/routers/search.py` | Added attribution logging on search |
| `api/routers/analytics.py` | **NEW** — Usage analytics endpoints |
| `api/services/attribution_service.py` | **NEW** — Core attribution logging |
| `api/main.py` | Registered analytics router |
| `.tmp/attribution.jsonl` | **NEW** — Append-only audit log |

---

## Example: Billing Query

To calculate billable usage per institution per month:

```python
from api.services.attribution_service import get_usage_stats

# Get metrics for billing
for institution in ["uni_edinburgh", "tu_berlin", "global_policy", "guest"]:
    stats = get_usage_stats(institution_id=institution)
    print(f"\n{institution}")
    print(f"  Full-text accesses: {stats['by_access_level'].get('FULL_TEXT', 0)}")
    print(f"  Snippet-only accesses: {stats['by_access_level'].get('SNIPPET_ONLY', 0)}")
    print(f"  Open access views: {stats['by_access_level'].get('OPEN_ACCESS', 0)}")
```

---

## Integration Notes

When users search or browse collections, attribution is automatically logged. No client-side changes required for Phase 1. The analytics endpoints are ready to query at any time.

All attribution data is preserved in `.tmp/attribution.jsonl` for audit/compliance purposes.
