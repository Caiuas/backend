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

RDSTATION_CRM_TOKEN = os.getenv("RDSTATION_CRM_TOKEN", "690e0fae49c7af001325954a")
RDSTATION_CLIENT_ID = os.getenv("RDSTATION_CLIENT_ID", "9e92497d-1c87-433e-a114-ec1280409dff")
RDSTATION_CLIENT_SECRET = os.getenv("RDSTATION_CLIENT_SECRET", "8c6b23279c01463faf65ec8f9e9bd37b")
RDSTATION_REFRESH_TOKEN = os.getenv("RDSTATION_REFRESH_TOKEN", "n53CRz_SUPSrv1ugmrYk4jFXwDFBWSmpbH_gIxpKR6k")

DEAL_STAGE_ID = "69174534bf3d7a0013223cf1"
USER_ID = "5cd0bc3c78ba160010ea287c"
DEAL_SOURCE_ID = "665645bae4789f00230ad321"

FIELD_DESCRICAO_PRODUTO = "69f3bc1ab9d9320015bbf4fa"
FIELD_MODELO = "69f3bc78a42fdb0013e3009d"
FIELD_SEGURO_AUTO = "5ceeb230498142001048ea9d"
FIELD_NOVO_USADO = "69f3bcf4047a570013fec9ea"
FIELD_COD_PROPOSTA = "69f3bd4d48260700132d2adc"
FIELD_CHASSI = "69f3bd8e347954001de63c25"
FIELD_DATA_PROPOSTA = "69f3bde6faa816001315cfc0"
FIELD_CIDADE = "69f3be30b9d9320019bbfef7"
FIELD_NOME_VENDEDOR = "69fde0e09532050020f0ed87"
FIELD_EMPRESA = "69fde98e62b32c0013411e36"

TOKENS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rdstation_tokens.json")


def _fetch_proposta(cursor):
    query = """
        SELECT * FROM (
            SELECT
                to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
                vp.EMISSAO DATA_PROPOSTA,
                vp.data_venda,
                vp.COD_CLIENTE,
                eu.NOME_COMPLETO NOME_VENDEDOR,
                eu.COD_EMPRESA,
                pr.descricao_produto DESCRICAO_PRODUTO,
                pm.DESCRICAO_MODELO MODELO,
                COALESCE(ce_veic.DESCRICAO, ce_ped.DESCRICAO, ce_fic.DESCRICAO) AS COR,
                v.CHASSI_COMPLETO,
                c.cod_cliente CPF_CNPJ,
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
                        UNION ALL
                        SELECT COD_CLIENTE, TRIM(PREFIXO_MSG_TXT_INST) || TRIM(NUMERO_MSG_TXT_INST) FROM clientes WHERE NUMERO_MSG_TXT_INST IS NOT NULL
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
                        UNION ALL
                        SELECT COD_CLIENTE, EMAIL_TRABALHO FROM clientes WHERE EMAIL_TRABALHO IS NOT NULL
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
                END CIDADE_CLIENTE
            FROM VEICULOS_PROPOSTAS vP
            LEFT JOIN VEICULOS_PEDIDOS vped ON vp.COD_PEDIDO = vped.COD_PEDIDO
            LEFT JOIN PROP_FICTICIA_DADOS pfd ON vp.COD_FICTICIO = pfd.COD_FICTICIO
            LEFT JOIN caiuas_sync_rdstation csr ON csr.cod_proposta = vp.cod_proposta
            LEFT JOIN VEICULOS v ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
            LEFT JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO
            LEFT JOIN CORES_EXTERNAS ce_veic ON ce_veic.COR_EXTERNA = v.COR_EXTERNA
            LEFT JOIN CORES_EXTERNAS ce_ped ON ce_ped.COR_EXTERNA = vped.COR_EXTERNA
            LEFT JOIN CORES_EXTERNAS ce_fic ON ce_fic.COR_EXTERNA = pfd.COR_EXTERNA
            LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
            LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES
            LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM
            LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA
            WHERE vp.status_proposta NOT IN ('C')
                AND TRUNC(vp.emissao) >= TO_DATE('2026-05-04', 'YYYY-MM-DD')
                AND eu.NOME_COMPLETO NOT IN ('DIRETORIA SOROCABA','LUIS ROBERTO DE OLIVEIRA')
                AND csr.id_crm IS NULL
                AND c.cod_cliente <> '22534303000127'
            ORDER BY vp.emissao
        ) WHERE ROWNUM = 1
    """
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    if not row:
        return None
    return dict(zip(columns, row))


