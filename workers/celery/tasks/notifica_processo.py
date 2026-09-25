import datetime
import html
import os
import sys
from pathlib import Path

import requests
from requests_aws4auth import AWS4Auth

try:
    from database import oracle
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from database import oracle

SES_REGION = "sa-east-1"
SES_SENDER = "pablo@caiuas.com.br"
SES_RECIPIENT = "opabloedu@gmail.com"

gestores = [
    "marcelotcf@caiuas.com.br",
    "opabloedu@gmail.com",
    "welder@caiuas.com.br",
    "ricardo.camargo@caiuas.com.br"
]


def ler_lob(valor):
    if valor is None or isinstance(valor, str):
        return valor
    if hasattr(valor, "getSubString"):
        return valor.getSubString(1, int(valor.length()))
    if hasattr(valor, "getBytes"):
        return bytes(valor.getBytes(1, int(valor.length()))).decode("utf-8", "ignore")
    return str(valor)


def esc(valor):
    return html.escape("" if valor is None else str(valor))


def send_email(subject, body, destinatarios, copia=None):
    auth = AWS4Auth(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        SES_REGION,
        "ses",
        session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
    destination = {"ToAddresses": destinatarios}
    if copia:
        destination["CcAddresses"] = copia
    payload = {
        "FromEmailAddress": SES_SENDER,
        "Destination": destination,
        "Content": {
            "Simple": {
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body}},
            }
        },
    }
    return requests.post(
        f"https://email.{SES_REGION}.amazonaws.com/v2/email/outbound-emails",
        auth=auth,
        json=payload,
        timeout=30,
    )



query = """
    SELECT *
    FROM (
        SELECT resultado.*, ROWNUM AS rn
        FROM (
            SELECT
                NVL(v.cod_proposta, v.cod_proposta_internet) AS cod_proposta,
                --                vp.EMISSAO AS data_proposta, 
                TO_CHAR(vp.DATA_VENDA, 'DD/MM/YYYY HH24:MI') AS DATA_VENDA,
                TRUNC(SYSDATE) - TRUNC(vp.DATA_VENDA) AS dias_emissao,
                --vp.VENDEDOR AS cod_vendedor,  
                eu.EMAIL,
                eu.NOME_COMPLETO AS nome_vendedor, 
                pm.DESCRICAO_MODELO AS modelo, 
                ce.DESCRICAO AS cor, 
                --v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                --e.NOME AS empresa, 
                --v.DATA_NOTA AS emissao,
                p.DESCRICAO AS patio,
                c.COD_CLIENTE, 
                c.NOME AS nome_cliente,
                --CASE 
                --    WHEN v.novo_usado = 'U' THEN 'Usado'
                --    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                --    ELSE 'Novo'
                --END AS novo_usado,
                --cf.PLACA,
                --COALESCE(cid_com.DESCRICAO, cid_res.DESCRICAO, cid_cob.DESCRICAO) AS cidade,
                cvp.ID_PROCESSO,
                --cvp.status,
                --ea.DATA_AGENDADA,
                --ea.DATA_BAIXA,
                cvp.OBS_FATURAMENTO,
                cvp.OBS_ENTREGA,
                cvp.OBS_LIBERACAO,
                cvp.OBS_DOCUMENTACAO,
                cvp.REPASSE,
                NVL(etapas.json_etapas, '[]') AS status_processo_etapas,
                es.DESCRICAO_SALA AS local_entrega,
                --v.COD_EMPRESA AS cod_empresa_veiculo,
                cvp.OBS_ISENCAO,
                cvp.OBS_ACESSORIOS,
                --cvp.DATA_SOLICITACAO,
                --crv.quem_recebeu,
                TO_CHAR(crv.created_at, 'DD/MM/YYYY HH24:MI') AS data_recebimento
                --COUNT(*) OVER() AS total
            FROM veiculos v 
            LEFT JOIN produtos pr 
                ON pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce 
                ON ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm 
                ON pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp 
                ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c 
                ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p 
                ON p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu 
                ON eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 
                ON eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e 
                ON e.cod_empresa = v.COD_EMPRESA
            LEFT JOIN CLIENTES_FROTA cf 
                ON cf.chassi = v.CHASSI_COMPLETO 
                AND cf.COD_CLIENTE = c.COD_CLIENTE  
                AND cf.nome = vp.VENDEDOR 
            LEFT JOIN cidades cid_res 
                ON cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com 
                ON cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob 
                ON cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            LEFT JOIN ev_agendados ea 
                ON ea.STATUS NOT IN ('C')
                AND TO_CHAR(ea.COD_PROPOSTA) = TO_CHAR(vp.COD_PROPOSTA)
                AND TO_CHAR(ea.CHASSI_RESUMIDO) = TO_CHAR(v.CHASSI_RESUMIDO)
            LEFT JOIN EV_SALAS es 
                ON es.cod_sala = ea.cod_sala
            LEFT JOIN caiuas_veic_proc cvp 
                ON cvp.cod_proposta = vp.cod_proposta
            LEFT JOIN caiuas_recebimento_veiculo crv 
                ON crv.cod_modelo = v.COD_MODELO 
                AND crv.cod_produto = v.COD_PRODUTO 
                AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                AND crv.cod_empresa = v.COD_EMPRESA
            LEFT JOIN (
                SELECT 
                    ID_PROCESSO,
                    '[' || LISTAGG('{"categoria":"' || CATEGORIA || '","status":"' || status_categoria || '"}', ',') 
                        WITHIN GROUP (ORDER BY CATEGORIA) || ']' AS json_etapas
                FROM (
                    SELECT 
                        ID_PROCESSO, 
                        CATEGORIA,
                        CASE 
                            WHEN COUNT(CASE WHEN STATUS <> 'Autorizado' OR STATUS IS NULL THEN 1 END) = 0 
                            THEN 'Autorizado'
                            ELSE 'Pendente'
                        END AS status_categoria
                    FROM CAIUAS_VEIC_PROC_ETAPAS
                    WHERE ID_PROCESSO IS NOT NULL
                    GROUP BY ID_PROCESSO, CATEGORIA
                )
                GROUP BY ID_PROCESSO
            ) etapas 
                ON etapas.ID_PROCESSO = cvp.ID_PROCESSO
            WHERE v.status = 'V'
                AND TO_CHAR(v.cod_cliente) <> '22534303000127'
                AND TRUNC(vp.DATA_VENDA) >= TO_DATE('2026-09-01', 'YYYY-MM-DD')
                AND (cvp.REPASSE IS NULL OR cvp.REPASSE <> 'S')
                AND crv.created_at IS NOT null
                AND ea.DATA_BAIXA IS NULL
            ORDER BY pm.DESCRICAO_MODELO
        ) resultado
        -- WHERE ROWNUM <= 50  -- Defina o limite final aqui (offset + limit)
    )
"""

