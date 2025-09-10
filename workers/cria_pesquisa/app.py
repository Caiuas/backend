import jaydebeapi
import json
import requests
from dotenv import load_dotenv
import os
from time import sleep
from datetime import datetime, timedelta
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

def chatwoot():
    driver_class = "org.postgresql.Driver"
    jdbc_url = f"jdbc:postgresql://{os.getenv('CHATWOOT_HOST')}:{os.getenv('CHATWOOT_PORT')}/{os.getenv('CHATWOOT_DATABASE')}"
    driver_args = [
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('CHATWOOT_USERNAME'), os.getenv('CHATWOOT_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur

while True:
    now = datetime.now()
    now_isoformat = now.isoformat()
    with open(f"processando.txt", "w") as f:
        f.write(f"{now_isoformat}")
    try:
        query = f"""
            SELECT 
                v.COD_EMPRESA, 
                v.CHASSI_COMPLETO, 
                v.COD_MODELO, 
                pm.DESCRICAO_MODELO, 
                a.COD_PROPOSTA, 
                a.DATA_BAIXA, 
                v.COD_CLIENTE 
            FROM EV_AGENDADOS a
            LEFT JOIN veiculos v ON 1=1
                AND v.COD_EMPRESA = a.COD_EMPRESA 
                AND v.CHASSI_RESUMIDO = a.CHASSI_RESUMIDO 
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_MODELO = v.COD_MODELO 
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN crm_eventos ce ON 1=1
                AND ce.COD_EMPRESA = v.COD_EMPRESA 
                AND ce.COD_PROPOSTA = v.COD_PROPOSTA 
                AND ce.COD_TIPO_EVENTO = 30
            WHERE 1=1
            --	AND v.CHASSI_COMPLETO = '93HGN5830TK400260'
                AND trunc(a.DATA_BAIXA) >= TO_DATE('2025-09-01', 'YYYY-MM-DD')
            --	AND a.COD_PROPOSTA = '1110085137'
                AND a.DATA_BAIXA IS NOT NULL
                and v.status in ('E', 'V')
                AND ce.cod_evento IS NULL
                
            """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        results = cur_oracle.fetchall()
        # cur_oracle.close()
        # conn_oracle.close()
        for row in results:
            data_baixa = row[5]
            data_baixa = datetime.strptime(data_baixa, "%Y-%m-%d %H:%M:%S")
            data_evento = data_baixa + timedelta(days=1)
            query = f"""
                INSERT INTO CRM_EVENTOS (
                    COD_EMPRESA,
                    COD_ANDAMENTO,
                    COD_EVENTO,
                    VEIC_COD_PRODUTO,
                    COD_QUESTIONARIO,
                    COD_PRIORIDADE,
                    COD_TIPO_EVENTO,
                    NUMERO_OS,
                    COD_PROPOSTA,
                    VEIC_COD_MODELO,
                    VEIC_CHASSI_COMPLETO,
                    DESC_EVENTO,
                    CRIOU_O_EVENTO,
                    DATA_EVENTO,
                    COD_CLIENTE,
                    STATUS,
                    RESPONSAVEL_PELO_EVENTO,
                    PLACA,
                    OBS_MEMO,
                    COD_PROGRAMACAO,
                    RESPONSAVEL_ORIGINAL,
                    DATA_CRIACAO,
                    DATA_ULTIMA_ATUALIZACAO,
                    CONSIDERA_VENDIDO,
                    USA_VIA_NUVEM
                ) VALUES (
                    {row[0]}, -- COD_EMPRESA
                    2, -- COD_ANDAMENTO
                    SEQ_CRM_COD_EVENTO.NEXTVAL, -- COD_EVENTO
                    {row[2]}, -- VEIC_COD_PRODUTO
                    143, -- COD_QUESTIONARIO
                    1, -- COD_PRIORIDADE
                    30, -- COD_TIPO_EVENTO
                    null, -- NUMERO_OS
                    '{row[4]}', -- COD_PROPOSTA
                    {row[2]}, -- VEIC_COD_MODELO
                    '{row[1]}', -- VEIC_CHASSI_COMPLETO
                    'Pesquisa de satisfação - Modelo {row[3]} - Proposta {row[4]}', -- DESC_EVENTO
                    'NBS', -- CRIOU_O_EVENTO
                    TO_TIMESTAMP('{data_evento.strftime("%Y-%m-%d %H:%M:%S")}', 'YYYY-MM-DD HH24:MI:SS'), -- DATA_EVENTO
                    {row[6]}, -- COD_CLIENTE
                    'P', -- STATUS
                    'NBS', -- RESPONSAVEL_PELO_EVENTO
                    null, -- PLACA
                    'Evento gerado pela integração - INTRANET', -- OBS_MEMO
                    null, -- COD_PROGRAMACAO
                    'NBS', -- RESPONSAVEL_ORIGINAL
                    SYSTIMESTAMP, -- DATA_CRIACAO
                    SYSTIMESTAMP, -- DATA_ULTIMA_ATUALIZACAO
                    'N', -- CONSIDERA_VENDIDO
                    'N' -- USA_VIA_NUVEM
                )
            """
            cur_oracle.execute(query)
            conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        #  espere 10 minutos
        sleep(600)
    except Exception as e:
        with open(f"log/{now_isoformat}.log", "a") as log_file:
            log_file.write(f"[{now_isoformat}] Error: {e}\n")
        try:
            cur_oracle.close()
            conn_oracle.close()
        except Exception as e:
            pass
