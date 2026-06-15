# SAP AI Assistant

Natural language query interface for SAP HANA database using Azure OpenAI GPT-4.1.

## Architecture

Mirrors Maharashtra Government GPT project structure with SAP-specific adaptations:

- **Zero Hardcoding**: Dynamic schema discovery, works with any SAP table structure
- **Auto-Healing**: Multi-layer fallback for failed queries
- **HANA + SQLite**: Production uses HANA, demo uses in-memory SQLite with Excel uploads

## Quick Start (2-Day Demo)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
cp .env.example .env
# Edit .env: Set USE_SQLITE_MEMORY=true, add Azure OpenAI keys

# Place Excel files in data/
# - vbak.xlsx (Sales Header)
# - vbap.xlsx (Sales Items)
# - vbep.xlsx (Schedule Lines)

# Run
uvicorn app.main:app --reload

# Test
curl -X POST http://localhost:8000/sap/upload-excel \
  -F "file=@data/vbak.xlsx"

curl -X POST http://localhost:8000/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many sales documents are there?"}'
```

## Folder Structure

```
sap-ai-assistant/
├── app/
│   ├── core/                    # Configuration, DB, LLM, Vector Store
│   │   ├── hana_connector.py    # SAP HANA client (hdbcli)
│   │   └── ...
│   ├── models/                  # Pydantic schemas
│   │   ├── sap_models.py        # VBAK/VBAP/VBEP models
│   │   └── ...
│   ├── routes/                  # FastAPI endpoints
│   │   ├── sap_routes.py        # Excel upload, schema info
│   │   └── ...
│   ├── services/                # Business logic
│   │   ├── excel_loader_service.py  # PRIORITY: Excel → DB
│   │   ├── schema_discovery_service.py
│   │   ├── auto_healing_service.py
│   │   └── ...
│   └── main.py
├── tests/                       # pytest tests
├── docker/                      # Dockerfile, docker-compose
├── data/                        # Excel files (gitignored)
└── requirements.txt
```

## Key Files for 2-Day Demo

1. **services/excel_loader_service.py** - Load XLSX into SQLite
2. **routes/sap_routes.py** - Upload endpoint
3. **services/chat_service.py** - Query processing (copy from MH-Gov)
4. **core/prompt_templates.py** - SAP-specific SQL prompts

## SAP Tables (Demo Data)

- **VBAK**: Sales Document Header (5 rows, 221 columns)
- **VBAP**: Sales Document Items (5 rows, 431 columns)
- **VBEP**: Schedule Lines (5 rows, 81 columns)

Relationships:
```
VBAK.Sales_document ← VBAP.Sales_document ← VBEP.Sales_document
```

## Production Deployment

Replace SQLite with SAP HANA:
1. Install `hdbcli`: `pip install hdbcli`
2. Update `core/hana_connector.py`
3. Set HANA credentials in `.env`
4. Deploy with Docker

## Contact

Based on Maharashtra Government GPT architecture.
Zero-hardcoding principle ensures scalability to any SAP schema.
