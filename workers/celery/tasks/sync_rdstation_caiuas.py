import os
import re
import logging
import json
import requests
from datetime import datetime, date
from dotenv import load_dotenv
from app import app
from database import oracle

load_dotenv()

logger = logging.getLogger(__name__)

# Credenciais RD Station - Conta Secundária (CAIUAS)
RDSTATION_CLIENT_ID_CAIUAS = os.getenv("RDSTATION_CLIENT_ID_CAIUAS")
RDSTATION_CLIENT_SECRET_CAIUAS = os.getenv("RDSTATION_CLIENT_SECRET_CAIUAS")
RDSTATION_REFRESH_TOKEN_CAIUAS = os.getenv("RDSTATION_REFRESH_TOKEN_CAIUAS")

# Arquivo de tokens isolado para a conta Caiuás
TOKENS_FILE_CAIUAS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rdstation_tokens_caiuas.json")

def _carregar_tokens_caiuas():
    try:
        with open(TOKENS_FILE_CAIUAS, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "access_token": None,
            "refresh_token": RDSTATION_REFRESH_TOKEN_CAIUAS,
        }

def _salvar_tokens_caiuas(tokens):
    os.makedirs(os.path.dirname(TOKENS_FILE_CAIUAS), exist_ok=True)
    with open(TOKENS_FILE_CAIUAS, 'w') as f:
        json.dump(tokens, f)

def _refresh_access_token_caiuas(tokens):
    response = requests.post(
        "https://api.rd.services/auth/token",
        json={
            "client_id": RDSTATION_CLIENT_ID_CAIUAS,
            "client_secret": RDSTATION_CLIENT_SECRET_CAIUAS,
            "refresh_token": tokens["refresh_token"],
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if response.status_code == 200:
        data = response.json()
        tokens["access_token"] = data.get("access_token")
        tokens["refresh_token"] = data.get("refresh_token", tokens["refresh_token"])
        _salvar_tokens_caiuas(tokens)
        return tokens["access_token"]
    else:
        logger.error("sync_rdstation_caiuas: erro ao obter access_token: %s", response.text)
        return None

def _fetch_proposta_caiuas(cursor):
    """
    Consulta propostas pendentes de envio para o MKT Caiuás
    """
    query = """
        SELECT * FROM (
            SELECT
                to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
                vp.EMISSAO DATA_PROPOSTA,
                vp.COD_CLIENTE,
                eu.NOME_COMPLETO NOME_VENDEDOR,
                eu.COD_EMPRESA,
                pr.descricao_produto DESCRICAO_PRODUTO,
                pm.DESCRICAO_MODELO MODELO,
                v.CHASSI_COMPLETO,
                c.NOME NOME_CLIENTE,
                (SELECT LISTAGG(tel, '|') WITHIN GROUP (ORDER BY tel)
                 FROM (
                    SELECT DISTINCT cod_cliente, tel
                    FROM (
                        SELECT COD_CLIENTE, TRIM(PREFIXO_CEL) || TRIM(TELEFONE_CEL) as tel FROM clientes WHERE TELEFONE_CEL IS NOT NULL
                        UNION ALL
                        SELECT COD_CLIENTE, TRIM(PREFIXO_RES) || TRIM(TELEFONE_RES) FROM clientes WHERE TELEFONE_RES IS NOT NULL
                        UNION ALL
                        SELECT COD_CLIENTE, TRIM(PREFIXO_COM) || TRIM(TELEFONE_COM) FROM clientes WHERE TELEFONE_COM IS NOT NULL
                    )
                 ) t_tel
                 WHERE t_tel.cod_cliente = c.cod_cliente
                ) AS TELEFONES,
                (SELECT LISTAGG(email_item, '|') WITHIN GROUP (ORDER BY email_item)
                 FROM (
                    SELECT DISTINCT cod_cliente, email_item
                    FROM (
                        SELECT COD_CLIENTE, EMAIL_NFE as email_item FROM clientes WHERE EMAIL_NFE IS NOT NULL
                        UNION ALL
                        SELECT COD_CLIENTE, EMAIL2 FROM clientes WHERE EMAIL2 IS NOT NULL
                        UNION ALL
                        SELECT COD_CLIENTE, ENDERECO_ELETRONICO FROM clientes WHERE ENDERECO_ELETRONICO IS NOT NULL
                    )
                 ) t_email
                 WHERE t_email.cod_cliente = c.cod_cliente
                ) AS EMAILS,
                CASE
                    WHEN vp.internet = 'F' THEN 'VENDA DIRETA'
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    ELSE 'Novo'
                END NOVO_USADO,
                CASE
                    WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO
                    WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO
                    ELSE cid_cob.DESCRICAO
                END CIDADE_CLIENTE,
                csr.id_crm
            FROM caiuas_sync_rdstation csr
            JOIN VEICULOS_PROPOSTAS vP ON csr.cod_proposta = vp.cod_proposta
            LEFT JOIN VEICULOS v ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
            LEFT JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO
            LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
            LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES
            LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM
            LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA
            WHERE 1=1
                AND csr.id_mkt_caiuas IS NULL
            ORDER BY vp.emissao
        ) WHERE ROWNUM = 1
    """
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    if not row:
        return None
    return dict(zip(columns, row))

def _split_unique(value):
    if not value:
        return []
    return list(dict.fromkeys([v.strip() for v in str(value).split('|') if v.strip()]))

def _email_valido(email):
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip().lower()))

