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

def get_dados_propostas(primeiro_dia, ultimo_dia, cod_empresa=None):
    # Filtro de empresa na proposta usa a empresa da unidade (loja)
    filtro_vp_empresa = f"AND vp.cod_empresa = '{cod_empresa}'" if cod_empresa else ""
    filtro_a_empresa = f"AND a.COD_EMPRESA_vendedora = '{cod_empresa}'" if cod_empresa else ""
    
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
            {filtro_vp_empresa}
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
           {filtro_a_empresa}
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
        {filtro_vp_empresa}
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
        to_char(ce.COD_EMPRESA) COD_EMPRESA, 
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
        to_date(ce.DATA_AGENDADA ) data_agendada,
        to_date(ce.data_visita ) data_visita
    FROM CRM_EVENTOS ce
    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
    LEFT JOIN empresas_usuarios eu2 ON eu2.nome = ce.criou_o_evento
    LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
    LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
    LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
    LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
    LEFT JOIN caiuas_crm_tags cct ON cct.cod_empresa = ce.COD_EMPRESA AND cct.cod_evento = ce.cod_evento
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
    if val_atual > val_ant: return "↑"
    elif val_atual < val_ant: return "↓"
    return "="

def get_percent(val_ant, val_atual):
    if val_ant > 0:
        return f"{((val_atual - val_ant) / val_ant) * 100:+.1f}%"
    elif val_atual > 0:
        return "+100.0%"
    return "0.0%"

