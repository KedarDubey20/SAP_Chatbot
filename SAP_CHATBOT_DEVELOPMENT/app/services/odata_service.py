"""
OData Service
=================================================
Replaces direct SAP HANA connection with OData REST API.
Connects to Primus CDS OData service.

BASE URL: http://primushana.primustechsys.com:8001/sap/opu/odata/sap/ZSALESORDERCHATBOT_CDS
ENTITY:   zsalesorderchatbot

KEY FIELDS CONFIRMED:
  SalesOrder          - Sales order number
  SalesOrderType      - Document type (OR = standard)
  CreationDate        - Order creation date (epoch ms format)
  SalesOrganization   - Sales org code
  SoldToParty         - Customer number
  TotalNetAmount      - Net order value
  TransactionCurrency - Currency (INR, USD etc)
  SalesOrderItem      - Line item number

NAVIGATION PROPERTIES (expandable):
  to_Item             - Sales order items
  to_Partner          - Partners on order
  to_SoldToParty      - Sold-to customer details
  to_PricingElement   - Pricing conditions
  to_ScheduleLine     - Delivery schedule lines
  to_SalesOrganization
  to_SalesOrderType

OData LIMITATIONS vs SQL:
  - No SUM/COUNT/GROUP BY natively
  - Aggregation done in Python after fetching data
  - Date format: /Date(epochms)/ must be converted
  - $top max may be limited by SAP server (usually 1000)
"""

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from loguru import logger
from decimal import Decimal
import json


# ── Connection config ─────────────────────────────────────────────
ODATA_BASE_URL = "http://primushana.primustechsys.com:8001/sap/opu/odata/sap/ZSALESORDERCHATBOT_CDS"
ODATA_USER     = "102703"
ODATA_PASSWORD = "Primus@2026"
MAIN_ENTITY    = "zsalesorderchatbot"

# Key fields available in the entity
AVAILABLE_FIELDS = [
    "SalesOrder", "SalesOrderType", "CreationDate", "SalesOrganization",
    "SoldToParty", "TotalNetAmount", "TransactionCurrency", "SalesOrderItem",
    "SalesDocumentRjcnReason", "OverallSDProcessStatus", "OverallDeliveryStatus",
    "OverallBillingBlockStatus", "OverallDeliveryBlockStatus",
    "IncotermsClassification", "CustomerPaymentTerms", "ShippingCondition",
    "SalesDistrict", "SalesGroup", "SalesOffice", "CustomerGroup",
    "PricingDate", "RequestedDeliveryDate", "LastChangeDate",
    "PurchaseOrderByCustomer", "CustomerPurchaseOrderDate"
]


