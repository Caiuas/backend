import json
import logging
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

from app import app
from database import chatwoot, oracle

load_dotenv()

logger = logging.getLogger(__name__)


def _extrair_telefones(registro):
    telefones = []

    residencial = ''.join(filter(str.isdigit, str(registro[2])))
    comercial = ''.join(filter(str.isdigit, str(registro[3])))
    fax = ''.join(filter(str.isdigit, str(registro[4])))
    celular = ''.join(filter(str.isdigit, str(registro[5])))
    whatsapp = ''.join(filter(str.isdigit, str(registro[8])))

    if residencial and len(residencial) == 11 and residencial[2] == "9":
        telefones.append(residencial)
    if comercial and len(comercial) == 11 and comercial[2] == "9":
        telefones.append(comercial)
    if fax and len(fax) == 11 and fax[2] == "9":
        telefones.append(fax)
    if celular and len(celular) == 11 and celular[2] == "9":
        telefones.append(celular)
    if whatsapp and len(whatsapp) == 11 and whatsapp[2] == "9":
        telefones.append(whatsapp)

    telefones = list(set(telefones))
    return [f"55{telefone}" for telefone in telefones if telefone]


def _upsert_contato_chatwoot(cur_chatwoot, conn_chatwoot, nome, telefone):
    query = f"""
        WITH update_result AS (
            UPDATE contacts
            SET
                "name" = '{nome}',
                updated_at = now(),
                last_activity_at = now()
            WHERE phone_number = '+{telefone}'
            RETURNING id
        ),
        insert_result AS (
            INSERT INTO contacts
            ("name", email, phone_number, account_id, created_at, updated_at, additional_attributes, identifier, custom_attributes, last_activity_at, contact_type, middle_name, last_name, "location", country_code, "blocked")
            SELECT
                '{nome}', NULL, '+{telefone}', 1, now(), now(), '{{}}'::jsonb, NULL, '{{}}'::jsonb, now(), 1, '', '', NULL, NULL, false
            WHERE NOT EXISTS (SELECT 1 FROM update_result)
            RETURNING id
        )
        SELECT id FROM update_result
        UNION ALL
        SELECT id FROM insert_result;
    """
    cur_chatwoot.execute(query)
    conn_chatwoot.commit()
    return cur_chatwoot.fetchone()[0]


def _marcar_status(cur_oracle, conn_oracle, id_log, status):
    query = f"""
        UPDATE CAIUAS_LOG_WHATSAPP clw
        SET clw.STATUS = '{status}'
        WHERE clw.id_log = {id_log}
    """
    cur_oracle.execute(query)
    conn_oracle.commit()


def _consulta_os(cod_empresa, cod_os_agenda):
    return f"""
        SELECT
            ce.COD_EVENTO,
            c.NOME,
            concat (c.PREFIXO_RES, c.TELEFONE_RES) residencial,
            concat (c.PREFIXO_COM, c.TELEFONE_COM) comercial,
            concat (c.PREFIXO_FAX, c.TELEFONE_FAX) fax,
            concat (c.PREFIXO_CEL, c.TELEFONE_CEL) celular,
            concat (c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST) whatsapp,
            pm.DESCRICAO_MODELO,
            oa.PLACA,
            TO_CHAR(oa.DATA_AGENDADA, 'YYYY-MM-DD HH24:MI:SS')
        FROM OS_AGENDA oa
        LEFT JOIN clientes c ON 1=1
            AND c.COD_CLIENTE = oa.COD_CLIENTE
        LEFT JOIN PRODUTOS p ON 1=1
            AND p.COD_PRODUTO = oa.COD_PRODUTO
        LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
            AND pm.COD_PRODUTO = p.COD_PRODUTO
            AND pm.COD_MODELO = oa.COD_MODELO
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_EMPRESA = oa.COD_EMPRESA
            AND ce.COD_EVENTO = oa.CRM_COD_EVENTO
        WHERE 1=1
            AND oa.cod_empresa = {cod_empresa}
            AND oa.COD_OS_AGENDA = {cod_os_agenda}
        ORDER BY oa.DATA_AGENDADA DESC
    """


def _payload_empresa_11(contact_id, telefone, modelo, placa, dia, hora):
    return json.dumps(
        {
            "inbox_id": 1,
            "contact_id": contact_id,
            "source_id": f"{telefone}",
            "message": {
                "content": (
                    "Confirmamos o agendamento de seu veículo:\n\n"
                    f"Modelo: {modelo}\n"
                    f"Placa: {placa}\n"
                    f"Dia: {dia}\n"
                    f"Horário: {hora}\n"
                    "Unidade: Sorocaba\n\n"
                    "*Para melhor atende-lo solicitamos que chegue no horário agendado*\n\n"
                    "•Trazer o manual de garantia;\n"
                    "•Pedimos a gentileza de retirar todos os pertences pessoais do veículo;\n\n"
                    "Endereço: Av. Dom Aguirre, 2865 - Jardim Santa Rosália - Sorocaba/SP\n\n"
                    "A Honda Caiuás agradece a preferência, tenha um excelente dia!\n\n"
                    "*Sistema Carona Aos Clientes Pós-venda**\n"
                    "* O Sistema Carona Caiuás funciona diariamente de 2° à 6°feira no período entre 08:30 e 11:00h*\n"
                    "* O primeiro carro sai diariamente às 08:30h. Os subsequentes dependem do horário de retorno do veículo à concessionária, não sendo possível prever exatamente o horário das próximas saída*.\n"
                    "* A rota é estabelecida visando otimizar cada saída.\n"
                    "* O Sistema Carona Caiuás abrange exclusivamente a cidade de Sorocaba."
                ),
                "template_params": {
                    "name": "confirma_agenda_sorocaba",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "processed_params": {
                        "modelo": f"{modelo}",
                        "placa": f"{placa}",
                        "dia": f"{dia}",
                        "hora": f"{hora}",
                    },
                },
            },
            "assignee_id": 117,
        }
    )