def render():
    st.title("Fechamento por Mês")
    
    col_ano, col_mes, col_emp = st.columns(3)
    anos = [2023, 2024, 2025, 2026, 2027]
    meses = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 
             7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    
    with col_ano:
        ano_selecionado = st.selectbox("Ano", anos, index=anos.index(datetime.now().year) if datetime.now().year in anos else len(anos)-1)
    with col_mes:
        mes_selecionado_nome = st.selectbox("Mês", list(meses.values()), index=datetime.now().month - 1)
        mes_selecionado = [k for k, v in meses.items() if v == mes_selecionado_nome][0]
    with col_emp:
        empresas_opcoes = ['Todas', 'Sorocaba', 'Indaiatuba', 'LLA']
        empresa_selecionada = st.selectbox("Empresa", empresas_opcoes)
        
    mapa_cod_empresa = {'Sorocaba': '11', 'Indaiatuba': '33', 'LLA': '111'}
    cod_emp_filtro = mapa_cod_empresa.get(empresa_selecionada)
    
    # Datas
    primeiro_dia = datetime(ano_selecionado, mes_selecionado, 1).strftime('%Y-%m-%d')
    ultimo_dia = datetime(ano_selecionado, mes_selecionado, calendar.monthrange(ano_selecionado, mes_selecionado)[1]).strftime('%Y-%m-%d')
    
    # Mês anterior para comparação
    data_ant = datetime(ano_selecionado, mes_selecionado, 1) - pd.DateOffset(months=1)
    primeiro_dia_ant = data_ant.strftime('%Y-%m-%d')
    ultimo_dia_ant = (data_ant + pd.DateOffset(days=calendar.monthrange(data_ant.year, data_ant.month)[1]-1)).strftime('%Y-%m-%d')

    with st.spinner("Buscando dados..."):
        df_atual = get_dados_mes(primeiro_dia, ultimo_dia)
        df_ant = get_dados_mes(primeiro_dia_ant, ultimo_dia_ant)
        
        # Filtro de Leads por Empresa da Unidade (COD_EMPRESA)
        if cod_emp_filtro:
            df_atual = df_atual[df_atual['COD_EMPRESA'] == cod_emp_filtro]
            df_ant = df_ant[df_ant['COD_EMPRESA'] == cod_emp_filtro]

        tot_prop_atual, fat_atual, a_fat_atual = get_dados_propostas(primeiro_dia, ultimo_dia, cod_emp_filtro)
        tot_prop_ant, fat_ant, a_fat_ant = get_dados_propostas(primeiro_dia_ant, ultimo_dia_ant, cod_emp_filtro)
        propostas_faturadas = get_propostas_faturadas(primeiro_dia, ultimo_dia)

    # Métricas
    total_leads_atual = len(df_atual)
    agendados_atual = len(df_atual[df_atual['DATA_AGENDADA'] != ''])
    compareceram_atual = len(df_atual[df_atual['DATA_VISITA'] != ''])
    
    total_leads_ant = len(df_ant)
    agendados_ant = len(df_ant[df_ant['DATA_AGENDADA'] != ''])
    compareceram_ant = len(df_ant[df_ant['DATA_VISITA'] != ''])

    st.subheader(f"Performance Geral - {empresa_selecionada}")
    
    c1, c2 = meses[data_ant.month][:3].upper(), mes_selecionado_nome[:3].upper()
    data_tabela = [
        {"Indicador": "Total leads do mês", c1: total_leads_ant, c2: total_leads_atual, "Evolução": get_arrow(total_leads_ant, total_leads_atual), "Variação %": get_percent(total_leads_ant, total_leads_atual)},
        {"Indicador": "Agendados", c1: agendados_ant, c2: agendados_atual, "Evolução": get_arrow(agendados_ant, agendados_atual), "Variação %": get_percent(agendados_ant, agendados_atual)},
        {"Indicador": "Compareceram", c1: compareceram_ant, c2: compareceram_atual, "Evolução": get_arrow(compareceram_ant, compareceram_atual), "Variação %": get_percent(compareceram_ant, compareceram_atual)},
        {"Indicador": "Total propostas", c1: tot_prop_ant, c2: tot_prop_atual, "Evolução": get_arrow(tot_prop_ant, tot_prop_atual), "Variação %": get_percent(tot_prop_ant, tot_prop_atual)},
        {"Indicador": "Faturados", c1: fat_ant, c2: fat_atual, "Evolução": get_arrow(fat_ant, fat_atual), "Variação %": get_percent(fat_ant, fat_atual)},
        {"Indicador": "A faturar", c1: a_fat_ant, c2: a_fat_atual, "Evolução": get_arrow(a_fat_ant, a_fat_atual), "Variação %": get_percent(a_fat_ant, a_fat_atual)},
    ]
    
    df_tabela = pd.DataFrame(data_tabela)
    
    def color_arrow(val):
        if val == '↑':
            return 'color: green; font-weight: bold;'
        elif val == '↓':
            return 'color: red; font-weight: bold;'
        return ''

    def color_percent(val):
        if isinstance(val, str) and val.startswith('+'):
            return 'color: green; font-weight: bold;'
        elif isinstance(val, str) and val.startswith('-'):
            return 'color: red; font-weight: bold;'
        return ''
        
    if hasattr(df_tabela.style, 'map'):
        styled_df = df_tabela.style.map(color_arrow, subset=['Evolução']).map(color_percent, subset=['Variação %'])
    else:
        styled_df = df_tabela.style.applymap(color_arrow, subset=['Evolução']).applymap(color_percent, subset=['Variação %'])

    st.dataframe(styled_df, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Leads por Vendedor")

    # Preparação para Tabela de Vendedores
    df_vend = df_atual.copy()
    # Se o nome estiver vazio, vira "Não Atribuído" para aparecer na contagem
    df_vend['RESP_ATUAL'] = df_vend['RESP_ATUAL'].replace('', 'Não Atribuído')
    
    df_vend['IS_AGENDADO'] = (df_vend['DATA_AGENDADA'] != '').astype(int)
    df_vend['IS_VISITA'] = (df_vend['DATA_VISITA'] != '').astype(int)
    df_vend['IS_FATURADO'] = [1 if (p, e) in propostas_faturadas else 0 for p, e in zip(df_vend['COD_PROPOSTA'], df_vend['COD_EMPRESA'])]

    resumo_vend = df_vend.groupby(['RESP_ATUAL']).agg(
        Leads=('RESP_ATUAL', 'count'),
        Agendados=('IS_AGENDADO', 'sum'),
        Visitas=('IS_VISITA', 'sum'),
        Faturados=('IS_FATURADO', 'sum'),
    ).reset_index().rename(columns={'RESP_ATUAL': 'Vendedor'})

    resumo_vend['% Sucesso'] = resumo_vend.apply(
        lambda r: f"{(r['Faturados']/r['Visitas']*100):.1f}%" if r['Visitas'] > 0 else "0.0%", axis=1
    )

    st.dataframe(resumo_vend.sort_values('Leads', ascending=False), hide_index=True, use_container_width=True)