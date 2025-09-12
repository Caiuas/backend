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
            SELECT
            oa.COD_EMPRESA,
            oa.COD_OS_AGENDA,
            ce.COD_EVENTO ,
            o.NUMERO_OS,
            o.status_os
        FROM
            crm_eventos ce
        LEFT JOIN CRM_EVENTOS_TIPO cet ON
            1 = 1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_GRUPO cg ON
            1 = 1
            AND cg.COD_GRUPO = cet.COD_GRUPO
        LEFT JOIN OS_AGENDA oa ON
            1 = 1
            AND oa.cod_empresa = ce.COD_EMPRESA
            AND oa.CRM_COD_EVENTO = ce.COD_EVENTO
        LEFT JOIN os o ON
            1 = 1
            AND o.NUMERO_OS = oa.NUMERO_OS
            AND o.COD_EMPRESA = oa.COD_EMPRESA
        WHERE
            1 = 1
            AND ce.COD_EMPRESA IN (11, 33)
            AND ce.status <> 'E'
            AND ce.status <> 'D'
            AND o.NUMERO_OS IS NOT NULL
            AND o.status_os = 1
"""
print("Iniciando processo de atualização de fechamento no CRM...")
cont = 0
while True:
    if cont == 1:
        exit()
    cont = cont + 1
    print("Connectando ao banco de dados...")
    conn, cur = oracle()
    print("Consultando eventos abertos vinculados a OS...")
    cur.execute(query)
    print("Processando eventos...")
    results = cur.fetchall()
    print(f"Foram encontrados {len(results)} eventos para serem encerrados.")
    if len(results) == 0:
        cur.close()
        conn.close()
        sleep(60)
        continue
    for row in results:
        cod_empresa, cod_os_agenda, cod_evento, numero_os, status_os = row
        
        query = f"""
            insert into crm_acoes   
            (cod_empresa,cod_evento,cod_acao,tipo_acao,observacao,responsavel,data,status, cod_andamento) 
            values
            ({cod_empresa},{cod_evento},seq_crm_cod_acao.nextval,9,'Encerrado Automaticamente pela intranet','NBS',sysdate,'E', NULL) 
        """
        cur.execute(query)
        query = f"""
            UPDATE
                crm_eventos
            SET
                cod_tipo_fechamento = 1,
                data_encerramento = sysdate,
                status = 'E',
                quem_encerrou = 'NBS',
                RAC_SATISFATORIO = NULL
            WHERE
                cod_empresa = {cod_empresa}
                AND cod_evento = {cod_evento}
        """
        cur.execute(query)
        conn.commit()
        print(f"Encerrado evento {cod_evento} da empresa {cod_empresa} da OS {numero_os}")
    cur.close()
    conn.close()
    print(f"Verificando novamente em 60 segundos... {datetime.now()}")
    sleep(60)