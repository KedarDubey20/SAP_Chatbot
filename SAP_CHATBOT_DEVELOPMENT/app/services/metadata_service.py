"""
Metadata Service
=================================================
Handles TWO things:
  1. Auto-generates column descriptions (metadata) for any client's tables
  2. Auto-generates relationships.json from HANA column matching

WHY THIS EXISTS:
  - GPT needs to know what each column means to write correct SQL
  - Without this, GPT hallucinates column names and wrong tables
  - Hardcoding metadata breaks for different clients
  - This auto-generates it from HANA itself — works for ANY client

HOW IT WORKS:
  - On boot: checks which tables exist in HANA
  - Compares with what's already in generated_metadata.json
  - Only processes NEW tables (incremental — skips existing)
  - Persists everything to app/config/ so it survives reboots
  - relationships.json is also auto-generated, not manually maintained

PERFORMANCE:
  - Max 5 tables processed simultaneously (semaphore)
  - Each table's batches run in parallel (max 6 at once)
  - Batch size = 50 columns -> 100% coverage guaranteed
  - 120s timeout per GPT call -> never hangs forever
  - WELL_KNOWN_SAP_COLS pre-filled -> no GPT call needed for standard fields
  - First boot: ~3-5 minutes | Every boot after: ~0 seconds

FILES WRITTEN:
  app/config/generated_metadata.json   <- column descriptions per table
  app/config/relationships.json        <- auto-detected join relationships
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


METADATA_PATH      = Path("app/config/generated_metadata.json")
RELATIONSHIPS_PATH = Path("app/config/relationships.json")

# Columns to skip - appear everywhere, meaningless for joins
SKIP_COLUMNS = {"MANDT", "AEDAT", "ERDAT", "ERNAM", "AENAM", "LAEDA"}

# Concurrency controls
MAX_CONCURRENT_TABLES  = 5    # max tables generating metadata at once
MAX_CONCURRENT_BATCHES = 6    # max GPT batch calls per table at once
BATCH_SIZE             = 50   # columns per GPT call - 50 guarantees 100% coverage
GPT_TIMEOUT_SECONDS    = 120  # hard timeout per GPT call - never hang

# Standard SAP fields — pre-filled, no GPT call needed
# These are identical in every SAP system worldwide
WELL_KNOWN_SAP_COLS = {
    'MANDT': 'Client or Mandant key',
    'ERDAT': 'Record creation date',
    'ERNAM': 'Created by username',
    'AEDAT': 'Last changed date',
    'AENAM': 'Last changed by username',
    'LAEDA': 'Last change date',
    'VBELN': 'Sales or purchasing document number',
    'POSNR': 'Item or position number',
    'MATNR': 'Material number',
    'KUNNR': 'Customer number padded to 10 digits',
    'LIFNR': 'Vendor or supplier number',
    'EBELN': 'Purchase order number',
    'EBELP': 'Purchase order item number',
    'WERKS': 'Plant code',
    'LGORT': 'Storage location',
    'BUKRS': 'Company code',
    'WAERS': 'Currency key for purchasing documents',
    'WAERK': 'Currency key for sales documents',
    'NETWR': 'Net value or amount',
    'MENGE': 'Quantity',
    'MEINS': 'Base unit of measure',
    'MATKL': 'Material group',
    'MTART': 'Material type',
    'LAND1': 'Country key',
    'SPRAS': 'Language key',
    'STRAS': 'Street address',
    'ORT01': 'City name',
    'PSTLZ': 'Postal code',
    'TELF1': 'Telephone number',
    'NAME1': 'Primary name field',
    'NAME2': 'Secondary name field',
    'VKORG': 'Sales organization',
    'VTWEG': 'Distribution channel',
    'SPART': 'Division',
    'AUART': 'Sales document type',
    'BSART': 'Purchase order document type',
    'BEDAT': 'Purchase order date',
    'NETPR': 'Net price',
    'PEINH': 'Price unit',
    'PSTYV': 'Sales document item category',
    'KWMENG': 'Cumulative order quantity',
    'ARKTX': 'Short text for sales order item',
    'AUDAT': 'Order date',
    'VKBUR': 'Sales office',
    'VKGRP': 'Sales group',
    'KDGRP': 'Customer group',
    'ZTERM': 'Payment terms key',
    'KNUMV': 'Document condition number',
    'LIFSK': 'Delivery block',
    'FAKSK': 'Billing block',
    'GBSTK': 'Overall processing status',
    'LFSTK': 'Delivery status',
    'FKSTK': 'Billing status',
    'ABSTK': 'Rejection status',
    'INCO1': 'Incoterms part 1',
    'INCO2': 'Incoterms part 2',
    'ETENR': 'Schedule line number',
    'EDATU': 'Delivery date',
    'WMENG': 'Scheduled quantity',
    'BMENG': 'Confirmed quantity',
    'EINDT': 'Requested delivery date',
    'MAKTX': 'Material description text',
    'BISMT': 'Old material number',
    'BRGEW': 'Gross weight',
    'NTGEW': 'Net weight',
    'GEWEI': 'Weight unit',
    'VOLUM': 'Volume',
    'VOLEH': 'Volume unit',
    'EKGRP': 'Purchasing group',
    'EKORG': 'Purchasing organization',
    'LPEIN': 'Category of delivery date',
    'LMEIN': 'Order unit',
    'BPRME': 'Order price unit',
    'PRSDT': 'Date for price determination',
    'WKURS': 'Exchange rate',
    'KUFIX': 'Fixed exchange rate',
}


class MetadataService:
    """
    Auto-generates and persists table metadata + relationships.
    Completely client-agnostic - works for any set of tables.
    """

    def __init__(
        self,
        hana_host,
        hana_port,
        hana_user,
        hana_password,
        hana_schema,
        ai_client,
        ai_deployment
    ):
        self.hana_host     = hana_host
        self.hana_port     = hana_port
        self.hana_user     = hana_user
        self.hana_password = hana_password
        self.hana_schema   = hana_schema
        self.ai_client     = ai_client
        self.ai_deployment = ai_deployment

        # Ensure config dir exists
        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT - called once on boot from main.py
    # ══════════════════════════════════════════════════════════════════

    async def run(self, current_tables: list, schema_info: dict):
        """
        Main method - called on startup.
        Only processes tables not already in metadata (incremental).
        """
        logger.info("🔍 MetadataService: checking what needs generating...")

        existing_metadata = self._load_metadata()
        existing_tables   = set(existing_metadata.keys())
        current_set       = set(current_tables)

        # Tables removed from env - clean them up
        removed = existing_tables - current_set
        if removed:
            for t in removed:
                existing_metadata.pop(t, None)
            logger.info(f"🗑️ Removed stale metadata for: {removed}")

        # Tables that are new - need metadata generated
        new_tables = current_set - existing_tables

        if new_tables:
            logger.info(f"✨ New tables detected: {new_tables} — generating metadata...")
            logger.info(
                f"⚙️  Config: batch_size={BATCH_SIZE}, "
                f"max_tables={MAX_CONCURRENT_TABLES}, "
                f"max_batches={MAX_CONCURRENT_BATCHES}, "
                f"timeout={GPT_TIMEOUT_SECONDS}s, "
                f"pre_filled={len(WELL_KNOWN_SAP_COLS)} known cols"
            )

            # Semaphore limits how many tables generate at once
            table_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABLES)

            async def _generate_one(table):
                async with table_semaphore:
                    if table in schema_info:
                        desc = await self._generate_table_metadata(
                            table, schema_info[table]
                        )
                        logger.info(f"✅ Metadata generated for {table}")
                        return table, desc
                    return table, {}

            results = await asyncio.gather(*[_generate_one(t) for t in new_tables])

            for table, desc in results:
                existing_metadata[table] = desc

        else:
            logger.info("✅ Metadata up to date — no new tables")

        # Always save
        self._save_metadata(existing_metadata)

        # Auto-generate relationships
        self._generate_relationships(schema_info)

        logger.info("✅ MetadataService complete")
        return existing_metadata

    # ══════════════════════════════════════════════════════════════════
    # METADATA GENERATION
    # ══════════════════════════════════════════════════════════════════

    async def _generate_table_metadata(
        self,
        table_name: str,
        table_data: dict
    ) -> dict:
        """
        Pre-fills well-known SAP columns instantly (no GPT needed).
        Sends only unknown columns to GPT in batches of 50.
        All batches run in parallel (max 6 at once).
        Each GPT call has a 120s timeout.
        Missing columns auto-filled with "unknown SAP field".
        """
        columns     = table_data.get("columns", [])
        sample_rows = table_data.get("sample_rows", [])

        # Build compact sample text
        sample_text = ""
        if sample_rows:
            for i, row in enumerate(sample_rows[:2]):
                sample_text += f"Row {i+1}: {dict(list(row.items())[:20])}\n"

        # ── Pre-fill well-known SAP columns — zero GPT calls needed ──
        known_columns   = {
            col: desc
            for col, desc in WELL_KNOWN_SAP_COLS.items()
            if col in columns
        }
        unknown_columns = [col for col in columns if col not in WELL_KNOWN_SAP_COLS]

        logger.info(
            f"📦 {table_name}: {len(columns)} total → "
            f"{len(known_columns)} pre-filled, "
            f"{len(unknown_columns)} need GPT → "
            f"{max(1, -(-len(unknown_columns) // BATCH_SIZE))} batch(es)"
        )

        # Only batch the unknown columns
        batches = [
            unknown_columns[i:i + BATCH_SIZE]
            for i in range(0, len(unknown_columns), BATCH_SIZE)
        ]

        # Semaphore limits concurrent batches per table
        batch_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

        async def _describe_batch(batch_cols: list) -> dict:
            async with batch_semaphore:
                # Dynamic tokens: each col needs ~25 tokens, floor 800, ceil 4096
                dynamic_max_tokens = min(4096, max(800, len(batch_cols) * 25))

                # Numbered list so GPT cannot skip
                col_list = "\n".join([f"{i+1}. {c}" for i, c in enumerate(batch_cols)])

                prompt = f"""You are an SAP data dictionary expert.

