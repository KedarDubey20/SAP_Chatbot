# SAP AI Assistant - Quick Start Guide

## 🚀 2-DAY DEMO SETUP

### Prerequisites
```bash
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env and add:
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
USE_SQLITE_MEMORY=true
```

### Place Excel Files
```bash
# Copy your SAP Excel files to data/
cp /path/to/VBAK.xlsx data/
cp /path/to/VBAP.xlsx data/
cp /path/to/VBEP.xlsx data/
```

### Run Application
```bash
# Development mode
uvicorn app.main:app --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Test Endpoints

**Health Check:**
```bash
curl http://localhost:8000/health/
```

**Upload Excel (if not auto-loaded):**
```bash
curl -X POST http://localhost:8000/sap/upload-excel \
  -F "file=@data/vbak.xlsx"
```

**Check Schema:**
```bash
curl http://localhost:8000/sap/schema
```

**Query:**
```bash
curl -X POST http://localhost:8000/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many sales documents are there?"}'
```

## 📊 Demo Queries

### Basic Queries
- "How many sales documents?"
- "Show all items for sales document 1"
- "What's the total net value?"
- "List all materials"

### Complex Queries
- "Show me sales documents with net value over 50"
- "Which items belong to sales document 2?"
- "What are the schedule lines for document 1, item 10?"

### SAP-Specific
- "Total order quantity across all schedule lines"
- "List sales documents created on 2026-01-20"
- "Show items with material 261"

## 🔧 Architecture Overview

```
User Question
    ↓
FastAPI (/chat/query)
    ↓
ChatService.process_query()
    ├─→ SchemaDiscoveryService (get table structure)
    ├─→ LLMClient.generate_sql() (GPT-4 → SQL)
    ├─→ ExcelLoaderService.execute_query() (run SQL)
    ├─→ AutoHealingService (fallback if error)
    └─→ LLMClient.format_answer() (results → natural language)
    ↓
Return: {answer, sql, results}
```

## 🏗️ Production Deployment

### Switch to SAP HANA
1. Install HANA client: `pip install hdbcli`
2. Update `.env`:
```env
USE_SQLITE_MEMORY=false
HANA_HOST=your-hana-host
HANA_PORT=30015
HANA_USER=your_user
HANA_PASSWORD=your_password
HANA_DATABASE=your_db
```

### Docker Deployment
```bash
docker-compose -f docker/docker-compose.yml up -d
```

## 📁 Key Files

- **app/services/excel_loader_service.py** - Excel → DB loader (CRITICAL)
- **app/services/chat_service.py** - Main query logic
- **app/core/llm_client.py** - GPT-4 integration
- **app/services/auto_healing_service.py** - Fallback mechanisms

## 🐛 Troubleshooting

### Issue: "No tables loaded"
- Check if Excel files are in `data/` directory
- Use `/sap/upload-excel` endpoint manually
- Check logs for auto-load errors

### Issue: "Query failed"
- Verify Azure OpenAI credentials in `.env`
- Check SQL syntax in response
- Auto-healing should retry automatically

### Issue: Column not found
- Excel column names get cleaned (spaces → underscores)
- Check schema: `curl http://localhost:8000/sap/schema`

## 💡 Tips

1. **Logs**: Watch console for SQL queries being generated
2. **Schema**: Always check schema endpoint to see exact column names
3. **Auto-heal**: Failed queries automatically retry with fixes
4. **Zero Hardcoding**: Add ANY Excel file - system adapts automatically

## 🎯 Success Metrics

- ✅ Upload 3 Excel files (VBAK, VBAP, VBEP)
- ✅ Run 10 test queries successfully
- ✅ Achieve 90%+ query accuracy
- ✅ Response time < 3 seconds
- ✅ Demo to client with live queries

---

Built on Maharashtra Government GPT architecture
Zero-hardcoding principle for maximum flexibility
