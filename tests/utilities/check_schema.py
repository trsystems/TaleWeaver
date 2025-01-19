import sqlite3
import sys

def main():
    db_path = "data/tale_weaver.db"
    try:
        print(f"Connecting to database at: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verify database connection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\nTables in database: {[t[0] for t in tables]}")
        
        # Get table info
        cursor.execute("PRAGMA table_info(characters)")
        columns = cursor.fetchall()
        
        if not columns:
            print("\nError: characters table not found!")
            return
            
        print("\nColumns in characters table:")
        print("cid | name | type | notnull | dflt_value | pk")
        print("----|------|------|---------|------------|---")
        for col in columns:
            print(f"{col[0]:<3} | {col[1]:<10} | {col[2]:<7} | {col[3]:<7} | {col[4] or 'NULL':<10} | {col[5]}")
            
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
