# Data Folder

Place SAP Excel files here for demo:

- `vbak.xlsx` - Sales Document Header Data
- `vbap.xlsx` - Sales Document Item Data  
- `vbep.xlsx` - Schedule Line Data

Files in this folder are gitignored.

## Auto-Load on Startup

If files exist here when app starts, they're automatically loaded into in-memory SQLite.

Alternatively, use the upload API:
```bash
POST /sap/upload-excel
```
