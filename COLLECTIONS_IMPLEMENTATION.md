# Collections View Implementation

## Overview

A complete collections browsing system that organizes articles by research domain and journal. Users can view all available articles, grouped hierarchically by domain → journal → article.

## What Was Built

### Backend Components

#### 1. **Collections Service** (`api/services/collections_service.py`)
- `ArticleMetadata`: Metadata for individual articles
- `JournalCollection`: Groups articles by journal
- `DomainCollection`: Groups journals by research domain
- `get_collections()`: Fetch collections for an institution with license checking
- `get_collections_summary()`: Get aggregated statistics

**Domain Mapping:**
- **Biomedical**: BJ, REDOX, CELREP, BIOPHA, GENDIS, CLNVES, AJPS, CTARC
- **Energy & Engineering**: ESR
- **Policy & Leadership**: PLAS
- **Other**: Unmapped journals

#### 2. **Collections Router** (`api/routers/collections.py`)
Two endpoints:
```
GET /collections/{institution_id}
├─ Returns all collections for the institution
├─ Hierarchical: domain → journals → articles
└─ Includes statistics (chunks, entities)

GET /collections/{institution_id}/domain/{domain_name}
├─ Returns articles in a specific domain
└─ Useful for domain-specific views
```

#### 3. **Data Models** (`api/models.py`)
```python
ArticleInfo           # Article metadata
JournalInCollection   # Journal with articles
DomainInCollection    # Domain with journals
CollectionsSummary    # Complete collection response
```

#### 4. **Attribution Logging**
Collections views are automatically logged:
- `log_collection_view()` called on every browse
- Tracks: institution, domain, journals, action
- Supports analytics for usage tracking

### Frontend Components

#### 1. **CollectionsPage** (`beacon-ui/src/pages/CollectionsPage.tsx`)
- Full-screen collections browser
- Hierarchical expandable view (domain → journal → articles)
- Statistics dashboard (domains, journals, articles, chunks, entities)
- Expandable sections for each domain and journal
- Article details with DOI and metadata
- Back button to search

#### 2. **UI Integration**
- Added "📚 Browse Collections" button in Sidebar
- Navigates to `/collections` route
- Added routing in App.tsx
- Integrated with institution selection

## API Response Format

```json
{
  "institution_id": "uni_edinburgh",
  "total_domains": 1,
  "total_journals": 2,
  "total_articles": 11,
  "total_chunks": 381,
  "total_entities": 1246,
  "collections": [
    {
      "domain": "Biomedical",
      "journal_count": 2,
      "article_count": 11,
      "total_chunks": 381,
      "total_entities": 1246,
      "journals": [
        {
          "journal_code": "BJ",
          "journal_name": "Biochemical Journal",
          "color": "#7c3aed",
          "article_count": 9,
          "total_chunks": 318,
          "total_entities": 964,
          "articles": [
            {
              "article_id": "BJ_100850",
              "journal_code": "BJ",
              "domain": "Biomedical",
              "doi": "10.1016/j.bj.2025.100850",
              "chunks": 19,
              "entities": 103
            }
            // ... more articles
          ]
        }
        // ... more journals
      ]
    }
    // ... more domains
  ]
}
```

## User Interface

### Collections Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  Article Collections                                    │
│  Browse articles organized by research domain           │
│                                         [← Back to Search] │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Statistics                                              │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│ 1        │ 2        │ 11       │ 381      │ 1246         │
│ Domains  │ Journals │ Articles │ Chunks   │ Entities     │
└──────────┴──────────┴──────────┴──────────┴──────────────┘

