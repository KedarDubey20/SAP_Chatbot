# SAP AI Assistant - Complete Folder Structure
 
```
sap-ai-assistant/
│
├── app/                                    # Main application package
│   ├── __init__.py                         # App initialization
│   ├── main.py                             # FastAPI app entry point
│   │
│   ├── core/                               # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                       # Environment config, settings
│   │   ├── database.py                     # Database abstraction layer
│   │   ├── hana_connector.py               # ⭐ SAP HANA client (hdbcli)
│   │   ├── llm_client.py                   # Azure OpenAI GPT-4.1 wrapper
│   │   ├── vector_store.py                 # Qdrant vector DB client
│   │   └── prompt_templates.py             # SQL generation prompts (SAP-specific)
│   │
│   ├── models/                             # Pydantic data models
│   │   ├── __init__.py
│   │   ├── chat_models.py                  # Chat request/response schemas
│   │   ├── sap_models.py                   # ⭐ VBAK/VBAP/VBEP table models
│   │   ├── vector_models.py                # Embedding/RAG models
│   │   └── file_models.py                  # File upload schemas
│   │
│   ├── routes/                             # FastAPI API endpoints
│   │   ├── __init__.py
│   │   ├── chat_routes.py                  # POST /chat/query, GET /chat/history
│   │   ├── health_routes.py                # GET /health, /status
│   │   └── sap_routes.py                   # ⭐ POST /sap/upload-excel, GET /sap/schema
│   │
│   ├── services/                           # Business logic layer
│   │   ├── __init__.py
│   │   ├── chat_service.py                 # Main query processing (from MH-Gov)
│   │   ├── sap_query_service.py            # ⭐ SAP-specific query logic
│   │   ├── schema_discovery_service.py     # Dynamic table/column discovery (from MH-Gov)
│   │   ├── auto_healing_service.py         # Query fallback mechanisms (from MH-Gov)
│   │   └── excel_loader_service.py         # ⭐⭐ PRIORITY: XLSX → SQLite/HANA
│   │
│   ├── middleware/                         # HTTP middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py              # JWT/API key validation
│   │   ├── logging_middleware.py           # Request/response logging
│   │   └── error_handler.py                # Global exception handling
│   │
│   └── utils/                              # Helper utilities
│       ├── __init__.py
│       ├── sql_validator.py                # SQL sanitization + HANA dialect
│       ├── response_formatter.py           # SQL results → natural language
│       └── helpers.py                      # Date parsing, string utils
│
├── tests/                                  # Test suite
│   ├── __init__.py
│   ├── test_chat.py                        # Chat service tests
│   ├── test_sap_queries.py                 # SAP query validation
│   └── test_auto_healing.py                # Fallback mechanism tests
│
├── docker/                                 # Docker configuration
│   ├── Dockerfile                          # Python 3.11 + FastAPI + HANA client
│   └── docker-compose.yml                  # Service orchestration
│
├── data/                                   # Data files (gitignored)
│   └── README.md                           # Instructions for Excel files
│
├── .env.example                            # Environment variables template
├── .gitignore                              # Git ignore rules
├── requirements.txt                        # Python dependencies
└── README.md                               # Project documentation
```

## File Count: 42 files

## Key Differences from MH-Gov

### New SAP-Specific Files (⭐):
1. **core/hana_connector.py** - SAP HANA DB client (replaces MySQL)
2. **models/sap_models.py** - VBAK/VBAP/VBEP schemas
3. **routes/sap_routes.py** - Excel upload + schema endpoints
4. **services/sap_query_service.py** - SAP table JOIN logic
5. **services/excel_loader_service.py** - CRITICAL for 2-day demo

### Reused from MH-Gov (Copy 1:1):
- `services/chat_service.py` - Core query processing
- `services/schema_discovery_service.py` - Dynamic table discovery
- `services/auto_healing_service.py` - Fallback logic
- `core/llm_client.py` - Azure OpenAI wrapper
- `core/vector_store.py` - Qdrant integration
- `middleware/*` - All middleware
- `utils/*` - All utilities

### Priority Order for 2-Day Demo:

**Day 1: Core Infrastructure**
1. `services/excel_loader_service.py` - Load XLSX → SQLite
2. `routes/sap_routes.py` - Upload endpoint
3. `core/config.py` - Environment setup
4. `app/main.py` - FastAPI initialization

**Day 2: Query Processing**
5. Copy `services/chat_service.py` from MH-Gov
6. Copy `services/schema_discovery_service.py` from MH-Gov
7. Copy `services/auto_healing_service.py` from MH-Gov
8. `routes/chat_routes.py` - Query endpoint

## SAP Table Relationships

```
VBAK (Header)
├── Sales_document (PK)
├── Net_Value
└── Created_on

    ↓ (1:N)

VBAP (Items)
├── Sales_document (FK → VBAK)
├── Sales_Document_Item (PK)
├── Material
└── Net_Value

    ↓ (1:N)

VBEP (Schedule Lines)
├── Sales_document (FK → VBAK)
├── Sales_Document_Item (FK → VBAP)
├── Schedule_line_number (PK)
└── Order_Quantity
```

## Demo Queries

- "How many sales documents?"
- "Show all items for sales document 1"
- "What's the total net value across all orders?"
- "List all materials ordered"
- "Show schedule lines for item 10 of sales doc 2"

All work with zero hardcoding - dynamic schema discovery handles everything.
