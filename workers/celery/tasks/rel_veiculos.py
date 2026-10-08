import calendar
import datetime
import html
import os
import sys
from pathlib import Path
import pandas as pd
import xlsxwriter
import requests
from requests_aws4auth import AWS4Auth

try:
    from database import oracle
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from database import oracle

conn, cur = oracle()

ano = 2026
mes = 10

# Veiculos Faturados

query = f"""
    SELECT
        pr.descricao_produto familia_veiculo,
        vp.cod_proposta,
        vp.cod_cliente,
        vp.EMISSAO data_proposta, 
        vp.VENDEDOR cod_vendedor, 
        eu.NOME_COMPLETO nome_vendedor, 
        eu.cod_empresa empresa_vendedor,
        pm.DESCRICAO_MODELO modelo, 
        COALESCE(ce.DESCRICAO, ce2.DESCRICAO) cor, 
        v.ANO_MODELO, 
        v.CHASSI_COMPLETO, 
        v.DATA_NOTA emissao,
        p.DESCRICAO patio,
        c.NOME nome_cliente,
        CASE 
            WHEN v.novo_usado = 'U' THEN 'Usado'
            WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
            ELSE
                'Novo'
        END novo_usado
    FROM veiculos v 
    LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
        --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
        AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
        AND vp.STATUS_PROPOSTA <> 'C'
    LEFT JOIN prop_ficticia_dados pfd ON 1=1
        AND pfd.COD_FICTICIO = vp.COD_FICTICIO
    LEFT JOIN produtos pr ON 1=1
        AND pr.COD_PRODUTO = v.COD_PRODUTO 
    LEFT JOIN CORES_EXTERNAS ce ON 1=1
        AND ce.COR_EXTERNA = v.COR_EXTERNA 
    LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
        AND ce2.COR_EXTERNA = pfd.COR_EXTERNA
    LEFT JOIN produtos_modelos pm ON 1=1
        AND pm.COD_PRODUTO = v.COD_PRODUTO 
        AND pm.COD_MODELO = v.COD_MODELO 
    LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
    LEFT JOIN patio p ON 1=1
        AND p.COD_PATIO = v.COD_PATIO
    LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
        AND eu.NOME = vp.VENDEDOR 
    LEFT JOIN empresas_usuarios eu2 ON 1=1
        AND eu2.nome = vp.QUEM_APROVOU 
    LEFT JOIN empresas e ON 1=1
        AND e.cod_empresa = v.COD_EMPRESA
    LEFT JOIN CLIENTES_FROTA cf ON 1=1
        AND cf.chassi = v.CHASSI_COMPLETO 
        AND cf.COD_CLIENTE = c.COD_CLIENTE  
        AND cf.nome = vp.VENDEDOR 
    LEFT JOIN cidades cid_res ON 1=1
        AND cid_res.cod_cidades = c.COD_CID_RES 
        AND cid_res.uf = c.UF_RES 
    LEFT JOIN cidades cid_com ON 1=1
        AND cid_com.cod_cidades = c.COD_CID_COM 
        AND cid_com.uf = c.UF_COM 
    LEFT JOIN cidades cid_cob ON 1=1
        AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
        AND cid_cob.uf = c.UF_COBRANCA 
    LEFT JOIN ev_agendados ea ON 1=1
        AND ea.STATUS NOT IN ('C')
        --AND ea.QUEM_CANCELOU IS NULL
        AND TO_CHAR(ea.COD_PROPOSTA) = TO_CHAR(vp.COD_PROPOSTA)
        AND TO_CHAR(ea.CHASSI_RESUMIDO) = TO_CHAR(v.CHASSI_RESUMIDO)
    left join EV_SALAS es on 1=1
        and es.cod_sala = ea.cod_sala
    left join caiuas_veic_proc cvp on 1=1
        and cvp.cod_proposta = vp.cod_proposta
    LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
        AND crv.cod_modelo = v.COD_MODELO 
        AND crv.cod_produto = v.COD_PRODUTO 
        AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
        AND crv.cod_empresa = v.COD_EMPRESA
    WHERE v.status = 'V'
        AND TO_CHAR(v.cod_cliente) <> '22534303000127'
        AND vp.VENDEDOR <> 'DIRETORIA'
        AND (cvp.REPASSE IS NULL OR cvp.REPASSE <> 'S')
        AND TRUNC(vp.data_venda ) >= TO_DATE('2026-10-01', 'YYYY-MM-DD')
      --  AND TRUNC(vp.data_venda ) <= TO_DATE('2026-09-30', 'YYYY-MM-DD')
"""
cur.execute(query)
result = cur.fetchall()
faturados = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

