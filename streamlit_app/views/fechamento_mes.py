import streamlit as st
from database import oracle
from datetime import datetime
import calendar
import pandas as pd

EMAILS_FECHAMENTO_MES = [
    "pablo.ti@caiuas.com.br",
    "marcelotcf@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br"
]

def get_dados_propostas(primeiro_dia, ultimo_dia):
    query_abertos = f"""
        SELECT 
            to_char(vp.COD_PROPOSTA) COD_PROPOSTA
        FROM VEICULOS_PROPOSTAS vp 
        LEFT JOIN VEICULOS v ON 1=1
            AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
            AND vp.COD_PRODUTO = v.COD_PRODUTO      
            AND vp.COD_MODELO = v.COD_MODELO        
            AND vp.cod_empresa = v.cod_empresa      
            AND v.status = 'E' 
        WHERE 1=1
            AND vp.status_proposta = 'A'
            AND TRUNC(vp.EMISSAO) BETWEEN TO_DATE('{primeiro_dia}', 'YYYY-MM-DD') AND TO_DATE('{ultimo_dia}', 'YYYY-MM-DD')
    """
    
    query_faturados = f"""
        select 1
          from veiculos    a,
               produtos    b,
               ponto_venda p,
               produtos_modelos pm
         where a.cod_produto = b.cod_produto
           and a.status = 'V'
           and a.cod_ponto_venda = p.cod_ponto_venda(+)
           and a.cod_produto  = pm.cod_produto
           and a.cod_modelo   = pm.cod_modelo
           and a.data_venda >= TO_DATE('{primeiro_dia}', 'YYYY-MM-DD')
           and a.data_venda <= TO_DATE('{ultimo_dia}', 'YYYY-MM-DD')
         AND a.COD_EMPRESA_vendedora  in (                  
                          SELECT DISTINCT UE1.COD_EMPRESA   
           FROM CRUZAMENTO_USUARIO_EMPRESAS UE1             
            LEFT JOIN EMPRESAS E3 ON (E3.COD_EMPRESA = UE1.COD_EMPRESA) 
         WHERE UE1.USUARIO = 'NBS'                                   
         AND  E3.COD_MATRIZ > 0                                         
          ) 
        AND( (decode( nvl(a.internet,'K'),'I','OK', 'K', decode(a.extra,'F', 'OK','NAO') )) = 'OK'     
        or (  (nvl(a.extra,'.') <> '0')  and  
              (nvl(a.extra,'.') <> 'F')  and   
              (nvl(a.extra,'.') <> 'X')  AND   
              (a.NOVO_USADO        = 'N')        
           ) 
        or (a.INTERNET ='F')                      
              )  
        AND a.COD_EMPRESA_vendedora in  (select x.cod_empresa                       
        from Gp_Veiculo_empresa x,Regiao_Veiculo_grupo y                            
        where x.cod_grupo = y.cod_grupo  and   y.cod_regiao = 1  )        
        AND a.COD_EMPRESA_vendedora in (select cod_empresa from Gp_Veiculo_empresa where cod_grupo = 1) 
    """
    
    query_total = f"""
        SELECT 
            to_char(vp.COD_PROPOSTA) COD_PROPOSTA
        FROM VEICULOS_PROPOSTAS vp 
        WHERE TRUNC(vp.EMISSAO) BETWEEN TO_DATE('{primeiro_dia}', 'YYYY-MM-DD') AND TO_DATE('{ultimo_dia}', 'YYYY-MM-DD')
    """

    conn_oracle, cur_oracle = oracle()
    
    cur_oracle.execute(query_abertos)
    abertos = len(cur_oracle.fetchall())
    
    cur_oracle.execute(query_faturados)
    faturados = len(cur_oracle.fetchall())
    
    cur_oracle.execute(query_total)
    total = len(cur_oracle.fetchall())
    
    cur_oracle.close()
    conn_oracle.close()
    
    return total, faturados, abertos

