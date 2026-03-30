#!/usr/bin/env python
"""
Verify RBAC database migration
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n" + "=" * 70)
print("✅ DATABASE TABLES VERIFICATION - RBAC MIGRATION")
print("=" * 70)

inspector = inspect(engine)
tables = inspector.get_table_names()

print(f"Total tables in database: {len(tables)}\n")

# Check for RBAC tables
rbac_tables = ["users", "user_company_roles", "contracts", "otp_tokens", "audit_logs"]
print("RBAC Tables Status:")
print("-" * 70)

for table in rbac_tables:
    if table in tables:
        columns = inspector.get_columns(table)
        col_names = [col["name"] for col in columns]
        print(f"✅ {table:25s} : {len(columns)} columns")
        print(f"   └─ {', '.join(col_names[:4])}")
    else:
        print(f"❌ {table:25s} : NOT FOUND")

# Display existing tables
print("\n" + "-" * 70)
print("All Tables in Database:")
print("-" * 70)

for i, table in enumerate(sorted(tables), 1):
    status = "🆕 RBAC" if table in rbac_tables else "📦"
    print(f"  {i:2d}. {status:12s} {table}")

print("\n" + "=" * 70)

# Verify indices for RBAC tables
print("Indices for RBAC Tables:")
print("-" * 70)

for table in rbac_tables:
    if table in tables:
        indices = inspector.get_indexes(table)
        if indices:
            print(f"\n{table}:")
            for idx in indices:
                idx_name = idx["name"]
                idx_cols = ", ".join(idx["column_names"])
                print(f"  - {idx_name} ON ({idx_cols})")
        else:
            print(f"\n{table}: No indices")

print("\n" + "=" * 70)
print("✅ MIGRATION VERIFICATION COMPLETE")
print("=" * 70)
