"""
Schema Loader Service - Auto-discovers table schemas from any data source
Supports: Excel, SAP HANA, SAP RFC
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger
import pandas as pd

try:
    import openpyxl
except ImportError:
    logger.warning("openpyxl not installed - Excel schema discovery will fail")


class SchemaLoaderService:
    """
    Auto-discovers and loads table schemas from multiple sources.
    Zero-hardcoding: Works with ANY table structure.
    Tables driven by HANA_TABLES in .env — no hardcoded table names anywhere.
    """

    def __init__(self, data_path: str = None, cache_service=None, config=None):
        self.data_path = Path(data_path) if data_path else None
        self.cache = cache_service
        self.config = config
        self.schemas = {}
        logger.info("✓ SchemaLoaderService initialized")

    # ============================================================
    # AUTO SCHEMA DISCOVERY
    # ============================================================

    def discover_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Auto-discover schemas — goes directly to the source set in DATA_SOURCE.
        Priority: hana → excel → rfc
        """
        logger.info("🔍 Auto-discovering schemas from all sources...")

        data_source = getattr(self.config, 'DATA_SOURCE', 'excel')
        logger.info(f"📌 DATA_SOURCE = {data_source}")

        if data_source == 'hana':
            if self.config and getattr(self.config, 'HANA_HOST', None):
                hana_schemas = self._discover_from_hana()
                if hana_schemas:
                    logger.info(f"✓ Found {len(hana_schemas)} schemas in HANA")
                    self.schemas.update(hana_schemas)
                    return self.schemas

        elif data_source == 'excel':
            if self.data_path and self.data_path.exists():
                excel_schemas = self._discover_from_excel()
                if excel_schemas:
                    logger.info(f"✓ Found {len(excel_schemas)} schemas in Excel")
                    self.schemas.update(excel_schemas)
                    return self.schemas

        elif data_source == 'rfc':
            if self.config and getattr(self.config, 'SAP_USE_RFC', False):
                rfc_schemas = self._discover_from_rfc()
                if rfc_schemas:
                    logger.info(f"✓ Found {len(rfc_schemas)} schemas in SAP RFC")
                    self.schemas.update(rfc_schemas)
                    return self.schemas

        logger.warning("⚠️ No schemas discovered from any source")
        return {}

    # ============================================================
    # EXCEL SCHEMA DISCOVERY
    # ============================================================

    def _discover_from_excel(self) -> Dict[str, Dict[str, Any]]:
        """Discover schemas from Excel/CSV files in the data path"""
        try:
            schemas = {}

            excel_files = list(self.data_path.glob("*.xlsx")) + list(self.data_path.glob("*.XLSX"))
            csv_files   = list(self.data_path.glob("*.csv"))
            all_files   = excel_files + csv_files

            logger.info(f"Found {len(all_files)} data files")

            for file_path in all_files:
                try:
                    if file_path.suffix.lower() == '.csv':
                        df = pd.read_csv(file_path, nrows=0)
                    else:
                        df = pd.read_excel(file_path, nrows=0)

                    table_name = self._extract_table_name(file_path.stem)

                    schemas[table_name] = {
                        'source': 'excel',
                        'table_name': table_name,
                        'columns': list(df.columns),
                        'column_count': len(df.columns),
                        'record_count': self._get_row_count(file_path),
                        'data_types': self._infer_types_from_excel(file_path),
                        'file_path': str(file_path),
                        'file_size': file_path.stat().st_size
                    }

                except Exception as e:
                    logger.warning(f"Failed to read {file_path.name}: {e}")
                    continue

            return schemas

        except Exception as e:
            logger.warning(f"Excel schema discovery failed: {e}")
            return {}

    def _extract_table_name(self, filename: str) -> str:
        """
        Extract table name from filename — generic, no hardcoded table names.
        Cleans common noise words and uses the result as table name.
        """
        clean_name = (
            filename.upper()
            .replace('CSV DUMP', '')
            .replace('CSV_DUMP', '')
            .replace('DUMP', '')
            .replace('HEADER', '')
            .replace('ITEM', '')
            .replace('DATA', '')
            .replace(' ', '_')
            .strip('_')
        )
        return clean_name[:20]

    def _get_row_count(self, file_path: Path) -> int:
        """Get total row count from file"""
        try:
            if file_path.suffix.lower() == '.csv':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return sum(1 for _ in f) - 1
            else:
                df = pd.read_excel(file_path, usecols=[0])
                return len(df)
        except:
            return 0

    def _infer_types_from_excel(self, file_path: Path) -> Dict[str, str]:
        """Infer column data types from Excel/CSV sample"""
        try:
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path, nrows=100)
            else:
                df = pd.read_excel(file_path, nrows=100)

            type_map = {}
            for col in df.columns:
                dtype = df[col].dtype
                if dtype == 'int64':
                    type_map[col] = 'INTEGER'
                elif dtype == 'float64':
                    type_map[col] = 'FLOAT'
                elif dtype == 'bool':
                    type_map[col] = 'BOOLEAN'
                elif dtype == 'datetime64[ns]':
                    type_map[col] = 'DATETIME'
                else:
                    type_map[col] = 'TEXT'
            return type_map

        except:
            return {}

    # ============================================================
    # SAP HANA SCHEMA DISCOVERY
    # ============================================================

    def _discover_from_hana(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover schemas from SAP HANA.
        Tables driven by HANA_TABLES in .env — no hardcoding.
        If HANA_TABLES not set → fails clearly with instructions.
        Works for any client, any number of tables.
        """
        try:
            from hdbcli import dbapi

            logger.info(f"🔌 Connecting to HANA at {self.config.HANA_HOST}:{self.config.HANA_PORT}")

            conn = dbapi.connect(
                address=self.config.HANA_HOST,
                port=self.config.HANA_PORT,
                user=self.config.HANA_USER,
                password=self.config.HANA_PASSWORD
            )

            hana_schema = getattr(self.config, 'HANA_SCHEMA', 'SAPHANADB')
            logger.info(f"📋 Using HANA schema: {hana_schema}")

            schemas = {}
            cursor  = conn.cursor()

            # Get target tables from .env — no hardcoding
            hana_tables_env = getattr(self.config, 'HANA_TABLES', '')
            if not hana_tables_env:
                logger.error("❌ HANA_TABLES not set in .env — please specify which tables to load")
                logger.error("   Example: HANA_TABLES=VBAK,VBAP,VBEP,KNA1,MARA,EKKO,EKPO")
                conn.close()
                return {}

            target_tables = [t.strip() for t in hana_tables_env.split(',')]
            logger.info(f"📋 Loading {len(target_tables)} tables from .env: {target_tables}")

            for table_name in target_tables:
                try:
                    # Fetch columns
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, DATA_TYPE_NAME
                        FROM SYS.TABLE_COLUMNS
                        WHERE SCHEMA_NAME = '{hana_schema}'
                        AND TABLE_NAME = '{table_name}'
                        ORDER BY POSITION
                    """)
                    columns = cursor.fetchall()

                    if not columns:
                        logger.warning(f"  ⚠️ {table_name} not found in {hana_schema} — skipping")
                        continue

                    # Fetch record count
                    cursor.execute(f"""
                        SELECT RECORD_COUNT FROM SYS.M_TABLES
                        WHERE SCHEMA_NAME = '{hana_schema}'
                        AND TABLE_NAME = '{table_name}'
                    """)
                    row          = cursor.fetchone()
                    record_count = row[0] if row else 0

                    schemas[table_name] = {
                        'source': 'hana',
                        'table_name': table_name,
                        'schema_name': hana_schema,
                        'columns': [col[0] for col in columns],
                        'column_count': len(columns),
                        'record_count': record_count,
                        'data_types': {col[0]: col[1] for col in columns}
                    }

                    logger.info(f"  ✓ {table_name}: {len(columns)} columns, {record_count:,} records")

                except Exception as e:
                    logger.warning(f"  ⚠️ Skipping {table_name}: {e}")
                    continue

            # Step 3 — Auto-discover relationships from HANA foreign keys
            # Uses target_tables from .env — no hardcoding
            try:
                tables_str = "', '".join(target_tables)
                cursor.execute(f"""
                    SELECT TABLE_NAME, COLUMN_NAME,
                           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM SYS.REFERENTIAL_CONSTRAINTS
                    WHERE SCHEMA_NAME = '{hana_schema}'
                    AND TABLE_NAME IN ('{tables_str}')
                """)
                fk_rows = cursor.fetchall()

                relationship_list = []
                for table, col, ref_table, ref_col in fk_rows:
                    rel = f'"{hana_schema}"."{table}".{col} = "{hana_schema}"."{ref_table}".{ref_col}'
                    relationship_list.append(rel)

                # Attach relationships to every table's schema dict
                for table_name in schemas:
                    schemas[table_name]['relationships'] = relationship_list

                logger.info(f"✅ Auto-discovered {len(relationship_list)} table relationships from HANA")

            except Exception as e:
                logger.warning(f"⚠️ Could not fetch relationships: {e} — GPT will infer from column names")
                for table_name in schemas:
                    schemas[table_name]['relationships'] = []

            conn.close()
            logger.info(f"✅ HANA discovery complete — {len(schemas)} tables loaded")
            return schemas

        except ImportError:
            logger.warning("hdbcli not installed - HANA schema discovery skipped")
            return {}
        except Exception as e:
            logger.error(f"❌ HANA schema discovery failed: {e}")
            return {}

    # ============================================================
    # SAP RFC SCHEMA DISCOVERY
    # ============================================================

    def _discover_from_rfc(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover schemas via SAP RFC.
        Tables driven by HANA_TABLES in .env — no hardcoding.
        """
        try:
            from pyrfc import Connection

            conn = Connection(
                ashost=self.config.SAP_ASHOST,
                sysnr=self.config.SAP_SYSNR,
                client=self.config.SAP_CLIENT,
                user=self.config.SAP_USER,
                passwd=self.config.SAP_PASSWORD
            )

            # Get target tables from .env — no hardcoding
            hana_tables_env = getattr(self.config, 'HANA_TABLES', '')
            if not hana_tables_env:
                logger.error("❌ HANA_TABLES not set in .env — RFC discovery skipped")
                logger.error("   Example: HANA_TABLES=VBAK,VBAP,VBEP,KNA1,MARA,EKKO,EKPO")
                conn.close()
                return {}

            sap_tables = [t.strip() for t in hana_tables_env.split(',')]
            logger.info(f"📋 RFC loading {len(sap_tables)} tables: {sap_tables}")

            schemas = {}
            for table_name in sap_tables:
                try:
                    result = conn.call('DDIF_FIELDINFO_GET', TABNAME=table_name)
                    if result['DFIES_TAB']:
                        fields = result['DFIES_TAB']
                        schemas[table_name] = {
                            'source': 'rfc',
                            'table_name': table_name,
                            'columns': [f['FIELDNAME'] for f in fields],
                            'column_count': len(fields),
                            'data_types': {f['FIELDNAME']: f['DATATYPE'] for f in fields}
                        }
                        logger.info(f"  ✓ {table_name}: {len(fields)} fields")
                except Exception as e:
                    logger.warning(f"  ⚠️ Skipping {table_name}: {e}")
                    continue

            conn.close()
            return schemas

        except ImportError:
            logger.warning("pyrfc not installed - RFC schema discovery skipped")
            return {}
        except Exception as e:
            logger.warning(f"RFC schema discovery failed: {e}")
            return {}

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    def get_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        return self.schemas.get(table_name.upper())

    def get_all_tables(self) -> List[str]:
        return list(self.schemas.keys())

    def get_columns(self, table_name: str) -> List[str]:
        schema = self.get_schema(table_name)
        return schema.get('columns', []) if schema else []

    def get_data_types(self, table_name: str) -> Dict[str, str]:
        schema = self.get_schema(table_name)
        return schema.get('data_types', {}) if schema else {}

    def format_for_ai(self) -> str:
        if not self.schemas:
            return "No schemas available"
        lines = ["Available SAP Tables:\n"]
        for table_name, schema in self.schemas.items():
            lines.append(f"\n**{table_name}**")
            lines.append(f"  Source: {schema['source']}")
            lines.append(f"  Records: {schema.get('record_count', 'Unknown')}")
            lines.append(f"  Columns ({schema['column_count']}): {', '.join(schema['columns'][:10])}")
            if schema['column_count'] > 10:
                lines.append(f"  ... and {schema['column_count'] - 10} more columns")
        return "\n".join(lines)

    def export_schemas(self) -> Dict[str, Any]:
        return {
            'total_tables': len(self.schemas),
            'tables': self.schemas,
            'summary': {
                table: {
                    'columns': len(schema['columns']),
                    'records': schema.get('record_count', 0),
                    'source': schema['source']
                }
                for table, schema in self.schemas.items()
            }
        }