def _buscar_id_crm_cliente_antigo(cursor, cod_cliente):
    query = """
        SELECT id_crm FROM (
            SELECT csr.id_crm
            FROM veiculos_propostas vp
            JOIN caiuas_sync_rdstation csr ON csr.cod_proposta = vp.cod_proposta
            WHERE vp.cod_cliente = ?
              AND csr.id_crm IS NOT NULL
              AND vp.EMISSAO >= TRUNC(SYSDATE) - 60
            ORDER BY vp.EMISSAO DESC
        ) WHERE ROWNUM = 1
    """
    cursor.execute(query, [cod_cliente])
    row = cursor.fetchone()
    return row[0] if row else None


def _split_unique(value):
    if not value:
        return []
    return list(dict.fromkeys([v.strip() for v in str(value).split('|') if v.strip()]))


def _format_date(value):
    if not value:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    return datetime.fromisoformat(str(value)).strftime('%d/%m/%Y')


def _email_valido(email):
    if not email:
        return False
    email = email.strip().lower()
    if ' ' in email:
        return False
    if email.count('@') != 1:
        return False
    local, domain = email.split('@')
    if not local or not domain:
        return False
    if local.startswith('.') or local.endswith('.'):
        return False
    if '.' not in domain:
        return False
    if domain.startswith('.') or domain.endswith('.'):
        return False
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _filtrar_emails_validos(emails):
    if not emails:
        return []
    return [e for e in emails if _email_valido(e)]


def _carregar_tokens():
    try:
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "access_token": None,
            "refresh_token": RDSTATION_REFRESH_TOKEN,
        }


def _salvar_tokens(tokens):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f)


