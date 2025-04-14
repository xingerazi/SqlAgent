import os
import sqlite3
import traceback

class Executor:
    def __init__(self, db_path: str = "example.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在：{self.db_path}")

    def execute_sql(self, sql: str) -> dict:
        """
        自动判断 SQL 类型，执行并返回合适的输出信息。
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(sql.strip())
            conn.commit()

            result = cursor.fetchall()

            conn.close()

            return {
                "status": "success",
                "result": result
            }

        except Exception as e:
            return {
                "status": "error",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "trace": traceback.format_exc()
                }
            }

    def execute(self, code: str) -> dict:
        """
        在本地执行 Text-to-SQL 模型生成的 Python + sqlite3 代码。
        """
        local_vars = {
            "sqlite3": sqlite3,
            "db_path": self.db_path,
        }

        try:
            exec(code, {}, local_vars)
            output = local_vars.get("__output__", "<no output captured>")
            return {
                "status": "success",
                "result": output
            }
        except Exception as e:
            return {
                "status": "error",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "trace": traceback.format_exc()
                }
            }

# import sqlite3
# import traceback


# class Executor:
#     def __init__(self, db_path: str = "example.db"):
#         self.db_path = db_path

#     def execute_sql(self, sql: str) -> dict:
#         """
#         自动判断 SQL 类型，执行并返回合适的输出信息。
#         """
#     try:
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()

#         cursor.execute(sql.strip())
#         conn.commit()

#         if sql.strip().lower().startswith("select"):
#             output = cursor.fetchall()
#         else:
#             output = f"✅ SQL executed: {sql.strip().split()[0].upper()} (no result to fetch)"

#         conn.close()

#         return {
#             "status": "success",
#             "result": output
#         }

#     except Exception as e:
#         return {
#             "status": "error",
#             "error": {
#                 "type": type(e).__name__,
#                 "message": str(e),
#                 "trace": traceback.format_exc()
#             }
#         }

#     def execute(self, code: str) -> dict:
#         local_vars = {
#             "db_path": self.db_path,
#         }
#         global_vars = {
#             "sqlite3": sqlite3,
#             "db_path": self.db_path,
#         }

#         try:
#             exec(code, global_vars, local_vars)
#             output = local_vars.get("__output__", "<no output captured>")
#             return {
#                 "status": "success",
#                 "result": output
#             }
#         except Exception as e:
#             return {
#                 "status": "error",
#                 "error": {
#                     "type": type(e).__name__,
#                     "message": str(e),
#                     "trace": traceback.format_exc()
#                 }
#             }
