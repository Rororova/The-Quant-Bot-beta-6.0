#!/usr/bin/env python3
"""
Migration runner for Supabase database
Run this script to apply all migrations to your Supabase database
"""

import os
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client() -> Client:
    """Get Supabase client from environment variables"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # Use service role key for migrations
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
        print("\nRequired environment variables:")
        print("  SUPABASE_URL=https://your-project.supabase.co")
        print("  SUPABASE_SERVICE_ROLE_KEY=your-service-role-key")
        sys.exit(1)
    
    return create_client(supabase_url, supabase_key)

def get_migration_files():
    """Get all migration files in order"""
    migrations_dir = Path(__file__).parent
    migration_files = sorted(migrations_dir.glob('*.sql'))
    return migration_files

def run_migration(client: Client, migration_file: Path):
    """Run a single migration file"""
    print(f"\n📄 Running migration: {migration_file.name}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Split by semicolons and execute each statement
    # Note: Supabase PostgREST doesn't support raw SQL execution directly
    # You'll need to run these migrations through Supabase SQL Editor or use psycopg2
    
    print(f"⚠️  Note: This migration needs to be run manually in Supabase SQL Editor")
    print(f"   File: {migration_file}")
    print(f"   Content preview (first 200 chars): {sql_content[:200]}...")
    
    return True

def main():
    """Main migration runner"""
    print("🚀 Starting database migrations...")
    
    client = get_supabase_client()
    print("✅ Connected to Supabase")
    
    migration_files = get_migration_files()
    
    if not migration_files:
        print("❌ No migration files found!")
        return
    
    print(f"\n📋 Found {len(migration_files)} migration(s):")
    for mf in migration_files:
        print(f"   - {mf.name}")
    
    print("\n" + "="*60)
    print("⚠️  IMPORTANT: Supabase PostgREST API doesn't support")
    print("   raw SQL execution. You need to run migrations manually:")
    print("\n   1. Go to your Supabase Dashboard")
    print("   2. Navigate to SQL Editor")
    print("   3. Copy the contents of each migration file")
    print("   4. Run them in order (001, 002, etc.)")
    print("="*60)
    
    print("\n📝 Migration files to run:")
    for i, mf in enumerate(migration_files, 1):
        print(f"\n{i}. {mf.name}")
        print(f"   Path: {mf}")
        with open(mf, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   Lines: {len(content.splitlines())}")
    
    print("\n✅ Migration files prepared. Please run them in Supabase SQL Editor.")

if __name__ == "__main__":
    main()