def _payload_empresa_33(contact_id, telefone, modelo, placa, dia, hora):
    return json.dumps(
        {
            "inbox_id": 1,
            "contact_id": contact_id,
            "source_id": f"{telefone}",
            "message": {
                "content": (
                    "Confirmamos o agendamento de seu veículo:\n\n"
                    f"Modelo: {modelo}\n"
                    f"Placa: {placa}\n"
                    f"Dia: {dia}\n"
                    f"Horário: {hora}\n\n"
                    "*Unidade: Indaiatuba*\n\n"
                    "Para melhor atende-lo solicitamos que chegue no horário agendado\n\n"
                    "•Trazer o manual de garantia;\n"
                    "•Pedimos a gentileza de retirar todos os pertences pessoais do veículo;\n\n"
                    "Endereço: *Av. Pres. Vargas, 1168 - Centro, Indaiatuba.*\n\n"
                    "*Obs.:*\n"
                    "Informamos que na unidade de Indaiatuba não temos serviço de carona, é importante que o senhor(a) se programe quanto ao transporte para voltar para casa/trabalho após deixar o veículo para serviço em nossa oficina e para a retirada do veículo.\n\n"
                    "A Honda Caiuás agradece a preferência, tenha um excelente dia!"
                ),
                "template_params": {
                    "name": "confirma_agenda_indaiatuba_2",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "processed_params": {
                        "modelo": f"{modelo}",
                        "placa": f"{placa}",
                        "dia": f"{dia}",
                        "hora": f"{hora}",
                    },
                },
            },
            "assignee_id": 117,
        }
    )


@app.task(name="tasks.send_wpp_agendamento.process_send_wpp_agendamento")
def process_send_wpp_agendamento():
    conn_oracle = None
    cur_oracle = None
    conn_chatwoot = None
    cur_chatwoot = None

    try:
        query = """
            SELECT id_log, cod_empresa, cod_os_agenda, name
            FROM CAIUAS_LOG_WHATSAPP clw
            WHERE clw.STATUS = 'pendente'
            ORDER BY id_log DESC
        """

        conn_oracle, cur_oracle = oracle()
        conn_chatwoot, cur_chatwoot = chatwoot()

        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()

        if len(rows) == 0:
            logger.info("send_wpp_agendamento: nenhum registro pendente")
            return {"processed": 0}

        enviados = 0
        erros = 0

        for row in rows:
            id_log = row[0]
            cod_empresa = int(row[1])
            cod_os_agenda = row[2]

            if cod_empresa not in [11, 33]:
                continue

            query_os = _consulta_os(cod_empresa, cod_os_agenda)
            cur_oracle.execute(query_os)
            result = cur_oracle.fetchall()

            if len(result) == 0:
                _marcar_status(cur_oracle, conn_oracle, id_log, "Erro - Registro não encontrado")
                erros += 1
                continue

            for registro in result:
                telefones = _extrair_telefones(registro)

                if len(telefones) == 0:
                    _marcar_status(cur_oracle, conn_oracle, id_log, "Erro - Telefone não encontrado")
                    erros += 1
                    continue

                for telefone in telefones:
                    data_agendada = datetime.strptime(registro[9], "%Y-%m-%d %H:%M:%S")
                    dia = data_agendada.strftime("%d/%m")
                    hora = data_agendada.strftime("%H:%M")
                    modelo = str(registro[7]).upper()
                    placa = str(registro[8]).upper()
                    nome = str(registro[1]).upper()

                    contact_id = _upsert_contato_chatwoot(
                        cur_chatwoot,
                        conn_chatwoot,
                        nome,
                        telefone,
                    )

                    if cod_empresa == 11:
                        payload = _payload_empresa_11(contact_id, telefone, modelo, placa, dia, hora)
                    else:
                        payload = _payload_empresa_33(contact_id, telefone, modelo, placa, dia, hora)

                    headers = {
                        "api_access_token": os.getenv("CHATWOOT_TOKEN"),
                        "Content-Type": "application/json",
                    }
                    response = requests.request(
                        "POST",
                        "https://chat.caiuas.com.br/api/v1/accounts/1/conversations",
                        headers=headers,
                        data=payload,
                    )

                    if response.status_code in [200, 201]:
                        _marcar_status(cur_oracle, conn_oracle, id_log, "enviado")
                        enviados += 1
                    else:
                        logger.error(
                            "send_wpp_agendamento: erro ao enviar telefone=%s id_log=%s status=%s body=%s",
                            telefone,
                            id_log,
                            response.status_code,
                            response.text,
                        )
                        erros += 1

        return {"processed": len(rows), "sent": enviados, "errors": erros}

    except Exception as exc:
        logger.exception("send_wpp_agendamento: falha na execucao: %s", exc)
        raise
    finally:
        if cur_chatwoot:
            try:
                cur_chatwoot.close()
            except Exception:
                pass
        if conn_chatwoot:
            try:
                conn_chatwoot.close()
            except Exception:
                pass
        if cur_oracle:
            try:
                cur_oracle.close()
            except Exception:
                pass
        if conn_oracle:
            try:
                conn_oracle.close()
            except Exception:
                pass