def get_propostas_faturadas(primeiro_dia, ultimo_dia):
    query = f"""
        SELECT DISTINCT
            to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
            to_char(eu.cod_empresa) COD_EMPRESA_VENDEDOR
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = vp.vendedor
        JOIN VEICULOS v ON 1=1
            AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
            AND vp.COD_PRODUTO = v.COD_PRODUTO
            AND vp.COD_MODELO = v.COD_MODELO
            AND vp.cod_empresa = v.cod_empresa
        WHERE 1=1
            AND v.status = 'V'
            AND trunc(v.data_venda) BETWEEN TO_DATE('{primeiro_dia}', 'YYYY-MM-DD') AND TO_DATE('{ultimo_dia}', 'YYYY-MM-DD')
    """
    conn_oracle, cur_oracle = oracle()
    cur_oracle.execute(query)
    result = cur_oracle.fetchall()
    cur_oracle.close()
    conn_oracle.close()
    return {(row[0], row[1] or '') for row in result if row[0] is not None}

def get_dados_mes(primeiro_dia, ultimo_dia):
    query = f"""
    SELECT 
        ce.COD_EMPRESA, 
        ce.COD_EVENTO,
        to_char(ce.cod_proposta) as cod_proposta,
        eu2.NOME_COMPLETO quem_criou,
        eu.NOME_COMPLETO resp_atual,
        to_char(eu.cod_empresa) cod_empresa_resp,
        case
            when ce.cod_empresa = 11 AND eu.nome NOT IN ('KAYLANY','STEF_HS') then 'Sorocaba'
            when ce.cod_empresa = 33 then 'Indaiatuba'
            WHEN eu.nome = 'KAYLANY' THEN 'Aquecimento'
            WHEN eu.nome = 'STEF_HS' THEN 'Aquecimento'
        end empresa,
        ce.STATUS, 
        cet.DESC_TIPO_EVENTO, 
        m.DESCRICAO midia,
        ca.ANDAMENTO, 
        cd.DESCRICAO_DESCARTE, 
        cmp.desc_motivo as motivo_contato_perdido,
        cct.tag, 
        ce.OBS_MEMO,
        to_date(ce.data_criacao) data_criacao,
        to_date(ce.data_encerramento) data_encerramento,
        (
        	SELECT to_DATE(max(ca.DATA)) FROM CRM_ACOES ca 
    			WHERE 1=1
        	AND ca.COD_EVENTO = ce.COD_EVENTO 
        	AND ca.cod_empresa = ce.cod_empresa
        	AND observacao LIKE ('Responsável pelo evento alterado para%')
        	) data_transferencia,
        to_date(ce.DATA_AGENDADA ) data_agendada,
        (
    SELECT MAX(ca_resp.RESPONSAVEL) KEEP (DENSE_RANK LAST ORDER BY ca_resp.DATA)
    FROM CRM_ACOES ca_resp
    WHERE ca_resp.COD_EVENTO = ce.COD_EVENTO
      AND ca_resp.COD_EMPRESA = ce.COD_EMPRESA
      AND ca_resp.TIPO_ACAO = 12
      AND ca_resp.OBSERVACAO LIKE 'Agendamento marcado%'
    ) responsavel_agendamento,
    (
    SELECT MIN(ca_resp.RESPONSAVEL) KEEP (DENSE_RANK LAST ORDER BY ca_resp.DATA desc)
    FROM CRM_ACOES ca_resp
    WHERE ca_resp.COD_EVENTO = ce.COD_EVENTO
      AND ca_resp.COD_EMPRESA = ce.COD_EMPRESA
      AND ca_resp.TIPO_ACAO = 12
      AND ca_resp.OBSERVACAO LIKE 'Agendamento marcado%'
    ) resp_prim_agendamento,
        to_date(ce.data_visita ) data_visita,
        ce.COD_EMPRESA_ANTERIOR, 
        ce.COD_EVENTO_ANTERIOR
    FROM CRM_EVENTOS ce
    LEFT JOIN EMPRESAS_USUARIOS eu ON
        1 = 1
        AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
    LEFT JOIN empresas_usuarios eu2 ON 1=1
    	AND eu2.nome = ce.criou_o_evento
    LEFT JOIN CRM_ANDAMENTO ca ON
        1 = 1
        AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
    LEFT JOIN MIDIA m ON
        1=1
        AND m.COD_MIDIA = ce.COD_MIDIA 
    LEFT JOIN clientes c ON
        1 = 1
        AND ce.COD_CLIENTE = c.COD_CLIENTE
    LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
        AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
    LEFT JOIN CRM_DESCARTES cd on 1=1
        and cd.COD_DESCARTE = ce.COD_DESCARTE
    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
        AND cmp.cod_motivo_perda = ce.cod_motivo_perda
    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
    LEFT JOIN caiuas_crm_tags cct ON 1=1
        AND cct.cod_empresa = ce.COD_EMPRESA 
        AND cct.cod_evento = ce.cod_evento
    LEFT JOIN crm_eventos cev ON 1=1
    	AND cev.COD_EVENTO = ce.COD_EVENTO_ANTERIOR 
    	AND cev.COD_EMPRESA = ce.COD_EMPRESA_ANTERIOR 
    WHERE 1=1
        AND ce.cod_tipo_evento in ('829','831','795','793','797','799','819','821','785','807','815','817','810','812')
        AND trunc(ce.DATA_CRIACAO) >= TO_DATE('{primeiro_dia}', 'YYYY-MM-DD')
        AND trunc(ce.DATA_CRIACAO) <= TO_DATE('{ultimo_dia}', 'YYYY-MM-DD')
    """
    conn_oracle, cur_oracle = oracle()
    cur_oracle.execute(query)
    result_oracle = cur_oracle.fetchall()
    columns = [desc[0] for desc in cur_oracle.description]
    df = pd.DataFrame(result_oracle, columns=columns, dtype=str)
    df = df.fillna('')
    cur_oracle.close()
    conn_oracle.close()
    return df

