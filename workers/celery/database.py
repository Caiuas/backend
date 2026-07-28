import os
import logging
import jaydebeapi
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JDBC_JARS = [
    "/flask_app/jdbc/oracle-jdbc-11.jar",
    "/flask_app/jdbc/postgresql-42.7.5.jar",
]


def oracle():
    driver_class = "oracle.jdbc.OracleDriver"
    jdbc_url = (
        f"jdbc:oracle:thin:@{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}:{os.getenv('ORACLE_DATABASE')}"
        f"?oracle.net.CONNECT_TIMEOUT=10000"
        f"&oracle.net.READ_TIMEOUT=60000"
    )
    conn = jaydebeapi.connect(
        driver_class,
        jdbc_url,
        [os.getenv("ORACLE_USERNAME"), os.getenv("ORACLE_PASSWORD")],
        JDBC_JARS,
    )
    conn.jconn.setAutoCommit(False)
    return conn, conn.cursor()


def chatwoot():
    driver_class = "org.postgresql.Driver"
    jdbc_url = f"jdbc:postgresql://{os.getenv('CHATWOOT_HOST')}:{os.getenv('CHATWOOT_PORT')}/{os.getenv('CHATWOOT_DATABASE')}"
    driver_args = [
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('CHATWOOT_USERNAME'), os.getenv('CHATWOOT_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur


def postgres_site():
    db_config = {
        "dbname": os.environ.get("POSTGRES_SITE_DB"),
        "user": os.environ.get("POSTGRES_SITE_USER"),
        "password": os.environ.get("POSTGRES_SITE_PASSWORD"),
        "host": os.environ.get("POSTGRES_SITE_HOST"),
        "port": os.environ.get("POSTGRES_SITE_PORT"),
    }
    conn = psycopg2.connect(**db_config, cursor_factory=psycopg2.extras.DictCursor)
    return conn, conn.cursor()
