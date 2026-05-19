import logging
from datetime import datetime
from dotenv import load_dotenv
from app import app
from database import oracle, postgres_site

load_dotenv()

logger = logging.getLogger(__name__)


@app.task(name="tasks.myhonda_leads.process_myhonda_leads")
def process_myhonda_leads():
    try:
        conn_pg, cur_pg = postgres_site()
    except Exception as e:
        logger.error(f"Erro ao conectar no PostgreSQL: {e}")
        return

    try:
        cur_pg.execute("""
            SELECT evento_id, nome_completo, tipo, modelo_interesse, cpf, cnpj, origem,
                   celular, email, concessionaria, created_at
            FROM leads_myhonda
            WHERE status_integracao = 'dados_completados'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        rows = cur_pg.fetchall()
    except Exception as e:
        logger.error(f"Erro ao buscar leads: {e}")
        cur_pg.close()
        conn_pg.close()
        return

    for row in rows:
        row = list(row)

        # Sanitiza campos string
        row = [str(field).replace("'", "") if isinstance(field, str) else field for field in row]

        # Remove prefixo 55 do celular
        celular = str(row[7])
        if celular.startswith("55"):
            celular = celular[2:]
        row[7] = celular

        observacao = (
            f"Lead ID: {row[0]}\n"
            f"nome_completo: {str(row[1])[:100]}\n"
            f"tipo: {row[2]}\n"
            f"modelo_interesse: {row[3]}\n"
            f"cpf: {row[4]}\n"
            f"cnpj: {row[5]}\n"
            f"origem: {row[6]}\n"
            f"celular: {row[7]}\n"
            f"email: {row[8]}\n"
            f"concessionaria: {str(row[9]).strip()}"
        )

        cod_tipo_evento = 799
        modelo_interesse = str(row[3])
        if modelo_interesse == "HAB - Automóveis Novos":
            cod_tipo_evento = 795
        elif modelo_interesse == "CS - Serviços e Peças":
            cod_tipo_evento = 799
        elif modelo_interesse == "HAB - Automóveis":
            cod_tipo_evento = 795
        elif modelo_interesse == "BHB - Banco Honda":
            cod_tipo_evento = 793
        elif modelo_interesse == "CNH - Consórcio Honda":
            cod_tipo_evento = 797

        created_at_val = row[10]
        if hasattr(created_at_val, "strftime"):
            created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at_str = str(created_at_val)[:19]

        query_oracle = f"""
            INSERT INTO crm_eventos (
                COD_EMPRESA, COD_EVENTO, COD_TIPO_EVENTO, COD_PRIORIDADE,
                NOME_CLIENTE_AVULSO, FONE_CLIENTE_AVULSO, cod_midia, data_criacao,
                cod_cliente_honda, DESC_EVENTO, CRIOU_O_EVENTO, DATA_EVENTO,
                OBS_memo, COD_ANDAMENTO, COD_CLIENTE, STATUS,
                RESPONSAVEL_PELO_EVENTO, TIPO_ATENDIMENTO, COD_PRODUTO,
                COD_MODELO, EMAIL_CLIENTE_AVULSO
            ) VALUES (
                11,
                seq_crm_COD_EVENTO.nextval,
                {cod_tipo_evento},
                2,
                '{str(row[1])[:100]}',
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
                null,
                null,
                null,
                null,
                '{row[8]}'
            )
        """.replace("'None'", "null").replace("'null'", "null")

        oracle_ok = False
        conn_oracle = None
        cur_oracle = None
        try:
            conn_oracle, cur_oracle = oracle()
            cur_oracle.execute(query_oracle)
            conn_oracle.commit()
            oracle_ok = True
            logger.info(f"Lead ID {row[0]} inserido com sucesso no Oracle.")
        except Exception as e:
            logger.error(f"Erro ao inserir Lead ID {row[0]} no Oracle: {e}")
        finally:
            if cur_oracle:
                cur_oracle.close()
            if conn_oracle:
                conn_oracle.close()

        if oracle_ok:
            try:
                cur_pg.execute(
                    "UPDATE leads_myhonda SET status_integracao = 'integrado_nbs' WHERE evento_id = %s",
                    (row[0],),
                )
                conn_pg.commit()
                logger.info(f"Lead ID {row[0]} marcado como integrado_nbs no Postgres.")
            except Exception as e:
                logger.error(f"Erro ao atualizar status do Lead ID {row[0]} no Postgres: {e}")
                conn_pg.rollback()

    cur_pg.close()
    conn_pg.close()
