import sqlite3
import os
from typing import Any, List, Dict,Optional
from .tool import tool

# new tools
@tool
def extract_table_metadata(db_path: str, table_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Extract structured metadata from a SQLite database, including primary keys, foreign keys, and field types.

    Args:
        db_path (str): Path to the SQLite database.
        table_names (List[str], optional): Specific tables to inspect.

    Returns:
        Dict[str, Any]: Dictionary with table-level metadata (primary keys, foreign keys, field types).
    """
    import sqlite3
    import os

    if not os.path.exists(db_path):
        return {"error": "❌ Database not found."}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取所有表名
        if table_names is None:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"]

        db_info = {}

        for table in table_names:
            table_info = {
                "primary_key": [],
                "foreign_keys": {},
                "fields": {}
            }

            # 字段信息
            cursor.execute(f"PRAGMA table_info('{table}')")
            for cid, name, dtype, notnull, default, pk in cursor.fetchall():
                table_info["fields"][name] = dtype
                if pk != 0:
                    table_info["primary_key"].append(name)

            # 外键信息
            cursor.execute(f"PRAGMA foreign_key_list('{table}')")
            for row in cursor.fetchall():
                from_col = row[3]
                to_table = row[2]
                table_info["foreign_keys"][from_col] = to_table

            db_info[table] = table_info

        conn.close()
        return db_info

    except Exception as e:
        return {"error": f"❌ Error extracting schema: {str(e)}"}
@tool
def search_table_or_column(db_path: str, keyword: str) -> dict:
    """
    Search for table or column names that fuzzily match the given keyword.
    Useful when the user query contains an approximate or unclear field/table name.

    Args:
        db_path (str): Path to the SQLite database.
        keyword (str): Partial or fuzzy name to search for.

    Returns:
        dict: {
            "matching_tables": [...],
            "matching_columns": {
                "table_name": ["col1", "col2", ...],
                ...
            }
        }
    """
    import sqlite3
    import os

    if not os.path.exists(db_path):
        return {"error": f"Database file not found: {db_path}"}

    keyword_lower = keyword.lower()
    result = {
        "matching_tables": [],
        "matching_columns": {}
    }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]

        # 查找表名匹配
        result["matching_tables"] = [t for t in tables if keyword_lower in t.lower()]

        # 查找列名匹配
        for table in tables:
            cursor.execute(f"PRAGMA table_info('{table}')")
            cols = [col[1] for col in cursor.fetchall()]
            matched = [c for c in cols if keyword_lower in c.lower()]
            if matched:
                result["matching_columns"][table] = matched

        conn.close()
        return result

    except Exception as e:
        return {"error": str(e)}
@tool
def get_table_sample(db_path: str, table_name: str, limit: int = 5) -> List[Dict]:
    """
    Retrieve sample rows from a table for observation.

    Args:
        db_path (str): Path to the SQLite database.
        table_name (str): Table to query.
        limit (int): Number of rows to return (default: 5).

    Returns:
        List[Dict]: A list of rows, each as a dictionary {column_name: value}.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return [{"error": str(e)}]

# @tool
# def get_column_info_all_tables(db_path: str) -> Dict[str, Dict[str, str]]:
#     """
#     Get all column names and types for all tables in the SQLite database.

#     Args:
#         db_path (str): Path to the SQLite database.

#     Returns:
#         dict: A dictionary where each key is a table name, and the value is another
#               dict of column names and their data types.
#     """
#     result = {}
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
        
#         # 获取所有表名
#         cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
#         tables = [row[0] for row in cursor.fetchall()]
        
#         # 获取每张表的 schema 信息
#         for table in tables:
#             cursor.execute(f"PRAGMA table_info('{table}')")
#             schema = cursor.fetchall()
#             result[table] = {col[1]: col[2] for col in schema}
        
#         conn.close()
#         return result

#     except Exception as e:
#         return {"error": str(e)}

# @tool
# def get_column_info(db_path: str, table_name: str) -> dict:
#     """
#     Get all column names and types of a table.

#     Args:
#         db_path (str): Path to the SQLite database.
#         table_name (str): Table to inspect.

#     Returns:
#         dict: A dictionary of column names and their data types.
#     """
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute(f"PRAGMA table_info('{table_name}')")
#         schema = cursor.fetchall()
#         conn.close()
#         return {col[1]: col[2] for col in schema}
#     except Exception as e:
#         return {"error": str(e)}
# @tool
# def search_table_by_column_name(db_path: str, column_name: str) -> dict:
#     """
#     Search which tables contain a given column name in a SQLite database.

#     Args:
#         db_path (str): Full path to the SQLite database.
#         column_name (str): The column name to search for.

#     Returns:
#         dict: Table names where the column appears.
#     """
#     import sqlite3
#     import os

#     if not os.path.exists(db_path):
#         return {"error": f"Database file not found: {db_path}"}

#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()

#         cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
#         tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]

#         result = []
#         for table in tables:
#             try:
#                 cursor.execute(f"PRAGMA table_info('{table}')")
#                 schema = cursor.fetchall()
#                 columns = [col[1] for col in schema]
#                 if column_name in columns:
#                     result.append(table)
#             except Exception as e:
#                 continue  # Skip erroring table

#         conn.close()
#         return {"column": column_name, "tables": result}
#     except Exception as e:
#         return {"error": str(e)}
# old tools
# @tool
# def format_schema_for_prompt(db_path: str, num_rows: int = 1, table_names: Optional[List[str]] = None) -> str:
#     """
#     Extract and format the schema of selected or all tables in a SQLite database.

#     Args:
#         db_path (str): Path to the SQLite database.
#         num_rows (int): Number of sample rows to include (default: 1).
#         table_names (List[str], optional): List of tables to include. If not provided, include all.

#     Returns:
#         str: Formatted schema and sample rows as a prompt-friendly string.
#     """
#     import sqlite3
#     import os

#     if not os.path.exists(db_path):
#         return "❌ Database not found"

#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()

#         # 自动获取所有表（如果未指定）
#         if table_names is None:
#             cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
#             table_names = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]

#         lines = []

#         for table in table_names:
#             cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
#             create_stmt = cursor.fetchone()[0]

#             lines.append(f"-- Table: {table}")
#             lines.append(create_stmt.strip().rstrip(";") + ";")

#             if num_rows > 0:
#                 try:
#                     cursor.execute(f"SELECT * FROM `{table}` LIMIT {num_rows}")
#                     rows = cursor.fetchall()
#                     columns = [desc[0] for desc in cursor.description]
#                     lines.append(f"-- Example rows from {table}:\n{nice_look_table(columns, rows)}")
#                 except Exception as e:
#                     lines.append(f"-- Example rows from {table}: (读取失败: {e})")

#             lines.append("")

#         conn.close()
#         return "\n".join(lines)

#     except Exception as e:
#         return f"❌ Error: {str(e)}"
# @tool
# def get_multiple_table_schemas(db_path: str, table_names: List[str], num_rows: int = 1) -> dict:
#     """
#     Get schema and sample rows for multiple tables from a SQLite database.

#     Args:
#         db_path (str): Path to the SQLite database file.
#         table_names (List[str]): A list of table names to extract.
#         num_rows (int): Number of sample rows per table (default is 1).

#     Returns:
#         dict: A dictionary with schemas for the requested tables.
#     """
#     if not os.path.exists(db_path):
#         return {"error": f"Database not found: {db_path}"}
    
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
#     result = {}

#     for table_name in table_names:
#         try:
#             cursor.execute(f"PRAGMA table_info('{table_name}')")
#             schema = cursor.fetchall()

#             cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {num_rows}")
#             rows = cursor.fetchall()
#             columns = [desc[0] for desc in cursor.description]

#             result[table_name] = {
#                 "columns": {col[1]: col[2] for col in schema},
#                 "sample_rows": [dict(zip(columns, row)) for row in rows]
#             }
#         except Exception as e:
#             result[table_name] = {"error": str(e)}

#     conn.close()
#     return result

# @tool
# def list_tables(db_path: str) -> dict:
#     """
#     List all table names in a SQLite database.

#     Args:
#         db_path (str): The full path to the SQLite database file.

#     Returns:
#         dict: A dictionary containing the list of table names.
#     """
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
#         tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]
#         conn.close()
#         return {"tables": tables}
#     except Exception as e:
#         return {"error": str(e)}
# @tool
# def get_primary_keys(db_path: str, table_name: str) -> List[str]:
#     """
#     Return the primary key columns of a table.

#     Args:
#         db_path (str): Path to the SQLite database.
#         table_name (str): Name of the table.

#     Returns:
#         List[str]: A list of column names that are primary keys.
#     """
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute(f"PRAGMA table_info('{table_name}')")
#         schema = cursor.fetchall()
#         conn.close()
#         return [col[1] for col in schema if col[5] == 1]  # pk flag is at index 5
#     except Exception as e:
#         return [f"error: {str(e)}"]
# @tool
# def get_foreign_keys(db_path: str, table_name: str) -> List[Dict]:
#     """
#     Retrieve foreign key relationships of a specific table.

#     Args:
#         db_path (str): Path to the SQLite database.
#         table_name (str): Name of the table to inspect.

#     Returns:
#         List[Dict]: A list of foreign key mappings, each including 'from_column', 'ref_table', and 'ref_column'.
#     """
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
#         keys = cursor.fetchall()
#         conn.close()
#         return [
#             {
#                 "from_column": row[3],
#                 "ref_table": row[2],
#                 "ref_column": row[4]
#             } for row in keys
#         ]
#     except Exception as e:
#         return [{"error": str(e)}]
# @tool
# def get_database_schema(db_path: str, num_rows: int = 1) -> dict:
#     """
#     Extracts the schema and example data from a SQLite database.

#     Args:
#         db_path (str): The full path to the SQLite database file.
#         num_rows (int): The number of sample rows to return for each table (default is 1).

#     Returns:
#         dict: A dictionary containing table names, CREATE TABLE SQL statements,
#               and sample rows for each table in the database.
#     """
#     return extract_schema_from_sqlite(db_path, num_rows)

# @tool
# def get_table_schema(db_path: str, table_name: str, num_rows: int = 1) -> dict:
#     """
#     Retrieve the schema and sample rows of a specific table from a SQLite database.

#     Args:
#         db_path (str): Full path to the SQLite database.
#         table_name (str): The name of the table to extract.
#         num_rows (int): Number of sample rows to return (default is 1).

#     Returns:
#         dict: Table name, column types, and sample rows.
#     """
#     if not os.path.exists(db_path):
#         return {"error": f"Database not found: {db_path}"}
    
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()

#         # Get column info
#         cursor.execute(f"PRAGMA table_info('{table_name}')")
#         schema = cursor.fetchall()

#         # Get sample data
#         cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {num_rows}")
#         rows = cursor.fetchall()
#         columns = [desc[0] for desc in cursor.description]

#         conn.close()

#         return {
#             "table": table_name,
#             "columns": {col[1]: col[2] for col in schema},  # column_name: type
#             "sample_rows": [dict(zip(columns, row)) for row in rows]
#         }
#     except Exception as e:
#         return {"error": str(e)}


def nice_look_table(column_names: List[str], values: List[List]) -> str:
    if not values:
        return "无数据"
    widths = [
        max(len(str(value[i])) for value in values + [column_names])
        for i in range(len(column_names))
    ]
    header = " | ".join(f"{col:<{w}}" for col, w in zip(column_names, widths))
    divider = "-+-".join("-" * w for w in widths)
    rows = [
        " | ".join(f"{str(val):<{w}}" for val, w in zip(row, widths))
        for row in values
    ]
    return "\n".join([header, divider] + rows)

def extract_schema_from_sqlite(db_path: str, num_rows: int = 3) -> Dict:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库文件未找到: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]

    schema_info = {"db_path": db_path, "tables": []}

    for table in tables:
        cursor.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';"
        )
        create_sql = cursor.fetchone()[0]

        table_entry = {"table_name": table, "create_sql": create_sql}

        if num_rows > 0:
            try:
                cursor.execute(f"SELECT * FROM `{table}` LIMIT {num_rows}")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                table_entry["example_rows"] = nice_look_table(columns, rows)
            except Exception as e:
                table_entry["example_rows"] = f"(读取失败: {e})"

        schema_info["tables"].append(table_entry)

    conn.close()
    return schema_info

