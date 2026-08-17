import os
import re
import time
import jaydebeapi
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from dotenv import load_dotenv

load_dotenv()

def log_debug(message):
    print(f"[DEBUG] {message}", flush=True)

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
    log_debug("SELECT buscar_links_pendentes: iniciando consulta")
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
    rows = cur_chatwoot.fetchall()
    log_debug(f"SELECT buscar_links_pendentes: finalizada com {len(rows)} linhas")
    return rows

def atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha):
    log_debug(f"UPDATE conversations: iniciando para conversation_id={conversation_id}")
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
    result = cur_chatwoot.fetchone()
    log_debug(
        "UPDATE conversations: finalizado para conversation_id={0} | atualizado={1}".format(
            conversation_id,
            "sim" if result else "nao",
        )
    )
    return result

def marca_payload_processado(cur_chatwoot, source_id):
    log_debug(f"UPDATE whatsapp_raw_payloads: iniciando para source_id={source_id}")
    query = """
        UPDATE whatsapp_raw_payloads
        SET sync_message = TRUE
                WHERE source_id = ?
          AND sync_message = FALSE
    """
    cur_chatwoot.execute(query, [source_id])
    log_debug(
        f"UPDATE whatsapp_raw_payloads: finalizado para source_id={source_id} | rowcount={cur_chatwoot.rowcount}"
    )

def processa_lote(conn_chatwoot, cur_chatwoot):
    log_debug("processa_lote: inicio")
    rows = buscar_links_pendentes(cur_chatwoot)
    atualizadas = 0
    processadas = 0

    for row in rows:
        conversation_id = row[0]
        source_id = row[3]
        link_campanha = row[4]

        log_debug(
            f"processa_lote: item conversation_id={conversation_id} | source_id={source_id}"
        )

        if source_id is None:
            continue

        if link_campanha is not None and str(link_campanha).strip() != "" and conversation_id is not None:
            resultado = atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha)
            if resultado:
                atualizadas += 1
                log_debug(
                    f"processa_lote: commit apos atualizar link da conversation_id={conversation_id}"
                )
                conn_chatwoot.commit()

        marca_payload_processado(cur_chatwoot, source_id)
        processadas += 1

    log_debug(
        "processa_lote: fim | lidas={0} | processadas={1} | atualizadas={2}".format(
            len(rows), processadas, atualizadas
        )
    )
    return len(rows), processadas, atualizadas

def buscar_mensagens_atendimento(cur_chatwoot):
    log_debug("SELECT buscar_mensagens_atendimento: iniciando consulta")
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
    rows = cur_chatwoot.fetchall()
    log_debug(f"SELECT buscar_mensagens_atendimento: finalizada com {len(rows)} linhas")
    return rows

def buscar_link_por_hash(cur_chatwoot, hash_code):
    log_debug(f"SELECT whatsapp_links: iniciando para hash={hash_code}")
    query = """
        SELECT url, phone FROM whatsapp_links
        WHERE hash = ?
    """
    cur_chatwoot.execute(query, [hash_code])
    row = cur_chatwoot.fetchone()
    log_debug(
        "SELECT whatsapp_links: finalizada para hash={0} | encontrado={1}".format(
            hash_code,
            "sim" if row else "nao",
        )
    )
    return row

def adicionar_parametro_url(url, phone):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params['caiuas_number'] = [phone]
    nova_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=nova_query))

def atualiza_content_mensagem(cur_chatwoot, message_id):
    log_debug(f"UPDATE messages: iniciando para message_id={message_id}")
    query = """
        UPDATE messages
        SET content = REPLACE(content, 'Atendimento ', '')
        WHERE id = ?
    """
    cur_chatwoot.execute(query, [message_id])
    log_debug(f"UPDATE messages: finalizado para message_id={message_id} | rowcount={cur_chatwoot.rowcount}")
    return cur_chatwoot.rowcount > 0

def processa_lote_atendimento(conn_chatwoot, cur_chatwoot):
    log_debug("processa_lote_atendimento: inicio")
    rows = buscar_mensagens_atendimento(cur_chatwoot)
    atualizadas = 0

    for row in rows:
        conversation_id = row[0]
        content = row[3]
        message_id = row[4]

        log_debug(
            f"processa_lote_atendimento: item conversation_id={conversation_id} | message_id={message_id}"
        )

        match = re.search(r'Atendimento #([^:]+):', content)
        if not match:
            mensagem_atualizada = atualiza_content_mensagem(cur_chatwoot, message_id)
            if mensagem_atualizada:
                log_debug(
                    f"processa_lote_atendimento: commit apos atualizar message_id={message_id}"
                )
                conn_chatwoot.commit()
            continue

        hash_code = match.group(1).strip()

        resultado_link = buscar_link_por_hash(cur_chatwoot, hash_code)
        if resultado_link is None:
            mensagem_atualizada = atualiza_content_mensagem(cur_chatwoot, message_id)
            if mensagem_atualizada:
                log_debug(
                    f"processa_lote_atendimento: commit apos atualizar message_id={message_id}"
                )
                conn_chatwoot.commit()
            continue

        url, phone = resultado_link[0], resultado_link[1]
        if url and phone:
            link_campanha = adicionar_parametro_url(url, phone)
            if conversation_id is not None:
                resultado = atualiza_conversation_link(cur_chatwoot, conversation_id, link_campanha)
                if resultado:
                    atualizadas += 1
                    log_debug(
                        f"processa_lote_atendimento: commit apos atualizar link da conversation_id={conversation_id}"
                    )
                    conn_chatwoot.commit()

        mensagem_atualizada = atualiza_content_mensagem(cur_chatwoot, message_id)
        if mensagem_atualizada:
            log_debug(
                f"processa_lote_atendimento: commit apos atualizar message_id={message_id}"
            )
            conn_chatwoot.commit()

    log_debug(
        f"processa_lote_atendimento: fim | lidas={len(rows)} | atualizadas={atualizadas}"
    )
    return len(rows), atualizadas

def main():
    log_debug("main: iniciando conexao com chatwoot")
    conn_chatwoot, cur_chatwoot = chatwoot()
    try:
        while True:
            try:
                log_debug("main: iniciando ciclo")
                # total_lidas, total_processadas, total_atualizadas = processa_lote(conn_chatwoot, cur_chatwoot)
                total_atend_lidas, total_atend_atualizadas = processa_lote_atendimento(conn_chatwoot, cur_chatwoot)
                log_debug("main: realizando commit")
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
                    log_debug("main: sem atualizacoes, aguardando 1 segundo")
                    time.sleep(1)
            except Exception as error:
                conn_chatwoot.rollback()
                print(f"Erro ao processar lote: {error}")
    finally:
        log_debug("main: fechando cursor e conexao")
        cur_chatwoot.close()
        conn_chatwoot.close()

if __name__ == "__main__":
    main()