def _filtrar_emails_validos(emails):
    return [e for e in emails if _email_valido(e)]

def _extrair_tags(proposta):
    # Inserção da tag fixa "cliente showroom"
    tags = ["social", "NBS", "Seguro Auto", "cliente showroom"]
    
    # Inserção das tags dinâmicas baseadas na loja (garantindo conversão para string para evitar erros)
    cod_empresa = proposta.get("COD_EMPRESA")
    if str(cod_empresa) == '33':
        tags.append("honda indaiatuba")
    else:
        tags.append("honda sorocaba")

    for campo in ["NOVO_USADO", "CIDADE_CLIENTE", "MODELO", "DESCRICAO_PRODUTO"]:
        valor = proposta.get(campo)
        if valor and isinstance(valor, str) and valor.strip():
            tags.append(valor.strip())
            
    return tags

def _criar_conversao_rdstation_caiuas(proposta, deal_url, email):
    nome_cliente = (proposta.get('NOME_CLIENTE') or '').strip()
    tags = _extrair_tags(proposta)

    tokens = _carregar_tokens_caiuas()
    access_token = tokens.get("access_token") or _refresh_access_token_caiuas(tokens)
    
    if not access_token:
        return None

    for attempt in range(3):
        response = requests.post(
            "https://api.rd.services/platform/events?event_type=conversion",
            json={
                "event_type": "CONVERSION",
                "event_family": "CDP",
                "payload": {
                    "conversion_identifier": "Proposta emitida no NBS",
                    "name": nome_cliente,
                    "email": email,
                    "company_name": nome_cliente,
                    "tags": tags,
                    "traffic_source": "NBS",
                    "cf_url_da_negociacao": deal_url,
                },
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )

        if response.status_code == 401 and attempt < 2:
            access_token = _refresh_access_token_caiuas(tokens)
            continue

        if response.status_code in (200, 201):
            return response.json().get("event_uuid")
        
        logger.error("sync_rdstation_caiuas: erro na conversao: %s", response.text)
        return None

@app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_propostas_rdstation_caiuas(self):
    conn = None
    cursor = None

    try:
        conn, cursor = oracle()
        proposta = _fetch_proposta_caiuas(cursor)
        
        if not proposta:
            logger.info("sync_rdstation_caiuas: nenhuma proposta pendente")
            return {"status": "no_pending"}

        cod_proposta = proposta['COD_PROPOSTA']
        id_crm = proposta.get('ID_CRM')
        emails_validos = _filtrar_emails_validos(_split_unique(proposta.get('EMAILS')))

        if emails_validos and id_crm:
            deal_url = f"https://crm.rdstation.com/app/#/deals/{id_crm}"
            id_mkt_caiuas = _criar_conversao_rdstation_caiuas(proposta, deal_url, emails_validos[0])
            
            if not id_mkt_caiuas:
                id_mkt_caiuas = "ERRO_ENVIO"
        else:
            id_mkt_caiuas = "DADOS_INVALIDOS"

        cursor.execute(
            "UPDATE caiuas_sync_rdstation SET id_mkt_caiuas = ?, updated_at = SYSTIMESTAMP WHERE cod_proposta = ?",
            [id_mkt_caiuas, cod_proposta]
        )
        conn.jconn.commit()

        return {"status": "success", "cod_proposta": cod_proposta, "id_mkt_caiuas": id_mkt_caiuas}

    except Exception as exc:
        logger.error("sync_rdstation_caiuas: erro: %s", exc)
        if conn: conn.jconn.rollback()
        raise self.retry(exc=exc)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()