def print_schema_info(schema_info: Dict):
    print("\n📊 数据库结构信息：\n")

    for table in schema_info["tables"]:
        print(f"📌 表名: {table['table_name']}")
        print("🔧 CREATE TABLE 语句:")
        print(table["create_sql"])
        if "example_rows" in table:
            print("🧾 示例数据:")
            print(table["example_rows"])
        print("-" * 60)

# if __name__ == "__main__":
#     db_path = "dataset/birdsql_dev/dev_databases/formula_1/formula_1.sqlite"
#     table_name = "races"
#     column_name = "raceId"

#     # # 1️⃣ 获取主键列
#     # print("\n🔑 get_primary_keys")
#     # primary_keys = get_primary_keys(db_path=db_path, table_name=table_name)
#     # print(f"Primary keys in {table_name}:", primary_keys)

#     # # 2️⃣ 获取表结构中的列名和类型
#     print("\n📋 get_column_info")
#     # columns = get_column_info(db_path=db_path, table_name=table_name)
#     # print(f"Columns in {table_name}:", columns)
#     # coloimns=get_column_info_all_tables(db_path=db_path)
#     # print(coloimns)
#     # # 3️⃣ 获取表中的样本数据
#     # print("\n📊 get_table_sample")
#     # samples = get_table_sample(db_path=db_path, table_name=table_name, limit=3)
#     # print(f"Sample rows from {table_name}:")
#     # for row in samples:
#     #     print(row)

