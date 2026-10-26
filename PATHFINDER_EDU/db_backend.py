"""Small DB compatibility layer for SQLite on desktop and PostgreSQL on Render.

Online deployments MUST provide DATABASE_URL. No fallback to ephemeral SQLite.
Only server-issued SQL is accepted here; never interpolate student values into SQL.
"""
import os,re,sqlite3

IS_POSTGRES = bool(os.environ.get('DATABASE_URL'))

class PGRow(dict):
    """Supports both sqlite.Row integer access and mapping access."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class PGResult:
    def __init__(self, cursor):
        self.cursor = cursor
    def fetchone(self):
        row = self.cursor.fetchone()
        return PGRow(row) if row is not None else None
    def fetchall(self):
        return [PGRow(row) for row in self.cursor.fetchall()]
    def __iter__(self):
        for row in self.cursor:
            yield PGRow(row)


def normalize_sql(sql):
    """Parameter placeholders, auto ids, and SQLite ignore semantics."""
    sql = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'BIGSERIAL PRIMARY KEY', sql, flags=re.I)
    sql = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b', 'BIGSERIAL PRIMARY KEY', sql, flags=re.I)
    ignored = bool(re.search(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b',sql,re.I))
    sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b','INSERT INTO',sql,flags=re.I)
    if ignored:
        sql = sql.rstrip().rstrip(';')+' ON CONFLICT DO NOTHING'
    return sql.replace('?', '%s')

class PostgresConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self._conn = psycopg.connect(url, sslmode='require', connect_timeout=12, row_factory=dict_row, prepare_threshold=None)
    def execute(self, statement, args=()):
        cursor=self._conn.execute(normalize_sql(statement), tuple(args))
        return PGResult(cursor)
    def executemany(self, statement, records):
        with self._conn.cursor() as cursor:
            cursor.executemany(normalize_sql(statement), records)
        return self
    def executescript(self, statements):
        for statement in statements.split(';'):
            if statement.strip():self.execute(statement)
    def commit(self):self._conn.commit()
    def rollback(self):self._conn.rollback()
    def __enter__(self):return self
    def __exit__(self, exc_type, exc, tb):
        try:
            self.rollback() if exc_type else self.commit()
        finally:self._conn.close()

def connect(path):
    url=os.environ.get('DATABASE_URL','')
    if url:
        if not (url.startswith('postgresql://') or url.startswith('postgres://')):
            raise RuntimeError('DATABASE_URL은 PostgreSQL 연결 문자열이어야 합니다.')
        return PostgresConnection(url)
    if os.environ.get('PF_PUBLIC_MODE')=='1':
        raise RuntimeError('Render 무료 서버는 SQLite 저장을 보장할 수 없습니다. DATABASE_URL(외부 PostgreSQL)을 설정하세요.')
    conn=sqlite3.connect(path,timeout=15,check_same_thread=False)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn
