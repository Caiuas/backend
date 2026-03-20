import os
import re
import time
import jaydebeapi
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from dotenv import load_dotenv

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
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('CHATWOOT_USERNAME'), os.getenv('CHATWOOT_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur

def buscar_links_pendentes(cur_chatwoot):
    query = """
        SELECT DISTINCT
            m.conversation_id,
            m.account_id,
            m.inbox_id,
            m.source_id,
            entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' AS link_campanha
        FROM messages m
        LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
        CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
        WHERE wrp.payload IS NOT NULL
          AND wrp.sync_message = FALSE
    """
    cur_chatwoot.execute(query)
    return cur_chatwoot.fetchall()


def atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha):
    query = """
        UPDATE conversations
        SET
            additional_attributes = CASE
                WHEN NOT jsonb_exists(COALESCE(additional_attributes, '{}'::jsonb), 'link_campanha')
                THEN COALESCE(additional_attributes, '{}'::jsonb) || jsonb_build_object('link_campanha', ?)
                ELSE additional_attributes
            END,
            custom_attributes = CASE
                WHEN NOT jsonb_exists(COALESCE(custom_attributes, '{}'::jsonb), 'link_campanha')
                THEN COALESCE(custom_attributes, '{}'::jsonb) || jsonb_build_object('link_campanha', ?)
                ELSE custom_attributes
            END
        WHERE id = ?
          AND (
            NOT jsonb_exists(COALESCE(additional_attributes, '{}'::jsonb), 'link_campanha')
            OR NOT jsonb_exists(COALESCE(custom_attributes, '{}'::jsonb), 'link_campanha')
          )
        RETURNING id
    """
    cur_chatwoot.execute(query, [link_campanha, link_campanha, conversation_id])
    return cur_chatwoot.fetchone()


def marca_payload_processado(cur_chatwoot, source_id):
    query = """
        UPDATE whatsapp_raw_payloads
        SET sync_message = TRUE
                WHERE source_id = ?
          AND sync_message = FALSE
    """
    cur_chatwoot.execute(query, [source_id])


def processa_lote(cur_chatwoot):
    rows = buscar_links_pendentes(cur_chatwoot)
    atualizadas = 0
    processadas = 0

    for row in rows:
        conversation_id = row[0]
        source_id = row[3]
        link_campanha = row[4]

        if source_id is None:
            continue

        if link_campanha is not None and str(link_campanha).strip() != "" and conversation_id is not None:
            resultado = atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha)
            if resultado:
                atualizadas += 1

        marca_payload_processado(cur_chatwoot, source_id)
        processadas += 1

    return len(rows), processadas, atualizadas


def buscar_mensagens_atendimento(cur_chatwoot):
    query = """
        SELECT DISTINCT
            m.conversation_id,
            m.account_id,
            m.inbox_id,
            m.content,
            m.id
        FROM messages m
        WHERE m.content LIKE 'Atendimento #%'
          AND m.created_at >= NOW() - INTERVAL '30 days'
    """
    cur_chatwoot.execute(query)
    return cur_chatwoot.fetchall()


def buscar_link_por_hash(cur_chatwoot, hash_code):
    query = """
        SELECT url, phone FROM whatsapp_links
        WHERE hash = ?
    """
    cur_chatwoot.execute(query, [hash_code])
    return cur_chatwoot.fetchone()


def adicionar_parametro_url(url, phone):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params['caiuas_number'] = [phone]
    nova_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=nova_query))


def atualiza_content_mensagem(cur_chatwoot, message_id):
    query = """
        UPDATE messages
        SET content = REPLACE(content, 'Atendimento ', '')
        WHERE id = ?
    """
    cur_chatwoot.execute(query, [message_id])


def processa_lote_atendimento(cur_chatwoot):
    rows = buscar_mensagens_atendimento(cur_chatwoot)
    atualizadas = 0

    for row in rows:
        conversation_id = row[0]
        content = row[3]
        message_id = row[4]

        match = re.search(r'Atendimento #([^:]+):', content)
        if not match:
            atualiza_content_mensagem(cur_chatwoot, message_id)
            continue

        hash_code = match.group(1).strip()

        resultado_link = buscar_link_por_hash(cur_chatwoot, hash_code)
        if resultado_link is None:
            atualiza_content_mensagem(cur_chatwoot, message_id)
            continue

        url, phone = resultado_link[0], resultado_link[1]
        if url and phone:
            link_campanha = adicionar_parametro_url(url, phone)
            if conversation_id is not None:
                resultado = atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha)
                if resultado:
                    atualizadas += 1

        atualiza_content_mensagem(cur_chatwoot, message_id)

    return len(rows), atualizadas


def main():
    conn_chatwoot, cur_chatwoot = chatwoot()
    try:
        while True:
            try:
                total_lidas, total_processadas, total_atualizadas = processa_lote(cur_chatwoot)
                total_atend_lidas, total_atend_atualizadas = processa_lote_atendimento(cur_chatwoot)
                conn_chatwoot.commit()
                print(
                    "Lidas: {0} | Processadas: {1} | Conversations atualizadas: {2} | "
                    "Atendimentos lidos: {3} | Atendimentos atualizados: {4}".format(
                        total_lidas,
                        total_processadas,
                        total_atualizadas,
                        total_atend_lidas,
                        total_atend_atualizadas,
                    )
                )
                if total_atualizadas == 0 and total_atend_atualizadas == 0:
                    time.sleep(1)
            except Exception as error:
                conn_chatwoot.rollback()
                print(f"Erro ao processar lote: {error}")
    finally:
        cur_chatwoot.close()
        conn_chatwoot.close()


if __name__ == "__main__":
    main()