class ODataService:
    """
    Handles all data operations via SAP OData REST API.
    Replaces direct HANA hdbcli connection.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(ODATA_USER, ODATA_PASSWORD)
        self.session.headers.update({
            "Accept":       "application/json",
            "Content-Type": "application/json"
        })
        self._schema_cache = None
        logger.info("✓ ODataService initialized")

    # ══════════════════════════════════════════════════════════════════
    # CORE FETCH
    # ══════════════════════════════════════════════════════════════════

    def fetch(
        self,
        entity: str = MAIN_ENTITY,
        params: Optional[Dict] = None,
        top: int = 100,
        select: Optional[List[str]] = None,
        filter_str: Optional[str] = None,
        expand: Optional[str] = None,
        orderby: Optional[str] = None,
        count: bool = False
    ) -> List[Dict]:
        """
        Fetch records from OData entity with optional filters.
        Returns list of dicts with normalized field values.
        """
        query_params = {"$format": "json", "$top": top}

        if select:
            query_params["$select"] = ",".join(select)
        if filter_str:
            query_params["$filter"] = filter_str
        if expand:
            query_params["$expand"] = expand
        if orderby:
            query_params["$orderby"] = orderby
        if count:
            query_params["$inlinecount"] = "allpages"
        if params:
            query_params.update(params)

        url = f"{ODATA_BASE_URL}/{entity}"

        try:
            logger.info(f"🌐 OData GET: {entity} | params: {query_params}")
            response = self.session.get(url, params=query_params, timeout=30)
            response.raise_for_status()

            data    = response.json()
            results = data.get("d", {}).get("results", [])

            # Normalize values
            normalized = [self._normalize_record(r) for r in results]
            logger.info(f"✅ OData returned {len(normalized)} records")
            return normalized

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ OData request failed: {e}")
            raise

    def fetch_all(
        self,
        entity: str = MAIN_ENTITY,
        select: Optional[List[str]] = None,
        filter_str: Optional[str] = None,
        max_records: int = 5000
    ) -> List[Dict]:
        """
        Fetch all records using pagination ($skiptoken).
        Used for aggregation queries that need full dataset.
        """
        all_results = []
        skip        = 0
        page_size   = 500

        while len(all_results) < max_records:
            query_params = {
                "$format": "json",
                "$top":    page_size,
                "$skip":   skip
            }
            if select:
                query_params["$select"] = ",".join(select)
            if filter_str:
                query_params["$filter"] = filter_str

            url = f"{ODATA_BASE_URL}/{entity}"

            try:
                response = self.session.get(url, params=query_params, timeout=30)
                response.raise_for_status()
                data    = response.json()
                results = data.get("d", {}).get("results", [])

                if not results:
                    break

                normalized = [self._normalize_record(r) for r in results]
                all_results.extend(normalized)

                if len(results) < page_size:
                    break  # Last page

                skip += page_size
                logger.debug(f"📄 Fetched {len(all_results)} records so far...")

            except Exception as e:
                logger.error(f"❌ Pagination error at skip={skip}: {e}")
                break

        logger.info(f"✅ Total fetched: {len(all_results)} records")
        return all_results

    # ══════════════════════════════════════════════════════════════════
    # SCHEMA DISCOVERY — replaces _get_schema() in sap_service
    # ══════════════════════════════════════════════════════════════════

    def get_schema(self) -> Dict[str, Any]:
        """
        Returns schema info compatible with ai_service expectations.
        Fetches sample records to discover field formats.
        """
        if self._schema_cache:
            return self._schema_cache

        try:
            # Get sample records to show field formats
            sample = self.fetch(
                entity=MAIN_ENTITY,
                top=3,
                select=AVAILABLE_FIELDS[:20]
            )

            schema = {
                "zsalesorderchatbot": {
                    "columns":        AVAILABLE_FIELDS,
                    "sample_rows":    sample[:3],
                    "distinct_values": self._get_distinct_values(),
                    "description":    "SAP Sales Order CDS View — header + item combined"
                }
            }

            self._schema_cache = schema
            logger.info(f"✅ OData schema discovered: {len(AVAILABLE_FIELDS)} fields")
            return schema

        except Exception as e:
            logger.error(f"❌ Schema discovery failed: {e}")
            return {}

    def _get_distinct_values(self) -> Dict:
        """Get distinct values for key categorical fields."""
        distinct = {}
        try:
            records = self.fetch_all(
                select=["SalesOrderType", "TransactionCurrency", "SalesOrganization"],
                max_records=1000
            )

            for field in ["SalesOrderType", "TransactionCurrency", "SalesOrganization"]:
                vals = list({r.get(field) for r in records if r.get(field)})
                distinct[field] = [{"value": v, "count": 0} for v in vals[:20]]

        except Exception as e:
            logger.warning(f"⚠️ Could not get distinct values: {e}")

        return distinct

    # ══════════════════════════════════════════════════════════════════
    # BUSINESS QUERIES — replaces SQL queries
    # ══════════════════════════════════════════════════════════════════

    def execute_natural_language_query(
        self,
        odata_params: Dict
    ) -> List[Dict]:
        """
        Execute an OData query from AI-generated parameters.
        Called by sap_service instead of _execute_sql_query.
        """
        entity     = odata_params.get("entity", MAIN_ENTITY)
        select     = odata_params.get("select")
        filter_str = odata_params.get("filter")
        top        = odata_params.get("top", 10)
        orderby    = odata_params.get("orderby")
        expand     = odata_params.get("expand")
        aggregate  = odata_params.get("aggregate")  # Python-side aggregation

        if aggregate:
            return self._execute_aggregation(
                select     = select,
                filter_str = filter_str,
                aggregate  = aggregate
            )

        return self.fetch(
            entity     = entity,
            select     = select,
            filter_str = filter_str,
            top        = top,
            orderby    = orderby,
            expand     = expand
        )

    def _execute_aggregation(
        self,
        select: Optional[List[str]],
        filter_str: Optional[str],
        aggregate: Dict
    ) -> List[Dict]:
        """
        Fetch full dataset and aggregate in Python.
        Handles: count, sum, group_by, top_n.

        aggregate dict format:
        {
            "type": "count" | "sum" | "group_by",
            "field": "TotalNetAmount",      # for sum
            "group_by": "SoldToParty",      # for group_by
            "order": "desc",
            "limit": 10
        }
        """
        agg_type = aggregate.get("type")
        field    = aggregate.get("field")
        group_by = aggregate.get("group_by")
        limit    = aggregate.get("limit", 10)

        # Always fetch minimal fields needed
        fetch_fields = ["SalesOrder", "TransactionCurrency"]
        if field:
            fetch_fields.append(field)
        if group_by:
            fetch_fields.append(group_by)

        records = self.fetch_all(
            select     = list(set(fetch_fields)),
            filter_str = filter_str,
            max_records = 5000
        )

        if agg_type == "count":
            return [{"COUNT": len(records)}]

        if agg_type == "sum" and field:
            # Sum per currency to avoid mixing
            totals = {}
            for r in records:
                currency = r.get("TransactionCurrency", "UNKNOWN")
                val      = float(r.get(field, 0) or 0)
                totals[currency] = totals.get(currency, 0) + val
            return [
                {"TransactionCurrency": k, f"TOTAL_{field.upper()}": round(v, 2)}
                for k, v in totals.items()
            ]

        if agg_type == "group_by" and group_by:
            # Group and count/sum per group
            groups: Dict[str, Dict] = {}
            for r in records:
                key = r.get(group_by, "UNKNOWN")
                if key not in groups:
                    groups[key] = {"COUNT": 0, "TOTAL": 0.0}
                groups[key]["COUNT"] += 1
                if field:
                    groups[key]["TOTAL"] += float(r.get(field, 0) or 0)

            results = [
                {group_by: k, "ORDER_COUNT": v["COUNT"], "TOTAL_VALUE": round(v["TOTAL"], 2)}
                for k, v in groups.items()
            ]

            # Sort by count descending
            results.sort(key=lambda x: x["ORDER_COUNT"], reverse=True)
            return results[:limit]

        return records[:limit]

    # ══════════════════════════════════════════════════════════════════
    # DATA CONTEXT HELPERS — replaces sap_service helpers
    # ══════════════════════════════════════════════════════════════════

    def get_date_range(self) -> str:
        """Get min/max order creation dates."""
        try:
            oldest = self.fetch(
                select  = ["SalesOrder", "CreationDate"],
                orderby = "CreationDate asc",
                top     = 1
            )
            newest = self.fetch(
                select  = ["SalesOrder", "CreationDate"],
                orderby = "CreationDate desc",
                top     = 1
            )
            if oldest and newest:
                min_date = oldest[0].get("CreationDate", "")
                max_date = newest[0].get("CreationDate", "")
                return f"Data available from {min_date} to {max_date}"
        except Exception as e:
            logger.warning(f"⚠️ Could not get date range: {e}")
        return ""

    def get_currencies(self) -> str:
        """Get distinct currencies in use."""
        try:
            records = self.fetch(
                select = ["TransactionCurrency"],
                top    = 100
            )
            currencies = list({r.get("TransactionCurrency") for r in records if r.get("TransactionCurrency")})
            return ", ".join(currencies)
        except Exception as e:
            logger.warning(f"⚠️ Could not get currencies: {e}")
        return "INR"

    # ══════════════════════════════════════════════════════════════════
    # NORMALIZERS
    # ══════════════════════════════════════════════════════════════════

    def _normalize_record(self, record: Dict) -> Dict:
        """
        Clean up OData record:
        - Convert /Date(ms)/ to readable date string
        - Remove __metadata and __deferred navigation links
        - Convert string numbers to float where appropriate
        """
        cleaned = {}
        for key, val in record.items():
            if key.startswith("__"):
                continue
            if isinstance(val, dict) and "__deferred" in val:
                continue  # Skip navigation property stubs
            if isinstance(val, str) and val.startswith("/Date("):
                val = self._parse_odata_date(val)
            if key == "TotalNetAmount" and val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
            cleaned[key] = val
        return cleaned

    def _parse_odata_date(self, date_str: str) -> str:
        """Convert /Date(1776643200000)/ to YYYY-MM-DD string."""
        try:
            ms        = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
            dt        = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return date_str

    # ══════════════════════════════════════════════════════════════════
    # ODATA FILTER BUILDER — for common queries
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def build_date_filter(field: str, year: int, month: int) -> str:
        """Build OData date filter for a specific month."""
        from calendar import monthrange
        last_day    = monthrange(year, month)[1]
        start_epoch = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
        end_epoch   = int(datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
        return f"{field} ge datetime'{year}-{month:02d}-01T00:00:00' and {field} le datetime'{year}-{month:02d}-{last_day:02d}T23:59:59'"

    @staticmethod
    def build_customer_filter(customer_id: str) -> str:
        return f"SoldToParty eq '{customer_id}'"

    @staticmethod
    def build_sales_org_filter(org: str) -> str:
        return f"SalesOrganization eq '{org}'"


# ── Singleton ─────────────────────────────────────────────────────
odata_service = ODataService()