def get_arrow(val_ant, val_atual):
    if val_atual > val_ant:
        return "↑"
    elif val_atual < val_ant:
        return "↓"
    else:
        return "="

def render():
    st.title("Fechamento por Mês")
    
    # Month/Year selectors
    col_ano, col_mes = st.columns(2)
    anos = [2023, 2024, 2025, 2026, 2027]
    meses = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    with col_ano:
        ano_selecionado = st.selectbox("Ano", anos, index=anos.index(datetime.now().year) if datetime.now().year in anos else len(anos)-1)
    
    with col_mes:
        mes_atual = datetime.now().month
        mes_selecionado_nome = st.selectbox("Mês", list(meses.values()), index=mes_atual - 1)
        mes_selecionado = [k for k, v in meses.items() if v == mes_selecionado_nome][0]
    
    # Calculate initial and final date
    primeiro_dia = datetime(ano_selecionado, mes_selecionado, 1).strftime('%Y-%m-%d')
    ultimo_dia_mes = calendar.monthrange(ano_selecionado, mes_selecionado)[1]
    ultimo_dia = datetime(ano_selecionado, mes_selecionado, ultimo_dia_mes).strftime('%Y-%m-%d')
    
    # Mês anterior
    if mes_selecionado == 1:
        mes_ant = 12
        ano_ant = ano_selecionado - 1
    else:
        mes_ant = mes_selecionado - 1
        ano_ant = ano_selecionado
        
    mes_ant_nome = meses[mes_ant]
    primeiro_dia_ant = datetime(ano_ant, mes_ant, 1).strftime('%Y-%m-%d')
    ultimo_dia_mes_ant = calendar.monthrange(ano_ant, mes_ant)[1]
    ultimo_dia_ant = datetime(ano_ant, mes_ant, ultimo_dia_mes_ant).strftime('%Y-%m-%d')
    
    with st.spinner("Carregando dados do banco de dados..."):
        df_atual = get_dados_mes(primeiro_dia, ultimo_dia)
        df_ant = get_dados_mes(primeiro_dia_ant, ultimo_dia_ant)

        # Propostas
        tot_prop_atual, fat_atual, a_fat_atual = get_dados_propostas(primeiro_dia, ultimo_dia)
        tot_prop_ant, fat_ant, a_fat_ant = get_dados_propostas(primeiro_dia_ant, ultimo_dia_ant)

        propostas_faturadas = get_propostas_faturadas(primeiro_dia, ultimo_dia)

    # Calculos Mes Atual
    total_leads_atual = len(df_atual)
    agendados_atual = len(df_atual[df_atual['DATA_AGENDADA'] != ''])
    compareceram_atual = len(df_atual[df_atual['DATA_VISITA'] != ''])
    nao_compareceram_atual = agendados_atual - compareceram_atual
    
    # Calculos Mes Anterior
    total_leads_ant = len(df_ant)
    agendados_ant = len(df_ant[df_ant['DATA_AGENDADA'] != ''])
    compareceram_ant = len(df_ant[df_ant['DATA_VISITA'] != ''])
    nao_compareceram_ant = agendados_ant - compareceram_ant

    st.subheader(f"Performance Geral - {mes_selecionado_nome.upper()}")
    
    col_ant = mes_ant_nome[:3].upper()
    col_atual = mes_selecionado_nome[:3].upper()
    
    # Create the dataframe for display
    data_tabela = [
        {"Indicador": "Total leads do mês", col_ant: total_leads_ant, col_atual: total_leads_atual, "Evolução": get_arrow(total_leads_ant, total_leads_atual)},
        {"Indicador": "Agendados", col_ant: agendados_ant, col_atual: agendados_atual, "Evolução": get_arrow(agendados_ant, agendados_atual)},
        {"Indicador": "Compareceram", col_ant: compareceram_ant, col_atual: compareceram_atual, "Evolução": get_arrow(compareceram_ant, compareceram_atual)},
        {"Indicador": "Não compareceram", col_ant: nao_compareceram_ant, col_atual: nao_compareceram_atual, "Evolução": get_arrow(nao_compareceram_ant, nao_compareceram_atual)},
        {"Indicador": "Total propostas do mês", col_ant: tot_prop_ant, col_atual: tot_prop_atual, "Evolução": get_arrow(tot_prop_ant, tot_prop_atual)},
        {"Indicador": "Faturados do mês", col_ant: fat_ant, col_atual: fat_atual, "Evolução": get_arrow(fat_ant, fat_atual)},
        {"Indicador": "Faturados do mês anterior", col_ant: 0, col_atual: fat_ant, "Evolução": get_arrow(0, fat_ant)},
        {"Indicador": "A faturar", col_ant: a_fat_ant, col_atual: a_fat_atual, "Evolução": get_arrow(a_fat_ant, a_fat_atual)},
    ]
    
    df_indicadores = pd.DataFrame(data_tabela)
    
    # Make a bold style for the "Total leads do mês" and colors for arrows
    def style_dataframe(row):
        styles = [''] * len(row)
        if row.name == 0:
            styles = ['color: red; font-weight: bold'] * len(row)
            
        # Overwrite color for Evolução column
        evolucao_idx = row.index.get_loc('Evolução')
        val = row['Evolução']
        if val == '↑':
            styles[evolucao_idx] = 'color: green; font-weight: bold; font-size: 18px;'
        elif val == '↓':
            styles[evolucao_idx] = 'color: red; font-weight: bold; font-size: 18px;'
        elif val == '=':
            styles[evolucao_idx] = 'color: orange; font-weight: bold; font-size: 18px;'
            
        return styles

    st.dataframe(df_indicadores.style.apply(style_dataframe, axis=1), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Leads por Vendedor - {mes_selecionado_nome.upper()}")

    empresa_map = {'11': 'Sorocaba', '33': 'Indaiatuba', '111': 'LLA'}

    df_vend = df_atual[df_atual['RESP_ATUAL'] != ''].copy()
    df_vend['EMPRESA'] = df_vend['COD_EMPRESA_RESP'].map(empresa_map).fillna('')
    df_vend['IS_AGENDADO'] = (df_vend['DATA_AGENDADA'] != '').astype(int)
    df_vend['IS_VISITA'] = (df_vend['DATA_VISITA'] != '').astype(int)
    df_vend['IS_FATURADO'] = [
        1 if (cp, ce) in propostas_faturadas else 0
        for cp, ce in zip(df_vend['COD_PROPOSTA'], df_vend['COD_EMPRESA_RESP'])
    ]

    resumo_vend = df_vend.groupby(['EMPRESA', 'RESP_ATUAL']).agg(
        Leads=('RESP_ATUAL', 'count'),
        Agendados=('IS_AGENDADO', 'sum'),
        Visitas=('IS_VISITA', 'sum'),
        Faturados=('IS_FATURADO', 'sum'),
    ).reset_index().rename(columns={'RESP_ATUAL': 'Responsável', 'EMPRESA': 'Empresa'})

    # Adicionando a nova coluna "Percentual sucesso" com formatação em % e proteção contra divisão por zero
    resumo_vend['Percentual sucesso'] = resumo_vend.apply(
        lambda row: f"{(row['Faturados'] / row['Visitas'] * 100):.2f}%" if row['Visitas'] > 0 else "0.00%", 
        axis=1
    )

    resumo_vend = resumo_vend.sort_values('Leads', ascending=False)

    st.dataframe(resumo_vend, hide_index=True, use_container_width=True)