#     # # 4️⃣ 获取外键约束（适用于 JOIN）
#     # print("\n🔗 get_foreign_keys")
#     # foreign_keys = get_foreign_keys(db_path=db_path, table_name=table_name)
#     # print(f"Foreign keys in {table_name}:")
#     # for fk in foreign_keys:
#     #     print(fk)

#     # # 5️⃣ 搜索字段在哪些表中出现
#     # print("\n🔍 search_table_by_column_name")
#     # search_result = search_table_by_column_name(db_path=db_path, column_name=column_name)
#     # print(f"Column '{column_name}' appears in tables:", search_result.get("tables"))
#     # # ✅ 设置数据库路径
#     # db_path = "dataset/birdsql_dev/dev_databases/formula_1/formula_1.sqlite"

#     # # 1️⃣ list_tables
#     # print("🗂 1. List all tables in the database")
#     # tables_info = list_tables(db_path=db_path)
#     # print(tables_info)

#     # 2️⃣ get_table_schema - 单表结构与样例数据
#     # print("\n🔍 2. Get schema for a single table")
#     # if "tables" in tables_info and tables_info["tables"]:
#     #     table_name = tables_info["tables"][0]
#     #     table_schema = get_table_schema(db_path=db_path, table_name=table_name, num_rows=2)
#     #     print(f"📘 Table: {table_name}")
#     #     print(table_schema)
#     # else:
#     #     print("❌ No tables found.")

