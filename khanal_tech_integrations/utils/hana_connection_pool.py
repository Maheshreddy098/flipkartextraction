from queue import Queue
from hdbcli import dbapi

class PoolableConnection:
    def __init__(self, connection, pool):
        self._conn = connection
        self._pool = pool

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def close(self):
        # Instead of closing the connection, return it to the pool
        self._pool.release_connection(self._conn)

    # Forward other methods to the original connection
    def __getattr__(self, attr):
        return getattr(self._conn, attr)

# Pool class with custom connection handling
# Replace with your connection details
host = "103.69.202.108"
port = 30015  # default HANA port, yours may differ
user = "KHANALFOODS"
password = "7c1l1L3k7k#O"
max_size = 5

class HANAConnectionPool:
    def __init__(self):
        self.pool = Queue(maxsize=max_size)
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        for _ in range(max_size):
            conn = self._create_connection()
            self.pool.put(PoolableConnection(conn, self))

    def _create_connection(self):
        return dbapi.connect(
            address=self.host,
            port=self.port,
            user=self.user,
            password=self.password
        )

    def get_connection(self):
        return self.pool.get()

    def release_connection(self, conn):
        try:
            if conn.isconnected():
                self.pool.put(conn)
            else:
                # Replace with new if disconnected
                new_conn = self._create_connection()
                self.pool.put(PoolableConnection(new_conn, self))
        except Exception:
            new_conn = self._create_connection()
            self.pool.put(PoolableConnection(new_conn, self))

    def close_all(self):
        while not self.pool.empty():
            conn = self.pool.get_nowait()
            conn.close()
