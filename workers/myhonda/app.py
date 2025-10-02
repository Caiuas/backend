import jaydebeapi
import json
import requests
from dotenv import load_dotenv
import os
from time import sleep
from datetime import datetime
load_dotenv()

def db_site():
    driver_class = "org.postgresql.Driver"
    jdbc_url = f"jdbc:postgresql://{os.getenv('POSTGRES_SITE_HOST')}:{os.getenv('POSTGRES_SITE_PORT')}/{os.getenv('POSTGRES_SITE_DB')}"
    driver_args = [
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('POSTGRES_SITE_USER'), os.getenv('POSTGRES_SITE_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur

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

def process_leads():
    try:
        conn, cur = db_site()
    except Exception as e:
        print(f"[{datetime.now()}] Erro ao conectar no PostgreSQL: {e}")
        return

    query = """
        select * from leads_myhonda
        where upper(status) = 'PENDENTE'
        order by id_evento
    """
    try:
        cur.execute(query)
        rows = cur.fetchall()
    except Exception as e:
        print(f"[{datetime.now()}] Erro ao buscar leads: {e}")
        cur.close()
        conn.close()
        return

    for row in rows:
        observacao = f"""
Lead ID: {row[1]}
nome_completo: {row[2]}
tipo: {row[3]}
modelo_interesse: {row[4]}
cpf: {row[5]}
cnpj: {row[6]}
origem: {row[7]}
celular: {row[8]}
email: {row[9]}
concessionaria: {str(row[10]).strip()}
        """
        cod_tipo_evento = 799
        if row[3] == 'HAB - Automóveis Novos':
            cod_tipo_evento = 795
        elif row[3] == 'CS - Serviços e Peças':
            cod_tipo_evento = 799
        elif row[3] == 'HAB - Automóveis':
            cod_tipo_evento = 795
        elif row[3] == 'BHB - Banco Honda':
            cod_tipo_evento = 793
        elif row[3] == 'CNH - Consórcio Honda':
            cod_tipo_evento = 797

        query_oracle = f"""
                insert into crm_eventos(COD_EMPRESA,
                                        COD_EVENTO,
                                        COD_TIPO_EVENTO,
                                        COD_PRIORIDADE,
                                        NOME_CLIENTE_AVULSO ,
                                        FONE_CLIENTE_AVULSO,
                                        cod_midia,
                                        data_criacao ,
                                        cod_cliente_honda ,
                                        DESC_EVENTO,
                                        CRIOU_O_EVENTO,
                                        DATA_EVENTO,
                                        OBS_memo,
                                        COD_ANDAMENTO,
                                        COD_CLIENTE,
                                        STATUS,
                                        RESPONSAVEL_PELO_EVENTO,
                                        TIPO_ATENDIMENTO,
                                        COD_PRODUTO,
                                        COD_MODELO,
                                        EMAIL_CLIENTE_AVULSO)
                                VALUES(11,
                                seq_crm_COD_EVENTO.nextval,
                                {cod_tipo_evento},
                                2,
                                '{row[2]}',
                                '{row[8]}',
                                18,
                                SYSDATE,
                                seq_cod_cliente_honda.nextval,
                                'Evento criado via integração MyHonda - Lead ID {row[1]}',
                                'NBS',
                                SYSDATE,
                                '{observacao}',
                                2,
                                1,
                                'P',
                                Null,
                                null,
                                 'null',
                                'null',
                                '{row[9]}')
            """
        query_oracle = query_oracle.replace("'None'", 'null')
        query_oracle = query_oracle.replace("'null'", 'null')

        try:
            conn_oracle, cur_oracle = oracle()
            cur_oracle.execute(query_oracle)
            conn_oracle.commit()
            cur_oracle.close()
            conn_oracle.close()
            print(f"[{datetime.now()}] Lead ID {row[1]} inserido com sucesso.")
            query_update = f"""
                update leads_myhonda set status = 'Integrado'
                where id_evento = {row[0]}
            """
            cur.execute(query_update)
            conn.commit()
        except Exception as e:
            print(f"[{datetime.now()}] Erro ao inserir Lead ID {row[1]}: {e}")
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass

    cur.close()
    conn.close()

if __name__ == "__main__":
    while True:
        try:
            process_leads()
        except Exception as e:
            print(f"[{datetime.now()}] Erro inesperado: {e}")
        sleep(60)