#     # 3️⃣ get_multiple_table_schemas - 多表结构与样例数据
#     # print("\n📊 3. Get schemas for multiple tables")
#     # if "tables" in tables_info and tables_info["tables"]:
#     #     selected_tables = tables_info["tables"][:2]  # 前两个表
#     #     multiple_schemas = get_multiple_table_schemas(db_path=db_path, table_names=selected_tables, num_rows=2)
#     #     print(f"📚 Tables: {selected_tables}")
#     #     print(multiple_schemas)
#     # else:
#     #     print("❌ No tables to extract.")

#     # 4️⃣ get_database_schema - 全库结构与样例数据
#     # print("\n📦 4. Get full database schema (with 1 sample row per table)")
#     # full_schema = get_database_schema(db_path=db_path, num_rows=1)
#     # print(full_schema)

#     # 5️⃣ format_schema_for_prompt - 结构格式化为 Prompt
#     print("\n📝 5. Format full schema into prompt-friendly string")
#     formatted = format_schema_for_prompt(db_path=db_path, num_rows=1)
#     print(formatted)



# import sqlite3
# import os


# def nice_look_table(column_names: list, values: list) -> str:
#     """美化输出表格数据"""
#     if not values:
#         return "（无数据）"
#     widths = [
#         max(len(str(value[i])) for value in values + [column_names])
#         for i in range(len(column_names))
#     ]
#     header = "".join(f"{col.rjust(w)} " for col, w in zip(column_names, widths))
#     rows = [
#         "".join(f"{str(val).rjust(w)} " for val, w in zip(row, widths))
#         for row in values
#     ]
#     return header + "\n" + "\n".join(rows)


# def extract_schema_from_sqlite(db_path: str, num_rows: int = 3) -> dict:
#     """提取 SQLite 数据库的表结构和部分数据"""
#     if not os.path.exists(db_path):
#         raise FileNotFoundError(f"数据库文件未找到: {db_path}")

#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()

#     cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
#     tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]

#     schema_info = {"db_path": db_path, "tables": []}

#     for table in tables:
#         cursor.execute(
#             f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';"
#         )
#         create_sql = cursor.fetchone()[0]

#         table_entry = {"table_name": table, "create_sql": create_sql}

#         if num_rows > 0:
#             try:
#                 cursor.execute(f"SELECT * FROM `{table}` LIMIT {num_rows}")
#                 rows = cursor.fetchall()
#                 columns = [desc[0] for desc in cursor.description]
#                 table_entry["example_rows"] = nice_look_table(columns, rows)
#             except Exception as e:
#                 table_entry["example_rows"] = f"(读取失败: {e})"

#         schema_info["tables"].append(table_entry)

#     conn.close()
#     return schema_info


# if __name__ == "__main__":
#     # db_path = r"C:\Users\86155\Desktop\pytorch_code\pyten\test2\src\library.db"
#     db_path="./src/library.db"
#     num_rows = 1

#     info = extract_schema_from_sqlite(db_path, num_rows)
#     print("\n📊 数据库结构信息：\n")

#     for table in info["tables"]:
#         print(f"📌 表名: {table['table_name']}")
#         print("🔧 CREATE TABLE 语句:")
#         print(table["create_sql"])
#         if "example_rows" in table:
#             print("🧾 示例数据:")
#             print(table["example_rows"])
#         print("-" * 60)