def _refresh_access_token(tokens):
    response = requests.post(
        "https://api.rd.services/auth/token",
        json={
            "client_id": RDSTATION_CLIENT_ID,
            "client_secret": RDSTATION_CLIENT_SECRET,
            "refresh_token": tokens["refresh_token"],
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if response.status_code == 200:
        data = response.json()
        tokens["access_token"] = data.get("access_token")
        tokens["refresh_token"] = data.get("refresh_token", tokens["refresh_token"])
        _salvar_tokens(tokens)
        return tokens["access_token"]
    else:
        logger.error("sync_rdstation: erro ao obter access_token: %s", response.text)
        return None


def _obter_access_token():
    tokens = _carregar_tokens()

    if tokens.get("access_token"):
        return tokens["access_token"]

    return _refresh_access_token(tokens)


def _mapear_empresa(cod_empresa):
    mapeamento = {
        11: "HONDA SOROCABA",
        33: "HONDA INDAIATUBA",
        111: "LLA",
    }
    if cod_empresa in mapeamento:
        return mapeamento[cod_empresa]
    return "EMPRESA NAO IDENTIFICADA"


def _mapear_user_id(cod_empresa):
    mapeamento = {
        11: "654a7269852b02000dad51d7",
        33: "6823a3b6644f430014250fbd",
        111: "654a7269852b02000dad51d7",
    }
    return mapeamento.get(cod_empresa, "654a7269852b02000dad51d7")


def _extrair_tags(proposta):
    tags = ["social", "NBS", "Seguro Auto"]

    for campo in ["NOVO_USADO", "CIDADE_CLIENTE", "MODELO", "DESCRICAO_PRODUTO"]:
        valor = proposta.get(campo)
        if valor and isinstance(valor, str) and valor.strip():
            tags.append(valor.strip())

    return tags


def _criar_conversao_rdstation(proposta, deal_url, email):
    nome_cliente = (proposta.get('NOME_CLIENTE') or '').strip()
    tags = _extrair_tags(proposta)

    tokens = _carregar_tokens()
    access_token = tokens.get("access_token")
    if not access_token:
        access_token = _refresh_access_token(tokens)
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
                    "job_title": "",
                    "company_name": nome_cliente,
                    "tags": tags,
                    "traffic_source": "NBS",
                    "traffic_campaign": "NBS",
                    "cf_estagio_do_funil": "Fazer contato",
                    "cf_funil": "Funil Seguros - F&I",
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
            tokens = _carregar_tokens()
            access_token = _refresh_access_token(tokens)
            if not access_token:
                return None
            continue

        logger.info("sync_rdstation: conversao HTTP %s - %s", response.status_code, response.text[:500])

        if response.status_code in (200, 201):
            data = response.json()
            return data.get("event_uuid")
        else:
            logger.error("sync_rdstation: erro ao criar conversao: %s", response.text)
            return None

    return None


def _criar_deal_rdstation(proposta):
    cod_proposta = proposta['COD_PROPOSTA']
    cod_empresa = proposta.get('COD_EMPRESA')
    user_id = _mapear_user_id(cod_empresa)
    modelo = (proposta.get('MODELO') or '').strip()
    data_str = _format_date(proposta.get('DATA_PROPOSTA'))
    nome_cliente = (proposta.get('NOME_CLIENTE') or '').strip()
    deal_name = f"{modelo} - {data_str} - {nome_cliente}"

    deal_custom_fields = []

    descricao = proposta.get('DESCRICAO_PRODUTO')
    if descricao:
        deal_custom_fields.append({"custom_field_id": FIELD_DESCRICAO_PRODUTO, "value": descricao})

    modelo_val = proposta.get('MODELO')
    if modelo_val:
        deal_custom_fields.append({"custom_field_id": FIELD_MODELO, "value": modelo_val})

    deal_custom_fields.append({"custom_field_id": FIELD_SEGURO_AUTO, "value": "Seguro Auto"})

    novo_usado = proposta.get('NOVO_USADO')
    if novo_usado:
        deal_custom_fields.append({"custom_field_id": FIELD_NOVO_USADO, "value": novo_usado})

    deal_custom_fields.append({"custom_field_id": FIELD_COD_PROPOSTA, "value": cod_proposta})

    chassi = proposta.get('CHASSI_COMPLETO')
    if chassi:
        deal_custom_fields.append({"custom_field_id": FIELD_CHASSI, "value": chassi})

    if data_str:
        deal_custom_fields.append({"custom_field_id": FIELD_DATA_PROPOSTA, "value": data_str})

    cidade = proposta.get('CIDADE_CLIENTE')
    if cidade:
        deal_custom_fields.append({"custom_field_id": FIELD_CIDADE, "value": cidade})

    nome_vendedor = proposta.get('NOME_VENDEDOR')
    if nome_vendedor:
        deal_custom_fields.append({"custom_field_id": FIELD_NOME_VENDEDOR, "value": nome_vendedor})

    cod_empresa = proposta.get('COD_EMPRESA')
    if cod_empresa:
        empresa_nome = _mapear_empresa(cod_empresa)
        deal_custom_fields.append({"custom_field_id": FIELD_EMPRESA, "value": empresa_nome})

    phones = _split_unique(proposta.get('TELEFONES'))
    emails_raw = _split_unique(proposta.get('EMAILS'))
    emails = _filtrar_emails_validos(emails_raw)

    if emails_raw and not emails:
        logger.warning("sync_rdstation: proposta %s com emails invalidos descartados: %s", cod_proposta, emails_raw)
    elif len(emails) < len(emails_raw):
        logger.warning(
            "sync_rdstation: proposta %s com parte dos emails invalidos descartados (%s de %s)",
            cod_proposta,
            len(emails_raw) - len(emails),
            len(emails_raw),
        )

    contact = {"name": nome_cliente}
    if emails:
        contact["emails"] = [{"email": e} for e in emails]
    if phones:
        contact["phones"] = [{"phone": p, "type": "cellphone"} for p in phones]

    payload = {
        "deal": {
            "name": deal_name,
            "deal_stage_id": DEAL_STAGE_ID,
            "user_id": user_id,
            "deal_custom_fields": deal_custom_fields,
        },
        "deal_source": {"_id": DEAL_SOURCE_ID},
        "contacts": [contact] if (emails or phones) else [],
    }

    logger.info("sync_rdstation: criando deal para proposta %s", cod_proposta)

    response = requests.post(
        f"https://crm.rdstation.com/api/v1/deals?token={RDSTATION_CRM_TOKEN}",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    logger.info("sync_rdstation: resposta HTTP %s - %s", response.status_code, response.text[:500])

    data = {}
    try:
        data = response.json()
    except ValueError:
        pass

    if response.status_code in (200, 201):
        return data.get("_id") or data.get("id")

    # Alguns cenarios retornam 422 por dados do contato, mas o deal e criado e vem com id no corpo.
    if response.status_code == 422:
        deal_id = data.get("_id") or data.get("id")
        if deal_id:
            logger.warning("sync_rdstation: deal criado com aviso de validacao (HTTP 422), id=%s", deal_id)
            return deal_id

    logger.error("sync_rdstation: erro ao criar deal - %s", response.text)
    return None


def _insert_sync(cursor, cod_proposta, id_crm, id_mkt):
    cursor.execute(
        "INSERT INTO caiuas_sync_rdstation (cod_proposta, id_crm, id_mkt, created_at, updated_at) VALUES (?, ?, ?, SYSTIMESTAMP, SYSTIMESTAMP)",
        [cod_proposta, id_crm, id_mkt],
    )


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_propostas_rdstation(self):
    conn = None
    cursor = None

    try:
        conn, cursor = oracle()

        proposta = _fetch_proposta(cursor)
        if not proposta:
            logger.info("sync_rdstation: nenhuma proposta pendente")
            return {"status": "no_pending"}

        cod_proposta = proposta['COD_PROPOSTA']
        cod_cliente = proposta.get('COD_CLIENTE')

        logger.info("sync_rdstation: processando proposta %s, cliente %s", cod_proposta, cod_cliente)

        id_crm = _buscar_id_crm_cliente_antigo(cursor, cod_cliente)

        if id_crm:
            # Correção no texto do log para refletir a lógica certa
            logger.info("sync_rdstation: reutilizando id_crm %s do cliente %s (proposta nos ultimos 60 dias)", id_crm, cod_cliente)
        else:
            id_crm = _criar_deal_rdstation(proposta)
            if not id_crm:
                logger.error("sync_rdstation: falha ao criar deal para proposta %s", cod_proposta)
                return {"status": "error", "cod_proposta": cod_proposta, "details": "failed to create deal"}

        emails_raw = _split_unique(proposta.get('EMAILS'))
        emails_validos = _filtrar_emails_validos(emails_raw)

        if emails_validos:
            deal_url = f"https://crm.rdstation.com/app/#/deals/{id_crm}"
            id_mkt = _criar_conversao_rdstation(proposta, deal_url, emails_validos[0])
            if not id_mkt:
                id_mkt = "DADOS_INVALIDOS"
                logger.warning("sync_rdstation: falha na conversao MKT para proposta %s", cod_proposta)
        else:
            id_mkt = "DADOS_INVALIDOS"
            logger.info("sync_rdstation: sem emails validos para proposta %s", cod_proposta)

        _insert_sync(cursor, cod_proposta, id_crm, id_mkt)
        conn.jconn.commit()

        logger.info("sync_rdstation: proposta %s sincronizada - crm=%s mkt=%s", cod_proposta, id_crm, id_mkt)
        return {"status": "success", "cod_proposta": cod_proposta, "id_crm": id_crm, "id_mkt": id_mkt}

    except Exception as exc:
        logger.error("sync_rdstation: erro: %s", exc)
        if conn:
            try:
                conn.jconn.rollback()
            except Exception:
                pass
        raise self.retry(exc=exc)

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
