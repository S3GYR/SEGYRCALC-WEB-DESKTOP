import sqlite3
import _sqlite3

print("SQLite Python OK")
print(sqlite3.sqlite_version)
print(sqlite3.__file__)
print(_sqlite3.__file__)

connection = sqlite3.connect(":memory:")
connection.execute("CREATE TABLE test (id INTEGER)")
connection.execute("INSERT INTO test VALUES (1)")
result = connection.execute("SELECT id FROM test").fetchone()
assert result == (1,)
connection.close()
print("SQLite runtime OK")
