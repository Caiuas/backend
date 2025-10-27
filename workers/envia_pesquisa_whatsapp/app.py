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
        TO_CHAR(
            CASE
                WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                ELSE ce.data_novo_contato
            END, 'YYYY-MM-DD HH24:MI:SS'
        ) AS data_contato,
        ce.COD_EVENTO,
        ce.COD_EMPRESA,
        cet.COD_TIPO_EVENTO,
        cet.DESC_TIPO_EVENTO,
        ca.ANDAMENTO,
        CASE
            WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
            ELSE c.NOME 
        END nome_cliente,
        concat(c.PREFIXO_CEL,c.TELEFONE_CEL) tel_cel,
        ce.fone_cliente_avulso,
        ce.email_cliente_avulso,
        c.EMAIL_NFE,
        concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
        concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
        concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
        concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp
    FROM
        CRM_EVENTOS ce
    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
    LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
    LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
    LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
    LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
    LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
    WHERE
        1 = 1
        AND ce.COD_TIPO_EVENTO IN (38,180,30,22)
        AND ce.STATUS IN ('P','CV','CR','CA')
        AND ((ca.ANDAMENTO IS NULL) OR (LOWER(ca.ANDAMENTO) = 'pendente') OR (LOWER(ca.ANDAMENTO) = 'encaminhado ao vendedor'))
        AND CASE
            WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
            ELSE ce.data_novo_contato
        END <= SYSDATE
    ORDER BY
        1
    """
conn, cur = oracle()
cur.execute(query)
rows = cur.fetchall()
cont = 0
print(f"Total de eventos encontrados: {len(rows)}")
for row in rows:
    cont = cont + 1
    telefones_elegiveis = []
    cod_evento = row[1]
    cod_empresa = row[2]
    cod_tipo_evento = row[3]
    telefone_1 = (str(row[7]).strip() if row[7] else "")
    telefone_2 = (str(row[10]).strip() if row[10] else "")
    telefone_3 = (str(row[11]).strip() if row[11] else "")
    telefone_4 = (str(row[12]).strip() if row[12] else "")
    
    # se telefone1 não for só numeros não é elegivel
    if telefone_1 and telefone_1.isdigit() and len(telefone_1) == 11:
        telefones_elegiveis.append(telefone_1)
    
    if telefone_2 and telefone_2.isdigit() and len(telefone_2) == 11:
        telefones_elegiveis.append(telefone_2)
    if telefone_3 and telefone_3.isdigit() and len(telefone_3) == 11:
        telefones_elegiveis.append(telefone_3)
    if telefone_4 and telefone_4.isdigit() and len(telefone_4) == 11:
        telefones_elegiveis.append(telefone_4)
    
    for telefone in telefones_elegiveis:
        # se terceiro digito não for 9 ou 8 remove o telefone da lista
        if len(telefone) == 10 and telefone[-8] not in ['8','9']:
            telefones_elegiveis.remove(telefone)
            # continue
    
    # remova os numeros repetidos
    telefones_elegiveis = list(set(telefones_elegiveis))
    
    # print(f"Evento: {cod_evento} - Telefones elegiveis: {telefones_elegiveis}")
    if len(telefones_elegiveis) == 0:
        
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou, data_novo_contato)
            values (
                {cod_empresa},
                {cod_evento},
                'NBS',
                11, -- tipo acao pesquisa de satisfacao
                SYSDATE,
                'Evento sem telefone de contato elegivel para envio de pesquisa de satisfacao via WhatsApp',
                'E',
                seq_crm_COD_ACAO.nextval,
                null,
                null
            )
        """
        cur.execute(query)
        conn.commit()
        
        query = f"""
            update crm_eventos set                                                                                       
            cod_tipo_fechamento = 2,data_encerramento = sysdate, status = 'E', quem_encerrou = 'NBS',
            cod_motivo_perda = 240, cod_andamento = 107
            where cod_empresa = {cod_empresa} and cod_evento = {cod_evento}
        """
        cur.execute(query)
        conn.commit()
    if len(telefones_elegiveis) > 0:
        erros = 0
        for telefone in telefones_elegiveis:
            if cod_tipo_evento == 30:
                nome_template = "pesquisa_showroom"
                cod_controle = f"SW-{cod_empresa}-{cod_evento}"
            else:
                nome_template = "pesquisa_posvendas_1"
                cod_controle = f"PV-{cod_empresa}-{cod_evento}"
            url = f"https://graph.facebook.com/{os.getenv('WHATSAPP_VERSION')}/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages"
            # telefone = 15988272755
            payload = json.dumps({
                        "messaging_product": "whatsapp",
                        "to": f"+55{telefone}",
                        "type": "template",
                        "template": {
                            "name": nome_template,
                            "language": {
                            "code": "pt_BR"
                            },
                            "components": [
                            {
                                "type": "body",
                                "parameters": [
                                {
                                    "type": "text",
                                    "text": cod_controle
                                }
                                ]
                            },
                            {
                                "type": "button",
                                "sub_type": "flow",
                                "index": "0",
                                "parameters": [
                                {
                                    "type": "action",
                                    "action": {
                                    "flow_token": cod_controle
                                    }
                                }
                                ]
                            }
                            ]
                        }
                        })
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + os.getenv('WHATSAPP_TOKEN')
                }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
            except Exception as e:
                erros += 1
        if erros > 0:
            query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou, data_novo_contato)
            values (
                {cod_empresa},
                {cod_evento},
                'NBS',
                11, -- tipo acao pesquisa de satisfacao
                SYSDATE,
                'Erro ao enviar pesquisa de satisfacao via WhatsApp - Problema com algum numero de telefone',
                'P',
                seq_crm_COD_ACAO.nextval,
                null,
                null
            )
            """
            cur.execute(query)
            conn.commit()
        else:
            query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou, data_novo_contato)
            values (
                {cod_empresa},
                {cod_evento},
                'NBS',
                11, -- tipo acao pesquisa de satisfacao
                SYSDATE,
                'Pesquisa de satisfacao via WhatsApp enviada com sucesso',
                'P',
                seq_crm_COD_ACAO.nextval,
                null,
                null
            )
            """
            cur.execute(query)
            conn.commit()
        query = f"""
        update crm_eventos set                                                                                       
        status = 'P', 
        cod_andamento = 109,
        data_novo_contato = sysdate + 30 -- novo contato em 30 minutos
        where cod_empresa = {cod_empresa} and cod_evento = {cod_evento}
        """
        cur.execute(query)
        conn.commit()
    # if cont == 20:
    #     cur.close()
    #     conn.close()
    #     exit()
            
        # cur.close()
        # conn.close()
        # print(f"Evento: {cod_evento} - Enviando pesquisa para {telefone} - Cod controle: {cod_controle}")
        # exit()
    
            
        

cur.close()
conn.close()