# Venda Estoque

query = f"""
        SELECT 
        pr.descricao_produto familia_veiculo,
                vp.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                eu.cod_empresa empresa_vendedor,
                pm.DESCRICAO_MODELO modelo, 
                ce.DESCRICAO cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                    ELSE
                        'Novo'
                END novo_usado,
                crv.quem_recebeu,
                crv.created_at data_recebimento
            FROM veiculos v 
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA 
            LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
                AND crv.cod_modelo = v.COD_MODELO 
                AND crv.cod_produto = v.COD_PRODUTO 
                AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                AND crv.cod_empresa = v.COD_EMPRESA
            WHERE v.status = 'E'
            ORDER BY pm.DESCRICAO_MODELO
"""
cur.execute(query)
result = cur.fetchall()
venda_estoque = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])
venda_estoque = venda_estoque[venda_estoque['EMPRESA'].isin(['CAMARGO - SOROCABA', 'INDMAR'])]
venda_estoque = venda_estoque[venda_estoque['NOVO_USADO'] == 'Novo']
venda_estoque = venda_estoque[venda_estoque['COD_PROPOSTA'].notnull()]

# Venda grade
query = f"""
    SELECT 
        pr.descricao_produto familia_veiculo,
                vp.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                eu.cod_empresa empresa_vendedor,
                pm.DESCRICAO_MODELO modelo, 
                COALESCE(ce.DESCRICAO, ce2.DESCRICAO) cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                    ELSE
                        'Novo'
                END novo_usado,
                COALESCE(cid_com.DESCRICAO, cid_res.DESCRICAO, cid_cob.DESCRICAO) cidade,
                cvp.ID_PROCESSO,
                cvp.status,
                vp.DATA_VENDA,
                ea.DATA_AGENDADA,
                ea.DATA_BAIXA,
                cvp.OBS_FATURAMENTO,
                cvp.OBS_ENTREGA,
                cvp.OBS_LIBERACAO,
                cvp.OBS_DOCUMENTACAO,
                cvp.REPASSE,
                NVL(etapas.json_etapas, '[]') AS status_processo_etapas,
                ea.local_entrega,
                cvp.OBS_ISENCAO,
                cvp.OBS_ACESSORIOS,
                cvp.DATA_SOLICITACAO,
                crv.quem_recebeu,
                crv.created_at data_recebimento,
                vp2.NUMERO_FABRICA pedido_fabrica,
                vp.COD_EMPRESA cod_empresa
            FROM VEICULOS_PROPOSTAS vp
            LEFT JOIN veiculos v ON 1=1
                AND v.CHASSI_RESUMIDO = vp.CHASSI_RESUMIDO 
                AND v.STATUS = 'E'
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = vp.COD_PRODUTO 
            LEFT JOIN prop_ficticia_dados pfd ON 1=1
                AND pfd.COD_FICTICIO = vp.COD_FICTICIO
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
                AND ce2.COR_EXTERNA = pfd.COR_EXTERNA
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = vp.COD_PRODUTO 
                AND pm.COD_MODELO = vp.COD_MODELO 
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA 
            LEFT JOIN cidades cid_res ON 1=1
                AND cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON 1=1
                AND cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON 1=1
                AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            LEFT JOIN (
                SELECT
                    ea.COD_PROPOSTA,
                    MAX(ea.DATA_AGENDADA) DATA_AGENDADA,
                    MAX(ea.DATA_BAIXA) DATA_BAIXA,
                    MAX(es.DESCRICAO_SALA) local_entrega
                FROM EV_AGENDADOS ea
                LEFT JOIN EV_SALAS es ON 1=1
                    AND es.cod_sala = ea.COD_SALA
                WHERE ea.STATUS <> 'C'
                GROUP BY ea.COD_PROPOSTA
            ) ea ON 1=1
                AND ea.COD_PROPOSTA = vp.COD_PROPOSTA
            left join caiuas_veic_proc cvp on 1=1
                and cvp.cod_proposta = vp.cod_proposta
            LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
                AND crv.cod_modelo = v.COD_MODELO 
                AND crv.cod_produto = v.COD_PRODUTO 
                AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                AND crv.cod_empresa = v.COD_EMPRESA
            LEFT JOIN veiculos_pedidos vp2 ON 1=1
                AND vp2.cod_pedido = vp.cod_pedido
            LEFT JOIN (
                SELECT
                    ID_PROCESSO,
                    '[' || LISTAGG('{{"categoria":"' || CATEGORIA || '","status":"' || status_categoria || '"}}', ',')
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
            ) etapas ON 1=1
                AND etapas.ID_PROCESSO = cvp.ID_PROCESSO
            WHERE vp.STATUS_PROPOSTA NOT IN ('C','V')
                AND TRUNC(vp.EMISSAO ) >= TO_DATE('2024-01-01', 'YYYY-MM-DD')
            ORDER BY CASE WHEN v.CHASSI_COMPLETO IS NOT NULL THEN 0 ELSE 1 END,
            cvp.DATA_SOLICITACAO,vp.EMISSAO DESC
"""

