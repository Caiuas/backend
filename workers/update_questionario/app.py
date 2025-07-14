import jaydebeapi
import json
import requests
from dotenv import load_dotenv
import os
from time import sleep
from datetime import datetime
load_dotenv()

def oracle():
    driver_class = "oracle.jdbc.OracleDriver"
    jdbc_url = f"jdbc:oracle:thin:@{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}:{os.getenv('ORACLE_DATABASE')}"
    driver_args = [
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('ORACLE_USERNAME'), os.getenv('ORACLE_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur

query = f"""
        SELECT cr.COD_EMPRESA, cr.cod_evento, cr.COD_QUESTIONARIO 
        FROM CRM_RESPOSTAS cr 
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_EMPRESA = cr.COD_EMPRESA 
            AND ce.COD_EVENTO = cr.COD_EVENTO 
        WHERE 1=1
            AND ce.COD_QUESTIONARIO <> cr.COD_QUESTIONARIO
        GROUP BY cr.COD_EMPRESA, cr.cod_evento, cr.COD_QUESTIONARIO
"""

while True:
    conn, cur = oracle()
    cur.execute(query)
    results = cur.fetchall()
    if len(results) > 0:
        for row in results:
            cod_empresa, cod_evento, cod_questionario = row
            query = f"""
                update crm_eventos set cod_questionario = {cod_questionario}
                where cod_empresa = {cod_empresa} and cod_evento = {cod_evento}
            """
            cur.execute(query)
            conn.commit()
            print(f"Atualizado evento {cod_evento} da empresa {cod_empresa} para o questionário {cod_questionario}")
    else:
        print("Nenhum evento encontrado para atualizar.")
    cur.close()
    conn.close()
    print(f"Verificando novamente em 30 segundos... {datetime.now()}")
    sleep(30)
    