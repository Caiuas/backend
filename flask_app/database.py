import os
import jaydebeapi
from dotenv import load_dotenv

load_dotenv()

def oracle():
    driver_class = "oracle.jdbc.OracleDriver"
    jdbc_url = (
        f"jdbc:oracle:thin:@{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}:{os.getenv('ORACLE_DATABASE')}"
        f"?oracle.net.CONNECT_TIMEOUT=10000"  # 10 segundos de timeout
        f"&oracle.net.READ_TIMEOUT=60000"     # 60 segundos de tempo de resposta
    )
    driver_args = [
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('ORACLE_USERNAME'), os.getenv('ORACLE_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur

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