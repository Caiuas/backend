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
        select evento_id, nome_completo, tipo, modelo_interesse, cpf, cnpj, origem, celular, email, concessionaria, created_at from leads_myhonda
        where status_integracao = 'dados_completados'
        order by created_at desc
        limit 1
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
        # replace "'"" with "" in all string fields
        row = [str(field).replace("'", "") if isinstance(field, str) else field for field in row]
        observacao = f"""
            Lead ID: {row[0]}
            nome_completo: {row[1][:100]}
            tipo: {row[2]}
            modelo_interesse: {row[3]}
            cpf: {row[4]}
            cnpj: {row[5]}
            origem: {row[6]}
            celular: {row[7]}
            email: {row[8]}
            concessionaria: {str(row[9]).strip()}
        """
        cod_tipo_evento = 799

        created_at_val = row[10]
        if hasattr(created_at_val, 'strftime'):
            created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M:%S')
        else:
            created_at_str = str(created_at_val)[:19]

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
                                '{row[1][:100]}',
                                '{row[7]}',  
                                18,
                                TO_DATE('{created_at_str}', 'YYYY-MM-DD HH24:MI:SS'),
                                seq_cod_cliente_honda.nextval,
                                'Evento criado via integração MyHonda - Lead ID {row[0]}',
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
        # print(query_oracle)
        oracle_ok = False
        try:
            conn_oracle, cur_oracle = oracle()
            cur_oracle.execute(query_oracle)
            conn_oracle.commit()
            cur_oracle.close()
            conn_oracle.close()
            oracle_ok = True
            print(f"[{datetime.now()}] Lead ID {row[1]} inserido com sucesso no Oracle.")
        except Exception as e:
            print(f"[{datetime.now()}] Erro ao inserir Lead ID {row[1]} no Oracle: {e}")
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass

        if oracle_ok:
            try:
                query_update = f"""
                    UPDATE leads_myhonda SET status_integracao = 'integrado_nbs'
                    WHERE evento_id = '{row[0]}'
                """
                print(query_update)
                cur.execute(query_update)
                conn.commit()
                print(f"[{datetime.now()}] Lead ID {row[1]} marcado como integrado_nbs no Postgres.")
            except Exception as e:
                print(f"[{datetime.now()}] Erro ao atualizar status do Lead ID {row[1]} no Postgres: {e}")
                conn.rollback()

    cur.close()
    conn.close()

if __name__ == "__main__":
    while True:
        try:
            process_leads()
        except Exception as e:
            print(f"[{datetime.now()}] Erro inesperado: {e}")
            sleep(60)