cur.execute(query)
result = cur.fetchall()
venda_grade = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])
# apenas o que tem pedido_fabrica diferente de null
venda_grade = venda_grade[venda_grade['PEDIDO_FABRICA'].notnull()]


# une os dois dataframes
todos = pd.concat([faturados, venda_grade, venda_estoque], ignore_index=True)

varejo = todos[todos['NOVO_USADO'] == 'Novo']
vd = todos[todos['NOVO_USADO'] == 'Direta']
# LX = todo que contem " LX" no modelo
LX = todos[todos['MODELO'].str.contains(" LX", na=False)]
# remove todos os LX de todos
# todos = todos[~todos['MODELO'].str.contains(" LX", na=False)]
# renomeia familia LX para LX
todos.loc[todos['MODELO'].str.contains(" LX", na=False), 'FAMILIA_VEICULO'] = 'LX'
# remove 'AUTO-' do iniicio do nome do modelo
todos['MODELO'] = todos['MODELO'].str.replace('AUTO - ', '', regex=False)

# formatação
col_familia = next((c for c in todos.columns if c.lower() == 'familia_veiculo'), None)
todos[col_familia] = todos[col_familia].apply(
    lambda x: x.split('-')[1].strip() if isinstance(x, str) and len(x.split('-')) > 1 else x
)

Sorocaba = todos[todos['EMPRESA_VENDEDOR'] == 11]
Indaiatuba = todos[todos['EMPRESA_VENDEDOR'] == 33]

# Agrupa onde a linha é a familia e coluna é novo_usado e soma a quantidade (LX primeiro, demais em ordem alfabética)
ordem_familias = lambda df: sorted(df.index, key=lambda x: (x != 'LX', str(x)))

fechamento_sorocaba = Sorocaba.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
fechamento_sorocaba = fechamento_sorocaba.reindex(ordem_familias(fechamento_sorocaba))

fechamento_indaiatuba = Indaiatuba.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
fechamento_indaiatuba = fechamento_indaiatuba.reindex(ordem_familias(fechamento_indaiatuba))

# remove todos os veiculos que não estão em nenhum dos dois dataframes
todos = todos[todos['FAMILIA_VEICULO'].isin(fechamento_sorocaba.index) | todos['FAMILIA_VEICULO'].isin(fechamento_indaiatuba.index)]
# Agrupa onde a linha é a familia e coluna é novo_usado e soma a quantidade (LX primeiro, demais em ordem alfabética)
fechamento_geral = todos.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
fechamento_geral = fechamento_geral.reindex(ordem_familias(fechamento_geral))

query = f"""
    SELECT nome COD_VENDEDOR, sum(qtd) qtd_meta
    FROM caiuas_comissoes_vendedores
    WHERE 1=1
    AND EXTRACT(YEAR FROM data) = {ano}
    AND EXTRACT(month FROM data) = {mes}
    GROUP BY nome
"""
cur.execute(query)
result = cur.fetchall()
meta = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