┌─────────────────────────────────────────────────────────┐
│ ▼ Biomedical                                            │
│   2 journals · 11 articles · 381 chunks · 1246 entities │
├─────────────────────────────────────────────────────────┤
│   ▶ Biochemical Journal                              [BJ]│
│     9 articles · 318 chunks · 964 entities               │
│     ▶ BJ_100850 | 19 chunks · 103 entities              │
│     ▶ BJ_100833 | 30 chunks · 121 entities              │
│     ... more articles                                    │
│   ▶ Redox Biology                                [REDOX]│
│     2 articles · 63 chunks · 282 entities               │
└─────────────────────────────────────────────────────────┘
```

### Sidebar Integration

```
┌──────────────────────┐
│  Institution Info    │
│  ─────────────────── │
│  Your Collection     │
│  Journals list...    │
│  ─────────────────── │
│  Results: [1] ▬▬▬▬▬ │
│  ─────────────────── │
│  📚 Browse Collections│
│  Switch Institution  │
│  🔬 Beacon Logo      │
└──────────────────────┘
```

## Features

✅ **Hierarchical Organization**: Domain → Journal → Article
✅ **Expandable Sections**: Click to expand/collapse any level
✅ **License Checking**: Only shows articles user can access
✅ **Rich Metadata**: Chunks, entities, DOI for each article
✅ **Color Coding**: Journal-specific colors for visual distinction
✅ **Statistics**: Total counts at each level
✅ **Attribution Logging**: All views are tracked for metered usage
✅ **Easy Navigation**: Clear back button to search
✅ **Responsive Design**: Works on desktop and tablets

## Testing

### API Endpoint Test
```bash
curl http://localhost:8000/collections/uni_edinburgh | jq
```

### Response Sample (uni_edinburgh)
```
- 1 domain (Biomedical)
- 2 journals (BJ, REDOX)
- 11 articles total
- 381 chunks
- 1246 entities
```

## Integration with Attribution

All collection browsing is logged:

```json
{
  "timestamp": "2026-05-09T17:15:32.123456+00:00",
  "event_type": "collection_view",
  "institution_id": "uni_edinburgh",
  "domain": "Biomedical",
  "journals": ["BJ", "REDOX"],
  "action": "browse",
  "session_id": "sess_abc123"
}
```

This enables:
- Usage analytics by domain and journal
- Understanding browsing patterns
- Metered billing by collection type

## Files Changed/Created

| File | Type | Purpose |
|------|------|---------|
| `api/services/collections_service.py` | NEW | Collections logic and aggregation |
| `api/routers/collections.py` | NEW | API endpoints |
| `api/models.py` | MODIFIED | Added collection response models |
| `api/main.py` | MODIFIED | Registered collections router |
| `beacon-ui/src/pages/CollectionsPage.tsx` | NEW | Collections UI component |
| `beacon-ui/src/App.tsx` | MODIFIED | Added /collections route |
| `beacon-ui/src/components/layout/Sidebar.tsx` | MODIFIED | Added browse collections button |
| `beacon-ui/src/pages/SearchPage.tsx` | MODIFIED | Added navigation to collections |

## Architecture

```
Browser (Port 5173)
  └─ CollectionsPage Component
      └─ GET /collections/{institution_id}
          └─ Backend (Port 8000)
              ├─ collections.py (Router)
              ├─ collections_service.py (Service)
              ├─ license_service.py (License checking)
              └─ attribution_service.py (Logging)
                  └─ .tmp/attribution.jsonl
```

## Next Steps

### Phase 2: Enhanced Features
- **Search within Collections**: Filter articles by name/DOI
- **Bulk Actions**: Select multiple articles for comparison
- **Favorites**: Bookmark frequently accessed articles
- **Sort Options**: By date, entity count, chunk count

### Phase 3: Advanced Analytics
- **Domain Charts**: Visual breakdown of article distribution
- **Entity Analysis**: Most common entities per domain
- **Trending Articles**: Most accessed articles per domain

## License Checking

Collections respect license boundaries:
- Each institution only sees articles it has access to
- License decisions are cached for performance
- Open access articles visible to all

## Performance

- Collections loaded on demand (no background fetching)
- Minimal JSONL logging overhead
- Hierarchical rendering prevents overwhelming UI
- Article metadata loaded from disk cache

## Accessibility

- Keyboard navigation support
- Clear visual hierarchy
- Color + text labels (not color alone)
- Expandable sections for progressive disclosure