conn, cur = oracle()
cur.execute(query)
veiculos = cur.fetchall()
colunas = [desc[0] for desc in cur.description]

for veiculo in veiculos:
    dados = {coluna: ler_lob(valor) for coluna, valor in zip(colunas, veiculo)}
    cur.execute(f"""
        SELECT cvpe.nome_etapa, cvpe.AUTORIZADORES, cvpe.CATEGORIA
        FROM caiuas_veic_proc cvp
        LEFT JOIN CAIUAS_VEIC_PROC_ETAPAS cvpe ON 1=1
            AND cvpe.ID_PROCESSO = cvp.ID_PROCESSO
        WHERE 1=1
            AND cvp.COD_PROPOSTA = '{dados["COD_PROPOSTA"]}'
            AND cvpe.status IS null
    """)
    etapas = cur.fetchall()
    colunas_etapas = [desc[0] for desc in cur.description]

    logins = {
        login.strip()
        for etapa in etapas
        for login in (dict(zip(colunas_etapas, etapa))["AUTORIZADORES"] or "").split(",")
        if login.strip()
    }
    pessoas = {}
    if logins:
        lista = ", ".join(f"'{login.upper()}'" for login in logins)
        cur.execute(
            f"SELECT nome, nome_completo, email FROM empresas_usuarios WHERE UPPER(nome) IN ({lista})"
        )
        pessoas = {
            nome.upper(): (completo, email)
            for nome, completo, email in cur.fetchall()
        }

    blocos = []
    for etapa in etapas:
        etapa = dict(zip(colunas_etapas, etapa))
        aprovadores = ""
        for login in (etapa["AUTORIZADORES"] or "").split(","):
            login = login.strip()
            if login:
                nome_completo = pessoas.get(login.upper(), (login, None))[0]
                aprovadores += (
                    f"<div>{esc(nome_completo)} ({esc(login)})</div>"
                )
        blocos.append(
            '<div style="border:1px solid #e0e0e0;border-left:4px solid #cc0000;'
            'border-radius:4px;padding:10px 12px;margin:10px 0">'
            '<div style="font-weight:bold">Pode ser verificado por</div>'
            f"{aprovadores}"
            '<div style="margin-top:8px;color:#555">'
            f"{esc(etapa['CATEGORIA'])} - {esc(etapa['NOME_ETAPA'])}</div>"
            "</div>"
        )

    campo = (
        '<tr><td style="padding:4px 8px;color:#666">{rotulo}</td>'
        '<td style="padding:4px 8px;font-weight:bold">{valor}</td></tr>'
    )
    obs = (
        '<h3 style="font-size:16px;margin:18px 0 4px">{titulo}</h3>'
        '<div style="background:#f6f6f6;border-radius:4px;padding:8px 12px">{texto}</div>'
    )
    link = (
        "https://app.caiuas.com.br/veiculos/processos/"
        f'{esc(dados["ID_PROCESSO"])}'
    )

    corpo = f"""
<div style="font-family:Arial,Helvetica,sans-serif;color:#222;max-width:640px;margin:0 auto">
  <h1 style="color:#cc0000;font-size:24px;margin:0 0 16px">URGENTE! Veículo chegou</h1>
  <table style="border-collapse:collapse;width:100%;font-size:14px">
    {campo.format(rotulo="Responsável pela proposta", valor=esc(dados["NOME_VENDEDOR"]))}
    {campo.format(rotulo="Proposta", valor=esc(dados["COD_PROPOSTA"]))}
    {campo.format(rotulo="Faturada dia", valor=esc(dados["DATA_VENDA"]))}
    {campo.format(rotulo="Veículo", valor=esc(dados["MODELO"]))}
    {campo.format(rotulo="Cor", valor=esc(dados["COR"]))}
    {campo.format(rotulo="Chassi", valor=esc(dados["CHASSI_COMPLETO"]))}
    {campo.format(rotulo="CPF ou CNPJ", valor=esc(dados["COD_CLIENTE"]))}
    {campo.format(rotulo="Nome do cliente", valor=esc(dados["NOME_CLIENTE"]))}
    {campo.format(rotulo="Processo", valor=f'<a href="{link}">Abrir processo</a>')}
  </table>
  <p style="color:#cc0000;font-weight:bold;font-size:15px;margin:16px 0">
    Esse veículo foi recebido dia: {esc(dados["DATA_RECEBIMENTO"])}
  </p>
  <p style="font-size:14px;margin:0 0 8px">
    Por favor, esse veículo já recebido na concessionária, peço para que verifiquem dentro do
    processo do veículo se todos os arquivos e liberações estão em dia para que
    possamos agilizar o processo de entrega do veículo.
  </p>
  <p style="font-size:14px;margin:0 0 16px">
    É de suma importância que todas as liberações sejam feitas o mais rápido
    possível, pois esse veículo já foi faturado à {esc(dados["DIAS_EMISSAO"])} dias.
  </p>
  <p style="font-size:17px;font-weight:bold;color:#cc0000;margin:0 0 16px">
    Por favor, caso encontrem pendência de qualquer usuário, se comuniquem e
    mantenham o processo atualizado!
  </p>
  <h2 style="font-size:18px;margin:20px 0 4px">ETAPAS PENDENTES</h2>
  {''.join(blocos)}
  {obs.format(titulo="Última mensagem para liberação", texto=esc(dados["OBS_LIBERACAO"]))}
  {obs.format(titulo="Última mensagem para documentação", texto=esc(dados["OBS_DOCUMENTACAO"]))}
  {obs.format(titulo="Última mensagem para entrega", texto=esc(dados["OBS_ENTREGA"]))}
  {obs.format(titulo="Última mensagem para acessórios", texto=esc(dados["OBS_ACESSORIOS"]))}
</div>
"""

    destinatarios = [dados["EMAIL"]] if dados.get("EMAIL") else [SES_RECIPIENT]
    copia = sorted(
        {
            pessoas[login.upper()][1]
            for login in logins
            if pessoas.get(login.upper(), (None, None))[1]
        }
        | set(gestores)
    )
    copia = [email for email in copia if email not in destinatarios]

    resposta = send_email(
        f"Proposta {dados['COD_PROPOSTA']} - {dados['MODELO']}",
        corpo,
        destinatarios,
        copia,
    )
    print(dados["COD_PROPOSTA"], destinatarios, copia, resposta.status_code, resposta.text)
    