# agrupa por vendedor e sua meta que é o que está em comissao
fechamento_vendedores = pd.pivot_table(todos, index=['EMPRESA_VENDEDOR','COD_VENDEDOR','NOME_VENDEDOR'], aggfunc='size').reset_index()
fechamento_vendedores.columns = ['EMPRESA_VENDEDOR','COD_VENDEDOR','NOME_VENDEDOR', 'Total']
fechamento_vendedores = pd.merge(fechamento_vendedores, meta, left_on='COD_VENDEDOR', right_on='COD_VENDEDOR', how='left').fillna(0)
fechamento_vendedores['% Meta'] = (fechamento_vendedores['Total'] / fechamento_vendedores['QTD_META']) * 100
fechamento_vendedores['% Meta'] = fechamento_vendedores['% Meta'].round(2)

# soma total de faturados e qtd_comissao
fechamento_empresa = pd.pivot_table(fechamento_vendedores, index='EMPRESA_VENDEDOR', values=['Total', 'QTD_META'], aggfunc='sum').reset_index()
fechamento_empresa['% Meta'] = (fechamento_empresa['Total'] / fechamento_empresa['QTD_META']) * 100
fechamento_empresa['% Meta'] = fechamento_empresa['% Meta'].round(2)

# renomeia empresa_vendedor de 11 para Sorocaba e 33 para Indaiatuba
fechamento_empresa = fechamento_empresa.replace({'EMPRESA_VENDEDOR': {11: 'Sorocaba', 33: 'Indaiatuba'}})
# print(fechamento_empresa)
# print(fechamento_vendedores)

# apenas os veiculos que possuem cod_cliente repetido
col_cliente = next((c for c in todos.columns if c.lower() == 'cod_cliente'), None)
clientes_repetidos = todos.dropna(subset=[col_cliente])
clientes_repetidos = clientes_repetidos[clientes_repetidos.duplicated(subset=[col_cliente], keep=False)]
clientes_repetidos = clientes_repetidos.sort_values(by=col_cliente)

# quantidade de veiculos por modelo (varejo x venda direta)
col_modelo = next((c for c in todos.columns if c.lower() == 'familia_veiculo'), None)
col_novo_usado = next((c for c in todos.columns if c.lower() == 'novo_usado'), None)

query = f"""
    SELECT 
    TO_CHAR(TRUNC(f.DATA), 'YYYY-MM-DD') AS ano_mes,
	TRUNC(f.DATA)                     AS data_feriado,
	LISTAGG(f.MOTIVO, ', ') WITHIN GROUP (ORDER BY f.MOTIVO) AS motivos
FROM feriado f
WHERE 1=1
	AND EXTRACT(YEAR FROM data) = {ano}
	AND EXTRACT(month FROM data) = {mes}
GROUP BY
    TO_CHAR(TRUNC(f.DATA), 'YYYY-MM-DD'),
    TRUNC(f.DATA)
ORDER BY 
    data_feriado
"""

cur.execute(query)
result = cur.fetchall()
feriados = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

# quantidade de dias do mês
qtd_dias_mes = calendar.monthrange(ano, mes)[1]

# dias do mês que caem no domingo
qtd_domingos = sum(
    1
    for dia in range(1, qtd_dias_mes + 1)
    if datetime.date(ano, mes, dia).weekday() == calendar.SUNDAY
)

# feriados que caem em dia útil (não domingo), para não descontar duas vezes
col_feriado = next((c for c in feriados.columns if c.lower() == 'data_feriado'), None)
qtd_feriados_uteis = 0
if col_feriado is not None:
    for data_feriado in feriados[col_feriado]:
        if pd.notna(data_feriado) and pd.Timestamp(data_feriado).weekday() != calendar.SUNDAY:
            qtd_feriados_uteis += 1

qtd_dias_uteis = qtd_dias_mes - qtd_domingos - qtd_feriados_uteis
print(qtd_dias_uteis)

# dias úteis de hoje até o último dia do mês
hoje = datetime.date.today()
primeiro_dia = datetime.date(ano, mes, 1)
ultimo_dia = datetime.date(ano, mes, qtd_dias_mes)

