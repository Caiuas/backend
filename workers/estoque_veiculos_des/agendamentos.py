import jaydebeapi
import json
import requests
from dotenv import load_dotenv
import os
from time import sleep
from datetime import datetime, timedelta
load_dotenv()

def conn_oracle():
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

def format_datetime(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    else:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def extract_years(value):
    text = str(value).strip() if value is not None else ""
    if not text:
        return None, None

    def normalize(part):
        if not part:
            return None
        digits = "".join(filter(str.isdigit, part))
        if len(digits) == 4:
            return digits
        if len(digits) == 2:
            return f"20{digits}"
        return None

    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        fab = normalize(parts[0]) if parts else None
        mod = normalize(parts[-1]) if parts else None
        return fab, mod

    fab = normalize(text[:2])
    mod = normalize(text[-2:])
    return fab, mod

while True:
    now = datetime.now()
    
    primeiro_dia = now.replace(day=1).strftime("%Y-%m-%d")
    proximo_mes = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    ultimo_dia = (proximo_mes - timedelta(days=1)).strftime("%Y-%m-%d")
    conn, cur = conn_oracle()

    query = f"""
        SELECT *
    FROM (
        SELECT t.*, ROWNUM AS rn
        FROM (
            SELECT
                em.cgc cnpjClient,
                oa.cod_os_agenda numAppointment,
                s.data_comeca dtAppointmentStart,
                s.data_fim dtAppointmentEnd,
                c.cod_cliente cpfCnpj,
                CASE
                    WHEN c.cod_cliente IS NULL THEN oa.cliente_nome
                    ELSE c.nome
                END name, 
                oa.chassi chassi,
                oa.placa plate,
                cf.ano AS ano_veiculo,         -- Coluna adicionada
                cf.cor_veiculo AS cor_veiculo,  -- Coluna adicionada
                pm.descricao_modelo,
                oa.cod_empresa
            FROM os_agenda_servicos s
            LEFT JOIN CRM_EVENTOS ce ON 1=1
                AND ce.COD_EMPRESA = s.crm_cod_empresa
                AND ce.COD_EVENTO = s.CRM_COD_EVENTO
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND oa.COD_EMPRESA = s.COD_EMPRESA
                AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA
            LEFT JOIN CLIENTES c ON 1=1
                AND c.COD_CLIENTE = oa.cod_cliente
            LEFT JOIN PRISMA_BOX pb ON 1=1
                AND pb.PRISMA = oa.PRISMA
            LEFT JOIN produtos p ON 1=1
                AND p.COD_PRODUTO = oa.COD_PRODUTO
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = oa.COD_PRODUTO
                AND pm.COD_MODELO = oa.COD_MODELO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN os o ON 1=1
                AND oa.COD_EMPRESA = o.COD_EMPRESA
                AND oa.COD_OS_AGENDA = o.COD_OS_AGENDA
                AND o.ORCAMENTO <> 'S'
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.NOME = oa.CONSULTOR
            LEFT JOIN empresas_usuarios eu3 ON 1=1
                AND eu3.NOME = oa.quem_abriu
            LEFT JOIN empresas em ON 1=1
                AND em.cod_empresa = oa.cod_empresa
            LEFT JOIN clientes_frota cf ON 1=1
                AND cf.chassi = oa.chassi
                AND cf.vendido IS NOT NULL
                AND cf.vendido <> 'S'
            LEFT JOIN caiuas_os_agenda_des coad ON 1=1
                AND coad.cod_empresa = oa.COD_EMPRESA 
                AND coad.cod_os_agenda = oa.COD_OS_AGENDA 
            WHERE 1=1
                AND s.data_comeca IS NOT NULL
                AND s.COD_EMPRESA IN (11,33)
                --AND coad.data_envio IS null
                AND trunc(s.data_comeca) >= trunc(CURRENT_DATE)
            ORDER BY
                s.data_comeca DESC
            ) t 
                )
                WHERE 1=1
                    --rn BETWEEN 1 AND 1
    """
    cur.execute(query)
    r = cur.fetchall()
    veiculos = []
    if len(r) == 0:
        print('Nenhum agendamento novo para enviar')
        conn.close()
        # espera 5 minutos
        sleep(300)
        continue
    # print('Consultou o veículo')
    # print(r)
    for i in r:

        veiculo = {
            "cnpjClient": None,
            "numAppointment": None,
            "dtAppointmentStart": None,
            "dtAppointmentEnd": None,
            "cpfCnpj": None,
            "name": None,
            "chassi": None,
            "plate": None,
            "model": None,
            "yearFab": None,
            "yearMod": None,
            "color": None,
            "description": None,
            "typeOs": None
        }
        
        description = ''
        veiculo["cnpjClient"] = veiculo["cnpjClient"] = "".join(filter(str.isdigit, str(i[0]))) if i[0] else None
        veiculo["numAppointment"] = i[1]
        veiculo["dtAppointmentStart"] = format_datetime(i[2])
        veiculo["dtAppointmentEnd"] = format_datetime(i[3])
        veiculo["cpfCnpj"] = i[4]
        veiculo["name"] = i[5]
        veiculo["chassi"] = i[6]
        veiculo["plate"] = i[7]
        veiculo["yearFab"] = extract_years(i[8])[0]  # Extrai o ano de fabricação
        veiculo["yearMod"] = extract_years(i[8])[1]  # Extrai o ano do modelo
        veiculo["color"] = i[9]  # Usa a cor do veículo
        veiculo["model"] = i[10]  # Usa a descrição do modelo
        veiculo["description"] = None  # Mantém como None, pois não há informação no SELECT
        query = f"""
            SELECT oar.DESCRICAO
                FROM OS_AGENDA_RECLAMACAO oar 
                WHERE cod_empresa = {i[11]}
                AND COD_OS_AGENDA = {i[1]}
                ORDER BY cod_os_agenda DESC
            """
        # print(query)
        cur.execute(query)
        r2 = cur.fetchall()
        for j in r2:
            description += j[0] + ' - '
        veiculo["description"] = description[:-3] if description else None


        veiculos.append(veiculo)

    # Fecha a conexão
    
    
    with open("veiculos.json", "w") as f:
        json.dump(veiculos, f)
    # exit()

    url = "https://caiuas-miner-api.dealerequity.com.br/api/auth/login"

    payload = json.dumps({
    "username": os.getenv('DES_USER'),
    "password": os.getenv('DES_PASSWORD')
    })
    headers = {
    'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception("Erro ao autenticar na API")
    token = response.json()["token"]

    with open("veiculos2.json", "w") as f:
        json.dump(veiculos, f)

    url = "https://caiuas-miner-api.dealerequity.com.br/api/push/appointment"
    payload = json.dumps(veiculos)
    # print(payload)
    # exit()
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.status_code)
    
    if response.status_code != 201:
        try:
            conn.close()
        except:
            pass
        raise Exception("Erro ao enviar veículos para a API")
    # else:
    #     for r in r:
    #         query = f"""
    #             insert into caiuas_os_agenda_des (cod_empresa, cod_os_agenda, data_envio) values
    #             ({r[11]}, {r[1]}, SYSDATE)
    #         """
    #         cur.execute(query)
    #         conn.commit()
    #     conn.close()
    
    print(f"Apondamentos: {len(veiculos)}")
    # exit()
    sleep(600)  