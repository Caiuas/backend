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

cont = 0
while True:
    query = f"""
    SELECT id_log, cod_empresa, cod_os_agenda, name 
    FROM CAIUAS_LOG_WHATSAPP clw 
    WHERE 1=1
        AND clw.STATUS = 'pendente'
    ORDER BY id_log desc
    """
    conn, cur = oracle()
    conn_chatwoot, cur_chatwoot = chatwoot()
    cur.execute(query)
    rows = cur.fetchall()
    print(rows)
    if not rows:
        print("Nenhum registro encontrado.")
        cur.close()
        conn.close()
        sleep(5)
        continue
    print(f"Registros encontrados: {len(rows)}")
    for row in rows:
        
        cod_empresa = row[1]
        cod_os_agenda = row[2]
        message = row[3]
        if int(cod_empresa) == 11:
            query = f"""
                    SELECT
                        ce.COD_EVENTO,
                        c.NOME,
                        concat (c.PREFIXO_RES, c.TELEFONE_RES) residencial,
                        concat (c.PREFIXO_COM, c.TELEFONE_COM) comercial,
                        concat (c.PREFIXO_FAX, c.TELEFONE_FAX) fax,	
                        concat (c.PREFIXO_CEL, c.TELEFONE_CEL) celular,
                        concat (c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST) whatsapp,
                        pm.DESCRICAO_MODELO, 
                        oa.PLACA ,
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
                        AND oa.cod_empresa = 11
                        and oa.COD_OS_AGENDA = {cod_os_agenda}
                    ORDER BY oa.DATA_AGENDADA desc
            """
            conn, cur = oracle()
            cur.execute(query)
            result = cur.fetchall()
            if len(result) == 0:
                query = f"""
                    update CAIUAS_LOG_WHATSAPP clw 
                    set clw.STATUS = 'Erro - Registro não encontrado'
                    where clw.id_log = {row[0]}
                    """
                cur.execute(query)
                conn.commit()
            else:
                for i in result:
                    telefones = []
                    residencial = i[2]
                    comercial = i[3]
                    fax = i[4]
                    celular = i[5]
                    whatsapp = i[8]
                    residencial = ''.join(filter(str.isdigit, str(residencial)))
                    comercial = ''.join(filter(str.isdigit, str(comercial)))
                    fax = ''.join(filter(str.isdigit, str(fax)))
                    celular = ''.join(filter(str.isdigit, str(celular)))
                    whatsapp = ''.join(filter(str.isdigit, str(whatsapp)))
                    if residencial and len(residencial) == 11:
                        if residencial[2] == '9':
                            telefones.append(residencial)
                    if comercial and len(comercial) == 11:
                        if comercial[2] == '9':
                            telefones.append(comercial)
                    if fax and len(fax) == 11:
                        if fax[2] == '9':
                            telefones.append(fax)
                    if celular and len(celular) == 11:
                        if celular[2] == '9':
                            telefones.append(celular)
                    if whatsapp and len(whatsapp) == 11:
                        if whatsapp[2] == '9':
                            telefones.append(whatsapp)
                    telefones = list(set(telefones))
                    telefones = [f"55{telefone}" for telefone in telefones if telefone]
                    
                    for telefone in telefones:
                        data_agendada = i[9]
                        data_agendada = datetime.strptime(data_agendada, "%Y-%m-%d %H:%M:%S")
                        dia = data_agendada.strftime("%d/%m")
                        hora = data_agendada.strftime("%H:%M")
                        modelo = str(i[7]).upper()
                        placa = str(i[8]).upper()
                        print(f"Enviando mensagem para {telefone} ({cont}/{len(telefones)})")
                        query = f"""
                            WITH update_result AS (
                            UPDATE contacts
                            SET
                                "name" = '{str(i[1]).upper()}',
                                updated_at = now(),
                                last_activity_at = now()
                            WHERE phone_number = '+{telefone}'
                            RETURNING id
                        ),
                        insert_result AS (
                            INSERT INTO contacts
                            ("name", email, phone_number, account_id, created_at, updated_at, additional_attributes, identifier, custom_attributes, last_activity_at, contact_type, middle_name, last_name, "location", country_code, "blocked")
                            SELECT
                                '{str(i[1]).upper()}', NULL, '+{telefone}', 1, now(), now(), '{{}}'::jsonb, NULL, '{{}}'::jsonb, now(), 1, '', '', NULL, NULL, false
                            WHERE NOT EXISTS (SELECT 1 FROM update_result)
                            RETURNING id
                        )
                        SELECT id FROM update_result
                        UNION ALL
                        SELECT id FROM insert_result;
                        """
                        cur_chatwoot.execute(query)
                        conn_chatwoot.commit()
                        contact_id = cur_chatwoot.fetchone()[0]
                        url = "https://chat.caiuas.com.br/api/v1/accounts/1/conversations"
                        payload = json.dumps({
                        "inbox_id": 1,
                        "contact_id": contact_id,
                        "source_id": f"{telefone}",
                        "message": {
                            "content": f"Confirmamos o agendamento de seu veículo:\n\nModelo: {modelo}\nPlaca: {placa}\nDia: {dia}\nHorário: {hora}\nUnidade: Sorocaba\n\n*Para melhor atende-lo solicitamos que chegue no horário agendado*\n\n•Trazer o manual de garantia;\n•Pedimos a gentileza de retirar todos os pertences pessoais do veículo;\n\nEndereço: Av. Dom Aguirre, 2865 - Jardim Santa Rosália - Sorocaba/SP\n\nA Honda Caiuás agradece a preferência, tenha um excelente dia!\n\n*Sistema Carona Aos Clientes Pós-venda**\n* O Sistema Carona Caiuás funciona diariamente de 2° à 6°feira no período entre 08:30 e 11:00h*\n* O primeiro carro sai diariamente às 08:30h. Os subsequentes dependem do horário de retorno do veículo à concessionária, não sendo possível prever exatamente o horário das próximas saída*. \n* A rota é estabelecida visando otimizar cada saída. \n* O Sistema Carona Caiuás abrange exclusivamente a cidade de Sorocaba.",
                            "template_params": {
                            "name": "confirma_agenda_sorocaba",
                            "category": "UTILITY",
                            "language": "pt_BR",
                            "processed_params": {
                                "modelo": f"{modelo}",
                                "placa": f"{placa}",
                                "dia": f"{dia}",
                                "hora": f"{hora}"
                            }
                            }
                        },
                        "assignee_id": 2
                        })
                        headers = {
                        'api_access_token': f'{os.getenv("CHATWOOT_TOKEN")}',
                        'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)
                        if response.status_code == 200 or response.status_code == 201:
                            query = f"""
                            update CAIUAS_LOG_WHATSAPP clw 
                            set clw.STATUS = 'enviado'
                            where clw.id_log = {row[0]}
                            """
                            cur.execute(query)
                            conn.commit()
                        else:
                            print(f"Erro ao enviar mensagem para {telefone}: {response.status_code} - {response.text}")
        
        if int(cod_empresa) == 33:
            query = f"""
                SELECT
                    ce.COD_EVENTO,
                    c.NOME,
                    concat (c.PREFIXO_RES, c.TELEFONE_RES) residencial,
                    concat (c.PREFIXO_COM, c.TELEFONE_COM) comercial,
                    concat (c.PREFIXO_FAX, c.TELEFONE_FAX) fax,	
                    concat (c.PREFIXO_CEL, c.TELEFONE_CEL) celular,
                    concat (c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST) whatsapp,
                    pm.DESCRICAO_MODELO, 
                    oa.PLACA ,
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
                    AND oa.cod_empresa = 33
                    and oa.COD_OS_AGENDA = {cod_os_agenda}
                ORDER BY oa.DATA_AGENDADA desc
        """
        conn, cur = oracle()
        conn_chatwoot, cur_chatwoot = chatwoot()
        cur.execute(query)
        result = cur.fetchall()
        cont = 0
        telefones_enviados = []
        for i in result:
            telefones = []
            residencial = i[2]
            comercial = i[3]
            fax = i[4]
            celular = i[5]
            whatsapp = i[8]
            residencial = ''.join(filter(str.isdigit, str(residencial)))
            comercial = ''.join(filter(str.isdigit, str(comercial)))
            fax = ''.join(filter(str.isdigit, str(fax)))
            celular = ''.join(filter(str.isdigit, str(celular)))
            whatsapp = ''.join(filter(str.isdigit, str(whatsapp)))
            if residencial and len(residencial) == 11:
                if residencial[2] == '9':
                    telefones.append(residencial)
            if comercial and len(comercial) == 11:
                if comercial[2] == '9':
                    telefones.append(comercial)
            if fax and len(fax) == 11:
                if fax[2] == '9':
                    telefones.append(fax)
            if celular and len(celular) == 11:
                if celular[2] == '9':
                    telefones.append(celular)
            if whatsapp and len(whatsapp) == 11:
                if whatsapp[2] == '9':
                    telefones.append(whatsapp)
            telefones = list(set(telefones))  # Remove duplicates
            telefones = [f"55{telefone}" for telefone in telefones if telefone]
            for telefone in telefones:
                cont += 1
                data_agendada = i[9]
                data_agendada = datetime.strptime(data_agendada, "%Y-%m-%d %H:%M:%S")
                print(data_agendada)
                dia = data_agendada.strftime("%d/%m")
                hora = data_agendada.strftime("%H:%M")
                modelo = str(i[7]).upper()
                placa = str(i[8]).upper()
                query = f"""
                    WITH update_result AS (
                    UPDATE contacts
                    SET
                        "name" = '{str(i[1]).upper()}',
                        updated_at = now(),
                        last_activity_at = now()
                    WHERE phone_number = '+{telefone}'
                    RETURNING id
                ),
                insert_result AS (
                    INSERT INTO contacts
                    ("name", email, phone_number, account_id, created_at, updated_at, additional_attributes, identifier, custom_attributes, last_activity_at, contact_type, middle_name, last_name, "location", country_code, "blocked")
                    SELECT
                        '{str(i[1]).upper()}', NULL, '+{telefone}', 1, now(), now(), '{{}}'::jsonb, NULL, '{{}}'::jsonb, now(), 1, '', '', NULL, NULL, false
                    WHERE NOT EXISTS (SELECT 1 FROM update_result)
                    RETURNING id
                )
                SELECT id FROM update_result
                UNION ALL
                SELECT id FROM insert_result;
                """
                cur_chatwoot.execute(query)
                conn_chatwoot.commit()
                contact_id = cur_chatwoot.fetchone()[0]
                url = "https://chat.caiuas.com.br/api/v1/accounts/1/conversations"
                payload = json.dumps({
                "inbox_id": 1,
                "contact_id": contact_id,
                "source_id": f"{telefone}",
                "message": {
                    "content": f"Confirmamos o agendamento de seu veículo:\n\nModelo: {modelo}\nPlaca: {placa}\nDia: {dia}\nHorário: {hora}\n\nUnidade: Indaiatuba\n\n*Para melhor atende-lo solicitamos que chegue no horário agendado*\n\n•Trazer o manual de garantia;\n•Pedimos a gentileza de retirar todos os pertences pessoais do veículo;\n\nEndereço: Av. Pres. Vargas, 1168 - Centro, Indaiatuba.\n\nA Honda Caiuás agradece a preferência, tenha um excelente dia!",
                    "template_params": {
                    "name": "confirma_agenda_indaiatuba",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "processed_params": {
                        "modelo": f"{modelo}",
                        "placa": f"{placa}",
                        "dia": f"{dia}",
                        "hora": f"{hora}"
                    }
                    }
                },
                "assignee_id": 2
                })
                headers = {
                'api_access_token': f'{os.getenv("CHATWOOT_TOKEN")}',
                'Content-Type': 'application/json'
                }
                response = requests.request("POST", url, headers=headers, data=payload)
                if response.status_code == 200 or response.status_code == 201:
                    query = f"""
                    update CAIUAS_LOG_WHATSAPP clw 
                    set clw.STATUS = 'enviado'
                    where clw.id_log = {row[0]}
                    """
                    cur.execute(query)
                    conn.commit()
                else:
                    print(f"Erro ao enviar mensagem para {telefone}: {response.status_code} - {response.text}")
        
        # print(f"Registro atualizado: {row[0]} - {row[3]}")
        
        # Simulate sending a message
        # payload = {
        #     "cod_empresa": row[1],
        #     "cod_os_agenda": row[2],
        #     "message": f"Mensagem enviada para {row[3]}"
        # }
        # response = requests.post(os.getenv('API_URL'), json=payload)
        # if response.status_code == 200:
        #     print(f"Mensagem enviada com sucesso para {row[3]}")
        # else:
        #     print(f"Erro ao enviar mensagem para {row[3]}: {response.text}")