datas_feriado = set()
if col_feriado is not None:
    datas_feriado = {
        pd.Timestamp(data_feriado).date()
        for data_feriado in feriados[col_feriado]
        if pd.notna(data_feriado)
    }

if hoje > ultimo_dia:
    qtd_dias_uteis_restantes = 0
else:
    dia_inicio = max(primeiro_dia, hoje).day
    qtd_dias_uteis_restantes = sum(
        1
        for dia in range(dia_inicio, qtd_dias_mes + 1)
        if datetime.date(ano, mes, dia).weekday() != calendar.SUNDAY
        and datetime.date(ano, mes, dia) not in datas_feriado
    )

print(qtd_dias_uteis_restantes)

# meta proporcional aos dias úteis já decorridos e quanto falta para bater a meta do mês
dias_uteis_decorridos = qtd_dias_uteis - qtd_dias_uteis_restantes

if qtd_dias_uteis > 0:
    fechamento_empresa['Meta até agora'] = (
        fechamento_empresa['QTD_META'] * (dias_uteis_decorridos / qtd_dias_uteis)
    ).round(2)
else:
    fechamento_empresa['Meta até agora'] = 0

fechamento_empresa['Faltam p/ fim do mês'] = (
    fechamento_empresa['QTD_META'] - fechamento_empresa['Total']
).round(2)

if qtd_dias_uteis_restantes > 0:
    fechamento_empresa['Meta por dia'] = (
        fechamento_empresa['Faltam p/ fim do mês'] / qtd_dias_uteis_restantes
    ).round(2)
else:
    fechamento_empresa['Meta por dia'] = 0

print(fechamento_empresa)

# passagens e retornos por empresa (baseado em streamlit_app/views/fluxo_de_loja.py)
# passagens do mês são contabilizadas até o dia anterior (não inclui hoje)
dia_anterior = min(hoje - datetime.timedelta(days=1), ultimo_dia)

if dia_anterior < primeiro_dia:
    dia_anterior = None

tipos_passagens = "785, 807"
tipos_visitas = "819, 821, 815, 817, 810, 812, 829, 795, 793, 797, 799, 837"
tipos_retornos = "819, 821, 815, 817, 810, 812, 829, 795, 793, 797, 799, 837"