Table: {table_name}
Sample data:
{sample_text}

You MUST describe ALL {len(batch_cols)} columns listed below. No skipping allowed.

{col_list}

Return ONLY valid JSON in this exact format:
{{
    "columns": {{
        "COLUMN_NAME": "description max 8 words",
        "COLUMN_NAME2": "description max 8 words"
    }}
}}

CRITICAL RULES:
- Output MUST contain exactly {len(batch_cols)} entries
- Use the EXACT column name as the key (copy it exactly)
- Every single column in the list above must appear in your output
- If meaning is unclear, write "unknown SAP field"
- No explanations, no markdown, only the JSON object
"""
                try:
                    response = self.ai_client.chat.completions.create(
                        model=self.ai_deployment,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    f"You are an SAP ABAP data dictionary. "
                                    f"You MUST describe all {len(batch_cols)} columns. "
                                    f"Return only valid JSON with exactly {len(batch_cols)} entries. "
                                    f"Never skip a column."
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        response_format={"type": "json_object"},
                        max_tokens=dynamic_max_tokens,
                        timeout=GPT_TIMEOUT_SECONDS
                    )

                    result = json.loads(
                        response.choices[0].message.content
                    ).get("columns", {})

                    # Fill any GPT missed
                    for col in batch_cols:
                        if col not in result:
                            result[col] = "unknown SAP field"

                    return result

                except Exception as e:
                    logger.warning(
                        f"⚠️ Batch failed for {table_name} "
                        f"({len(batch_cols)} cols): {e}"
                    )
                    return {col: "unknown SAP field" for col in batch_cols}

        # ── All batches for this table run in parallel ────────────────
        batch_results = await asyncio.gather(
            *[_describe_batch(b) for b in batches]
        ) if batches else []

        # ── Merge: start with pre-filled known, then add GPT results ──
        all_columns = {**known_columns}
        for result in batch_results:
            all_columns.update(result)

        # Final safety fill - guarantee 100% coverage
        for col in columns:
            if col not in all_columns:
                all_columns[col] = "unknown SAP field"

        # Log coverage
        described = sum(1 for v in all_columns.values() if v != "unknown SAP field")
        coverage  = described / len(columns) if columns else 0
        logger.info(
            f"  📊 {table_name}: {described}/{len(columns)} cols described "
            f"({coverage:.0%} coverage) | "
            f"{len(known_columns)} pre-filled + "
            f"{described - len(known_columns)} GPT-described"
        )

        # Infer key columns from SAP naming conventions
        key_columns = [
            c for c in columns
            if any(c.endswith(x) for x in ['NR', 'ID', 'NO', 'KEY', 'ELN', 'SNR'])
        ][:3]

        return {
            "description": f"{table_name} SAP table ({len(columns)} columns)",
            "key_columns":  key_columns,
            "columns":      all_columns
        }

    # ══════════════════════════════════════════════════════════════════
    # RELATIONSHIP GENERATION
    # ══════════════════════════════════════════════════════════════════

    def _generate_relationships(self, schema_info: dict):
        """
        Auto-detect join relationships from column name matching.
        First tries HANA FK constraints, falls back to column matching.
        Skips if schema_info is empty (HANA was down).
        """
        # Guard - don't wipe existing file if HANA was down
        if not schema_info:
            logger.warning(
                "⚠️ schema_info empty — skipping relationships "
                "update to preserve existing file"
            )
            return

        logger.info("🔗 Auto-detecting table relationships...")

        # Priority 1 - HANA FK constraints
        hana_rels = self._query_hana_fk_constraints()
        if hana_rels:
            self._save_relationships(hana_rels)
            logger.info(f"✅ {len(hana_rels)} relationships from HANA FK constraints")
            return

        # Priority 2 - column name matching
        column_to_tables: Dict[str, list] = {}
        for table, table_data in schema_info.items():
            columns = (
                table_data.get("columns", [])
                if isinstance(table_data, dict)
                else []
            )
            for col in columns:
                if col.upper() in SKIP_COLUMNS:
                    continue
                if col not in column_to_tables:
                    column_to_tables[col] = []
                column_to_tables[col].append(table)

        relationships = {}
        for col, tables in column_to_tables.items():
            if len(tables) < 2:
                continue

            tables_sorted = sorted(tables, key=lambda t: (
                0 if col.startswith(t[:2]) or col.startswith(t[:3]) else 1,
                len(t)
            ))

            parent = tables_sorted[0]
            for child in tables_sorted[1:]:
                key = f"{child}.{col}"
                val = f"{parent}.{col}"
                if key != val:
                    relationships[key] = val

        self._save_relationships(relationships)
        logger.info(f"✅ {len(relationships)} relationships inferred from column matching")

    def _query_hana_fk_constraints(self) -> dict:
        """Try to get FK constraints from HANA SYS tables."""
        try:
            from hdbcli import dbapi
            conn = dbapi.connect(
                address=self.hana_host,
                port=self.hana_port,
                user=self.hana_user,
                password=self.hana_password
            )
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT TABLE_NAME, COLUMN_NAME,
                       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM SYS.REFERENTIAL_CONSTRAINTS
                WHERE SCHEMA_NAME = '{self.hana_schema}'
            """)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {}

            rels = {}
            for row in rows:
                child_table, child_col, parent_table, parent_col = row
                rels[f"{child_table}.{child_col}"] = f"{parent_table}.{parent_col}"
            return rels

        except Exception as e:
            logger.warning(f"⚠️ Could not query HANA FK constraints: {e}")
            return {}

    # ══════════════════════════════════════════════════════════════════
    # FILE I/O
    # ══════════════════════════════════════════════════════════════════

    def _load_metadata(self) -> dict:
        if METADATA_PATH.exists():
            try:
                return json.loads(METADATA_PATH.read_text())
            except Exception as e:
                logger.warning(f"⚠️ Could not load metadata file: {e}")
        return {}

    def _save_metadata(self, metadata: dict):
        try:
            METADATA_PATH.write_text(json.dumps(metadata, indent=2))
            logger.info(f"💾 Metadata saved → {METADATA_PATH}")
        except Exception as e:
            logger.error(f"❌ Could not save metadata: {e}")

    def _save_relationships(self, relationships: dict):
        try:
            RELATIONSHIPS_PATH.write_text(json.dumps(relationships, indent=2))
            logger.info(f"💾 Relationships saved → {RELATIONSHIPS_PATH}")
        except Exception as e:
            logger.error(f"❌ Could not save relationships: {e}")

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC LOADER - used by ai_service._format_schema_for_prompt
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def load_metadata() -> dict:
        """Load persisted metadata. Returns {} if not yet generated."""
        if METADATA_PATH.exists():
            try:
                return json.loads(METADATA_PATH.read_text())
            except Exception:
                return {}
        return {}