if dia_anterior is not None:
    primeiro_dia_sql = primeiro_dia.strftime('%Y-%m-%d')
    dia_fim_sql = dia_anterior.strftime('%Y-%m-%d')
    dia_anterior_sql = dia_anterior.strftime('%Y-%m-%d')

    query = f"""
        SELECT empresa,
            COUNT(CASE WHEN data_passagem = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD') THEN 1 END) passagens_dia_anterior,
            COUNT(*) passagens_mes,
            SUM(tem_test_drive) test_drives,
            SUM(CASE WHEN data_passagem = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD') THEN tem_test_drive ELSE 0 END) test_drives_dia_anterior
        FROM (
            SELECT eu.cod_empresa empresa, TRUNC(ce.data_criacao) data_passagem,
                CASE WHEN EXISTS (
                    SELECT 1 FROM caiuas_crm_test_drive cctd
                    WHERE cctd.cod_empresa = ce.cod_empresa
                      AND cctd.cod_evento = ce.cod_evento
                ) THEN 1 ELSE 0 END tem_test_drive
            FROM crm_eventos ce
            LEFT JOIN empresas_usuarios eu ON 1=1
                AND eu.nome = ce.responsavel_pelo_evento
            WHERE ce.cod_tipo_evento IN ({tipos_passagens})
              AND ce.status <> 'D'
              AND eu.cod_empresa IN (11, 33)
              AND TRUNC(ce.data_criacao) BETWEEN TO_DATE('{primeiro_dia_sql}', 'YYYY-MM-DD') AND TO_DATE('{dia_fim_sql}', 'YYYY-MM-DD')
            UNION ALL
            SELECT eu.cod_empresa empresa, TRUNC(ce.data_visita) data_passagem,
                CASE WHEN EXISTS (
                    SELECT 1 FROM caiuas_crm_test_drive cctd
                    WHERE cctd.cod_empresa = ce.cod_empresa
                      AND cctd.cod_evento = ce.cod_evento
                ) THEN 1 ELSE 0 END tem_test_drive
            FROM crm_eventos ce
            LEFT JOIN empresas_usuarios eu ON 1=1
                AND eu.nome = ce.responsavel_pelo_evento
            WHERE ce.cod_tipo_evento IN ({tipos_visitas})
              AND ce.status <> 'D'
              AND eu.cod_empresa IN (11, 33)
              AND TRUNC(ce.data_visita) BETWEEN TO_DATE('{primeiro_dia_sql}', 'YYYY-MM-DD') AND TO_DATE('{dia_fim_sql}', 'YYYY-MM-DD')
        )
        GROUP BY empresa
    """
    cur.execute(query)
    result = cur.fetchall()
    passagens = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

    query = f"""
        SELECT ccr.cod_empresa empresa, COUNT(*) retornos_dia_anterior
        FROM caiuas_crm_retorno ccr
        LEFT JOIN crm_eventos ce ON 1=1
            AND ce.cod_evento = ccr.cod_evento
            AND ce.cod_empresa = ccr.cod_empresa
        WHERE ce.status <> 'D'
          AND ce.cod_tipo_evento IN ({tipos_retornos})
          AND ccr.cod_empresa IN (11, 33)
          AND TRUNC(ccr.created_at) = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD')
        GROUP BY ccr.cod_empresa
    """
    cur.execute(query)
    result = cur.fetchall()
    retornos = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

    passagens = pd.merge(passagens, retornos, on='EMPRESA', how='outer')

    dias_uteis_ate_atual = sum(
        1
        for dia in range(1, dia_anterior.day + 1)
        if datetime.date(ano, mes, dia).weekday() != calendar.SUNDAY
        and datetime.date(ano, mes, dia) not in datas_feriado
    )

    if dias_uteis_ate_atual > 0:
        passagens['Média passagens/dia'] = (
            passagens['PASSAGENS_MES'] / dias_uteis_ate_atual
        ).round(2)
    else:
        passagens['Média passagens/dia'] = 0

    passagens = passagens.fillna(0)
    passagens['EMPRESA'] = passagens['EMPRESA'].replace({11: 'Sorocaba', 33: 'Indaiatuba'})
    passagens = passagens.rename(columns={
        'EMPRESA': 'Empresa',
        'PASSAGENS_DIA_ANTERIOR': 'Passagens dia anterior',
        'RETORNOS_DIA_ANTERIOR': 'Retornos dia anterior',
        'PASSAGENS_MES': 'Passagens no mês',
        'TEST_DRIVES': 'Test drives',
        'TEST_DRIVES_DIA_ANTERIOR': 'Test drives dia anterior',
    })
else:
    passagens = pd.DataFrame(columns=[
        'Empresa', 'Passagens dia anterior', 'Retornos dia anterior', 'Passagens no mês', 'Test drives', 'Test drives dia anterior', 'Média passagens/dia'
    ])

print(passagens)

cur.close()
conn.close()
# faça uma tabela com a meta x qtd vendida por empresa
# meta_empresa = pd.pivot_table(todos, values='COD_PROPOSTA', index='EMPRESA_VENDEDOR', columns='NOVO_USADO', aggfunc='count')


with pd.ExcelWriter('rel_veiculos.xlsx', engine='xlsxwriter') as writer:
    meta.to_excel(writer, sheet_name='Meta')
    fechamento_vendedores.to_excel(writer, sheet_name='Fechamento Vendedores')
    fechamento_geral.to_excel(writer, sheet_name='Fechamento Geral')
    fechamento_sorocaba.to_excel(writer, sheet_name='Fechamento Sorocaba')
    fechamento_indaiatuba.to_excel(writer, sheet_name='Fechamento Indaiatuba')
    faturados.to_excel(writer, sheet_name='Faturados')
    venda_estoque.to_excel(writer, sheet_name='Venda_estoque')
    venda_grade.to_excel(writer, sheet_name='Venda_grade')
    varejo.to_excel(writer, sheet_name='Varejo')
    vd.to_excel(writer, sheet_name='VD')
    LX.to_excel(writer, sheet_name='LX')
    todos.to_excel(writer, sheet_name='Todos')
    clientes_repetidos.to_excel(writer, sheet_name='Clientes Repetidos')
    passagens.to_excel(writer, sheet_name='Passagens')
   