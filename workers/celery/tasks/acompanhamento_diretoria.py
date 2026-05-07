import os
import re
import logging
import datetime
import requests
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import numpy as np
from app import app
from database import oracle

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
    "Cristiane": "8703967479",
    "Marcelo Camargo": "8105764200",
}
LOGO_PATH = "images/logo_honda.png"

# Paleta do Design System
COR_VERMELHO = "#D50000"
COR_AZUL = "#337AB7"
COR_CINZA_BORDA = "#D8DCE3"
COR_CINZA_FUNDO = "#F8F9FA"
COR_FUNDO_CARD = "#FFFFFF"
COR_TEXTO = "#2C3E50"

EMPRESAS_MAP = {"11": "Sorocaba", "33": "Indaiatuba", "111": "Seminovos"}

def _conexao():
    conn, cursor = oracle()
    return conn, cursor

def _extrair_empresa(cod_empresa_val):
    raw = str(cod_empresa_val) if cod_empresa_val is not None else ""
    m = re.search(r"(\d+)", raw)
    cod = m.group(1) if m else ""
    return EMPRESAS_MAP.get(cod, "Outros")

def _fetch_propostas_emitidas():
    query = """
        SELECT
            eu.cod_empresa,
            eu.NOME_COMPLETO NOME_VENDEDOR,
            pm.DESCRICAO_MODELO MODELO,
            vp.COD_PROPOSTA,
            vp.EMISSAO DATA_PROPOSTA,
            vp.DATA_VENDA,
            vp.DATA_CANCELAMENTO,
            vp.VALOR_PROPOSTA,
            vp.STATUS_PROPOSTA,
            vp.COD_CLIENTE,
            c.NOME NOME_CLIENTE
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
        WHERE TRUNC(vp.EMISSAO) >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
            AND vp.status_proposta NOT IN ('C')
        ORDER BY vp.EMISSAO
    """
    conn, cursor = _conexao()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(result, columns=columns)
    finally:
        cursor.close()
        conn.close()

def _fetch_canceladas():
    query = """
        SELECT
            eu.cod_empresa,
            eu.NOME_COMPLETO NOME_VENDEDOR,
            pm.DESCRICAO_MODELO MODELO,
            vp.COD_PROPOSTA,
            vp.DATA_CANCELAMENTO,
            vp.VALOR_PROPOSTA,
            c.NOME NOME_CLIENTE
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
        WHERE TRUNC(vp.DATA_CANCELAMENTO) >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
        ORDER BY vp.DATA_CANCELAMENTO
    """
    conn, cursor = _conexao()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(result, columns=columns)
    finally:
        cursor.close()
        conn.close()

def _fetch_faturadas_hoje():
    query = """
        SELECT
            eu.cod_empresa,
            eu.NOME_COMPLETO NOME_VENDEDOR,
            pm.DESCRICAO_MODELO MODELO,
            vp.COD_PROPOSTA,
            vp.DATA_VENDA,
            vp.VALOR_PROPOSTA,
            c.NOME NOME_CLIENTE
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
        WHERE vp.status_proposta = 'V'
            AND TRUNC(vp.DATA_VENDA) = TRUNC(SYSDATE)
        ORDER BY vp.DATA_VENDA
    """
    conn, cursor = _conexao()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(result, columns=columns)
    finally:
        cursor.close()
        conn.close()

def _gerar_kpis(df_emitidas, df_canceladas, df_faturadas):
    hoje = df_emitidas[df_emitidas["DATA_PROPOSTA"].notna()].copy()
    hoje["DATA"] = pd.to_datetime(hoje["DATA_PROPOSTA"]).dt.date
    hoje["MES"] = pd.to_datetime(hoje["DATA_PROPOSTA"]).dt.month
    hoje["ANO"] = pd.to_datetime(hoje["DATA_PROPOSTA"]).dt.year
    
    hoje_dia = datetime.date.today()
    mes_atual = hoje_dia.month
    ano_atual = hoje_dia.year

    primeiro_dia_mes_atual = hoje_dia.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    mes_anterior = ultimo_dia_mes_anterior.month
    ano_anterior = ultimo_dia_mes_anterior.year

    df_hoje = hoje[hoje["DATA"] == hoje_dia]
    df_mes = hoje[(hoje["MES"] == mes_atual) & (hoje["ANO"] == ano_atual)]
    df_mes_ant = hoje[(hoje["MES"] == mes_anterior) & (hoje["ANO"] == ano_anterior)]

    canc = df_canceladas[df_canceladas["DATA_CANCELAMENTO"].notna()].copy()
    canc["DATA"] = pd.to_datetime(canc["DATA_CANCELAMENTO"]).dt.date
    canc["MES"] = pd.to_datetime(canc["DATA_CANCELAMENTO"]).dt.month
    canc["ANO"] = pd.to_datetime(canc["DATA_CANCELAMENTO"]).dt.year
    
    df_canceladas_hoje = canc[canc["DATA"] == hoje_dia]
    df_canceladas_mes = canc[(canc["MES"] == mes_atual) & (canc["ANO"] == ano_atual)]

    total_emitidas_mes = len(df_mes)
    total_emitidas_mes_ant = len(df_mes_ant)
    total_emitidas = len(df_hoje)
    total_canceladas = len(df_canceladas_hoje)
    total_faturadas = len(df_faturadas)

    def _por_unidade(df, col_data="DATA_PROPOSTA"):
        result = {}
        for cod, nome in EMPRESAS_MAP.items():
            result[nome] = 0
        if df.empty:
            return result
        for _, row in df.iterrows():
            nome = _extrair_empresa(row.get("COD_EMPRESA"))
            if nome in result:
                result[nome] += 1
        return result

    unids_emitidas_mes = _por_unidade(df_mes)
    unids_emitidas = _por_unidade(df_hoje)
    unids_canceladas = _por_unidade(df_canceladas_hoje, "DATA_CANCELAMENTO")
    unids_faturadas = _por_unidade(df_faturadas, "DATA_VENDA")

    return {
        "emitidas_mes": {"total": total_emitidas_mes, "unidades": unids_emitidas_mes, "total_anterior": total_emitidas_mes_ant},
        "emitidas": {"total": total_emitidas, "unidades": unids_emitidas},
        "canceladas": {"total": total_canceladas, "unidades": unids_canceladas},
        "faturadas": {"total": total_faturadas, "unidades": unids_faturadas},
    }, df_hoje, df_canceladas_hoje, df_mes, df_canceladas_mes

def _formatar_tabela_design(t):
    t.auto_set_font_size(False)
    t.set_fontsize(7)
    for key, cell in t.get_celld().items():
        cell.set_edgecolor(COR_CINZA_BORDA)
        cell.set_linewidth(0.5)
        
        if key[0] == 0:
            cell.set_text_props(weight="bold", color="#333333", family="sans-serif")
            cell.set_facecolor("#E9ECEF")
        else:
            cell.set_facecolor(COR_FUNDO_CARD)
            cell.set_text_props(color=COR_TEXTO, family="sans-serif")

        if key[1] == 0:
            cell.set_text_props(ha='left')
            text_obj = cell.get_text()
            if not text_obj.get_text().startswith("  "):
                text_obj.set_text("   " + text_obj.get_text())
        else:
            cell.set_text_props(ha='center')

def setup_outer_card(ax):
    ax.set_facecolor(COR_FUNDO_CARD)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(COR_CINZA_BORDA)
        spine.set_linewidth(1.0)

def setup_inner_plot(ax):
    ax.set_facecolor(COR_FUNDO_CARD)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(COR_CINZA_BORDA)
    ax.grid(axis="y", linestyle="--", color=COR_CINZA_BORDA, alpha=0.7, zorder=0)
    ax.tick_params(axis="y", colors="#7F8C8D", labelsize=8, length=0)
    ax.tick_params(axis="x", colors=COR_TEXTO, labelsize=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

def generate_pdf():
    df_emitidas = _fetch_propostas_emitidas()
    df_canceladas = _fetch_canceladas()
    df_faturadas = _fetch_faturadas_hoje()

    kpis, df_hoje, df_canceladas_hoje, df_mes, df_canceladas_mes = _gerar_kpis(df_emitidas, df_canceladas, df_faturadas)
    hoje_data = datetime.date.today()

    fig = plt.figure(figsize=(8.27, 16.5), facecolor=COR_CINZA_FUNDO)
    
    gs = GridSpec(7, 4, figure=fig, 
                  height_ratios=[0.5, 1.3, 1.8, 1.8, 2.5, 2.5, 1.8],
                  top=0.96, bottom=0.04, left=0.06, right=0.94,
                  hspace=0.35, wspace=0.35)

    # --- 0. CABECALHO ---
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.axis("off")
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)
    try:
        logo_pil = Image.open(LOGO_PATH).convert("RGBA")
        logo_arr = np.array(logo_pil)
        ax_logo = ax_header.inset_axes([0, 0, 0.15, 1])
        ax_logo.imshow(logo_arr)
        ax_logo.axis("off")
    except Exception as e:
        logger.warning("Logo nao carregada: %s", e)
        
    ax_header.text(0.5, 0.6, "ACOMPANHAMENTO DIÁRIO", fontsize=18, ha="center",
                   weight="bold", color=COR_VERMELHO, family="sans-serif", transform=ax_header.transAxes)
    ax_header.text(0.5, 0.2, f"Relatório gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
                   fontsize=9, ha="center", color="#7F8C8D", family="sans-serif", transform=ax_header.transAxes)

    # --- 1. CARDS DE KPI ---
    kpi_configs = [
        ("EMITIDAS (MÊS)", kpis["emitidas_mes"]["total"], kpis["emitidas_mes"]["unidades"], "#8E44AD"),
        ("EMITIDAS (HOJE)", kpis["emitidas"]["total"], kpis["emitidas"]["unidades"], COR_AZUL),
        ("CANCELADAS (HOJE)", kpis["canceladas"]["total"], kpis["canceladas"]["unidades"], "#E74C3C"),
        ("FATURADAS (HOJE)", kpis["faturadas"]["total"], kpis["faturadas"]["unidades"], "#27AE60"),
    ]

    for idx, (titulo, total, unidades, cor_destaque) in enumerate(kpi_configs):
        ax_kpi = fig.add_subplot(gs[1, idx])
        setup_outer_card(ax_kpi)

        ax_kpi.text(0.5, 0.82, titulo, ha="center", va="center", fontsize=7.5,
                    weight="bold", color="#333333", family="sans-serif", transform=ax_kpi.transAxes)
        
        y_numero = 0.52 if titulo == "EMITIDAS (MÊS)" else 0.48
        
        ax_kpi.text(0.5, y_numero, str(total), ha="center", va="center", fontsize=28,
                    weight="bold", color=cor_destaque, family="sans-serif", transform=ax_kpi.transAxes)

        if titulo == "EMITIDAS (MÊS)":
            total_ant = kpis["emitidas_mes"]["total_anterior"]
            if total_ant > 0:
                pct = ((total - total_ant) / total_ant) * 100
                sinal = "▲" if pct > 0 else ("▼" if pct < 0 else "=")
                cor_pct = "#27AE60" if pct > 0 else ("#E74C3C" if pct < 0 else "#7F8C8D")
                comp_text = f"Mês ant: {total_ant} ({sinal} {abs(pct):.0f}%)"
            else:
                comp_text = f"Mês ant: {total_ant}"
                cor_pct = "#7F8C8D"
                
            ax_kpi.text(0.5, 0.30, comp_text, ha="center", va="center", fontsize=6.5,
                        weight="bold", color=cor_pct, family="sans-serif", transform=ax_kpi.transAxes)

        # A CORREÇÃO ESTÁ AQUI ABAIXO: Usando uma lista de 2 pontos pro Y também
        ax_kpi.plot([0.1, 0.9], [0.22, 0.22], color=COR_CINZA_BORDA, lw=1, transform=ax_kpi.transAxes)

        nomes_unidades = ["Sorocaba", "Indaiatuba", "Seminovos"]
        for j, nome in enumerate(nomes_unidades):
            qtd = unidades.get(nome, 0)
            x_nome = 0.16 + j * 0.34
            nome_abrev = nome if nome != "Indaiatuba" else "Indaia."
            ax_kpi.text(x_nome, 0.13, nome_abrev, ha="center", va="center",
                        fontsize=6, color="#7F8C8D", family="sans-serif", transform=ax_kpi.transAxes)
            ax_kpi.text(x_nome, 0.04, str(qtd), ha="center", va="center",
                        fontsize=8.5, weight="bold", color=COR_TEXTO, family="sans-serif", transform=ax_kpi.transAxes)

    # --- 2. GRÁFICO 1: Evolução Emitidas ---
    df_emitidas["DATA"] = pd.to_datetime(df_emitidas["DATA_PROPOSTA"]).dt.date
    vendas_por_dia = df_emitidas.groupby("DATA").size()
    dias = [hoje_data - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    valores_7d = [vendas_por_dia.get(dia, 0) for dia in dias]
    labels_7d = [dia.strftime("%d/%m") for dia in dias]

    ax_card1 = fig.add_subplot(gs[2, :])
    setup_outer_card(ax_card1)
    ax_card1.text(0.02, 0.88, "EVOLUÇÃO DE PROPOSTAS EMITIDAS", fontsize=11, weight="bold", color=COR_TEXTO, transform=ax_card1.transAxes)

    ax_plot1 = ax_card1.inset_axes([0.03, 0.12, 0.94, 0.65])
    setup_inner_plot(ax_plot1)
    
    bars1 = ax_plot1.bar(range(len(labels_7d)), valores_7d, color=COR_AZUL, edgecolor="none", width=0.5, zorder=3)
    ax_plot1.set_xticks(range(len(labels_7d)))
    ax_plot1.set_xticklabels(labels_7d)
    
    ymax1 = max(valores_7d) if max(valores_7d) > 0 else 5
    ax_plot1.set_ylim(0, ymax1 * 1.25)
    for i, v in enumerate(valores_7d):
        ax_plot1.text(i, v + ymax1 * 0.02, str(v), ha="center", va="bottom", fontsize=8, weight="bold", color=COR_TEXTO)

    # --- 3. GRÁFICO 2: Evolução Vendas ---
    ax_card2 = fig.add_subplot(gs[3, :])
    setup_outer_card(ax_card2)
    ax_card2.text(0.02, 0.88, "EVOLUÇÃO DE VENDAS", fontsize=11, weight="bold", color=COR_TEXTO, transform=ax_card2.transAxes)
    ax_card2.text(0.02, 0.76, "Vendas contabilizadas como: Propostas Emitidas - Propostas Canceladas no mesmo dia", fontsize=8, color="#7F8C8D", style="italic", transform=ax_card2.transAxes)

    ax_plot2 = ax_card2.inset_axes([0.03, 0.12, 0.94, 0.55])
    setup_inner_plot(ax_plot2)
    
    df_canceladas["DATA"] = pd.to_datetime(df_canceladas["DATA_CANCELAMENTO"]).dt.date
    df_emitidas["NOME_EMPRESA"] = df_emitidas["COD_EMPRESA"].apply(_extrair_empresa)
    df_canceladas["NOME_EMPRESA"] = df_canceladas["COD_EMPRESA"].apply(_extrair_empresa)

    v_soro, v_inda, v_semi, v_tot = [], [], [], []
    for dia in dias:
        emi_dia = df_emitidas[df_emitidas["DATA"] == dia]
        canc_dia = df_canceladas[df_canceladas["DATA"] == dia]
        v_soro.append(len(emi_dia[emi_dia["NOME_EMPRESA"] == "Sorocaba"]) - len(canc_dia[canc_dia["NOME_EMPRESA"] == "Sorocaba"]))
        v_inda.append(len(emi_dia[emi_dia["NOME_EMPRESA"] == "Indaiatuba"]) - len(canc_dia[canc_dia["NOME_EMPRESA"] == "Indaiatuba"]))
        v_semi.append(len(emi_dia[emi_dia["NOME_EMPRESA"] == "Seminovos"]) - len(canc_dia[canc_dia["NOME_EMPRESA"] == "Seminovos"]))
        v_tot.append(len(emi_dia) - len(canc_dia))

    x_pos = np.arange(len(labels_7d))
    width = 0.2

    b_soro = ax_plot2.bar(x_pos - 1.5 * width, v_soro, width, label='Sorocaba', color='#3498DB', zorder=3)
    b_inda = ax_plot2.bar(x_pos - 0.5 * width, v_inda, width, label='Indaiatuba', color='#E67E22', zorder=3)
    b_semi = ax_plot2.bar(x_pos + 0.5 * width, v_semi, width, label='Seminovos', color='#9B59B6', zorder=3)
    b_tot = ax_plot2.bar(x_pos + 1.5 * width, v_tot, width, label='Total', color='#27AE60', zorder=3)

    ax_plot2.set_xticks(x_pos)
    ax_plot2.set_xticklabels(labels_7d)
    ax_plot2.legend(loc='upper right', bbox_to_anchor=(1.0, 1.45), ncol=4, frameon=False, fontsize=8)

    max_val2 = max(max(v_soro), max(v_inda), max(v_semi), max(v_tot))
    ymax2 = max_val2 if max_val2 > 0 else 5
    ax_plot2.set_ylim(0, ymax2 * 1.35)

    for bars in [b_soro, b_inda, b_semi, b_tot]:
        for bar in bars:
            v = bar.get_height()
            ax_plot2.text(bar.get_x() + bar.get_width()/2., v + ymax2 * 0.02, str(int(v)), ha="center", va="bottom", fontsize=6, weight="bold", color=COR_TEXTO)

    # --- 4. TABELAS HOJE ---
    ax_card3 = fig.add_subplot(gs[4, 0:2])
    setup_outer_card(ax_card3)
    ax_card3.text(0.04, 0.90, "PROPOSTAS POR VENDEDOR (HOJE)", fontsize=10, weight="bold", color=COR_TEXTO, transform=ax_card3.transAxes)

    ax_tab1 = ax_card3.inset_axes([0.04, 0.04, 0.92, 0.80])
    ax_tab1.axis("off")
    if not df_hoje.empty and "NOME_VENDEDOR" in df_hoje.columns:
        vendas_vend = df_hoje.groupby("NOME_VENDEDOR").size().reset_index(name="EMITIDAS")
        vendas_vend["NOME_VENDEDOR"] = vendas_vend["NOME_VENDEDOR"].str.upper().str.strip()
        if not df_canceladas_hoje.empty and "NOME_VENDEDOR" in df_canceladas_hoje.columns:
            canc_vend = df_canceladas_hoje.groupby("NOME_VENDEDOR").size().reset_index(name="CANCELADAS")
            canc_vend["NOME_VENDEDOR"] = canc_vend["NOME_VENDEDOR"].str.upper().str.strip()
            tabela = vendas_vend.merge(canc_vend, on="NOME_VENDEDOR", how="left")
        else:
            tabela = vendas_vend.copy()
            tabela["CANCELADAS"] = 0

        tabela["CANCELADAS"] = tabela["CANCELADAS"].fillna(0).astype(int)
        tabela["VENDAS"] = tabela["EMITIDAS"] - tabela["CANCELADAS"]
        tabela = tabela.sort_values("EMITIDAS", ascending=False).head(10)
        tabela["NOME_VENDEDOR"] = tabela["NOME_VENDEDOR"].str[:25]

        cell_text = tabela[["NOME_VENDEDOR", "EMITIDAS", "CANCELADAS", "VENDAS"]].values.tolist()
        t1 = ax_tab1.table(cellText=cell_text, colLabels=["Vendedor", "Emitidas", "Canceladas", "Vendas"],
                         colWidths=[0.49, 0.17, 0.17, 0.17], loc="center", bbox=[0, 0, 1, 1])
        _formatar_tabela_design(t1)
    else:
        ax_tab1.text(0.5, 0.5, "Nenhuma proposta hoje", ha="center", va="center", fontsize=9, color="#7F8C8D")

    ax_card4 = fig.add_subplot(gs[4, 2:4])
    setup_outer_card(ax_card4)
    ax_card4.text(0.04, 0.90, "PROPOSTAS POR VEÍCULO (HOJE)", fontsize=10, weight="bold", color=COR_TEXTO, transform=ax_card4.transAxes)

    ax_tab2 = ax_card4.inset_axes([0.04, 0.04, 0.92, 0.80])
    ax_tab2.axis("off")
    if not df_hoje.empty and "MODELO" in df_hoje.columns:
        veic = df_hoje.groupby("MODELO").agg(PROPOSTAS=("COD_PROPOSTA", "count"), PRECO_MEDIO=("VALOR_PROPOSTA", "mean")).reset_index()
        veic["PRECO_MEDIO"] = veic["PRECO_MEDIO"].fillna(0).apply(lambda x: f"R$ {x:,.0f}" if x > 0 else "R$ 0")
        veic = veic.sort_values("PROPOSTAS", ascending=False).head(10)
        veic["MODELO"] = veic["MODELO"].fillna("Não informado").str[:25]

        cell_text2 = veic[["MODELO", "PROPOSTAS", "PRECO_MEDIO"]].values.tolist()
        t2 = ax_tab2.table(cellText=cell_text2, colLabels=["Veículo", "Propostas", "Preço Médio"],
                         colWidths=[0.55, 0.20, 0.25], loc="center", bbox=[0, 0, 1, 1])
        _formatar_tabela_design(t2)
    else:
        ax_tab2.text(0.5, 0.5, "Nenhuma proposta hoje", ha="center", va="center", fontsize=9, color="#7F8C8D")

    # --- 5. TABELAS MÊS ---
    ax_card5 = fig.add_subplot(gs[5, 0:2])
    setup_outer_card(ax_card5)
    ax_card5.text(0.04, 0.90, "PROPOSTAS POR VENDEDOR (MÊS)", fontsize=10, weight="bold", color=COR_TEXTO, transform=ax_card5.transAxes)

    ax_tab3 = ax_card5.inset_axes([0.04, 0.04, 0.92, 0.80])
    ax_tab3.axis("off")
    if not df_mes.empty and "NOME_VENDEDOR" in df_mes.columns:
        vendas_vend_m = df_mes.groupby("NOME_VENDEDOR").size().reset_index(name="EMITIDAS")
        vendas_vend_m["NOME_VENDEDOR"] = vendas_vend_m["NOME_VENDEDOR"].str.upper().str.strip()
        if not df_canceladas_mes.empty and "NOME_VENDEDOR" in df_canceladas_mes.columns:
            canc_vend_m = df_canceladas_mes.groupby("NOME_VENDEDOR").size().reset_index(name="CANCELADAS")
            canc_vend_m["NOME_VENDEDOR"] = canc_vend_m["NOME_VENDEDOR"].str.upper().str.strip()
            tabela_m = vendas_vend_m.merge(canc_vend_m, on="NOME_VENDEDOR", how="left")
        else:
            tabela_m = vendas_vend_m.copy()
            tabela_m["CANCELADAS"] = 0

        tabela_m["CANCELADAS"] = tabela_m["CANCELADAS"].fillna(0).astype(int)
        tabela_m["VENDAS"] = tabela_m["EMITIDAS"] - tabela_m["CANCELADAS"]
        tabela_m = tabela_m.sort_values("EMITIDAS", ascending=False).head(12)
        tabela_m["NOME_VENDEDOR"] = tabela_m["NOME_VENDEDOR"].str[:25]

        cell_text_m = tabela_m[["NOME_VENDEDOR", "EMITIDAS", "CANCELADAS", "VENDAS"]].values.tolist()
        t3 = ax_tab3.table(cellText=cell_text_m, colLabels=["Vendedor", "Emitidas", "Canceladas", "Vendas"],
                         colWidths=[0.49, 0.17, 0.17, 0.17], loc="center", bbox=[0, 0, 1, 1])
        _formatar_tabela_design(t3)
    else:
        ax_tab3.text(0.5, 0.5, "Nenhuma proposta no mês", ha="center", va="center", fontsize=9, color="#7F8C8D")

    ax_card6 = fig.add_subplot(gs[5, 2:4])
    setup_outer_card(ax_card6)
    ax_card6.text(0.04, 0.90, "PROPOSTAS POR VEÍCULO (MÊS)", fontsize=10, weight="bold", color=COR_TEXTO, transform=ax_card6.transAxes)

    ax_tab4 = ax_card6.inset_axes([0.04, 0.04, 0.92, 0.80])
    ax_tab4.axis("off")
    if not df_mes.empty and "MODELO" in df_mes.columns:
        veic_m = df_mes.groupby("MODELO").agg(PROPOSTAS=("COD_PROPOSTA", "count"), PRECO_MEDIO=("VALOR_PROPOSTA", "mean")).reset_index()
        veic_m["PRECO_MEDIO"] = veic_m["PRECO_MEDIO"].fillna(0).apply(lambda x: f"R$ {x:,.0f}" if x > 0 else "R$ 0")
        veic_m = veic_m.sort_values("PROPOSTAS", ascending=False).head(12)
        veic_m["MODELO"] = veic_m["MODELO"].fillna("Não informado").str[:25]

        cell_text4 = veic_m[["MODELO", "PROPOSTAS", "PRECO_MEDIO"]].values.tolist()
        t4 = ax_tab4.table(cellText=cell_text4, colLabels=["Veículo", "Propostas", "Preço Médio"],
                         colWidths=[0.55, 0.20, 0.25], loc="center", bbox=[0, 0, 1, 1])
        _formatar_tabela_design(t4)
    else:
        ax_tab4.text(0.5, 0.5, "Nenhuma proposta no mês", ha="center", va="center", fontsize=9, color="#7F8C8D")

    # --- 6. GRÁFICO 3: Total Emitidas Mês ---
    ax_card7 = fig.add_subplot(gs[6, :])
    setup_outer_card(ax_card7)
    ax_card7.text(0.02, 0.88, "TOTAL DE EMITIDAS DO MÊS (ACUMULADO)", fontsize=11, weight="bold", color=COR_TEXTO, transform=ax_card7.transAxes)
    
    ax_plot3 = ax_card7.inset_axes([0.03, 0.15, 0.94, 0.65])
    setup_inner_plot(ax_plot3)
    
    df_emitidas['MES_COMP'] = pd.to_datetime(df_emitidas["DATA_PROPOSTA"]).dt.month
    df_emitidas['DIA'] = pd.to_datetime(df_emitidas["DATA_PROPOSTA"]).dt.day

    mes_atual = hoje_data.month
    primeiro_dia_mes_atual = hoje_data.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    mes_anterior = ultimo_dia_mes_anterior.month

    emitidas_atual = df_emitidas[df_emitidas['MES_COMP'] == mes_atual].groupby('DIA').size()
    emitidas_anterior = df_emitidas[df_emitidas['MES_COMP'] == mes_anterior].groupby('DIA').size()

    max_dias_atual = (primeiro_dia_mes_atual.replace(month=primeiro_dia_mes_atual.month % 12 + 1, day=1) - datetime.timedelta(days=1)).day if primeiro_dia_mes_atual.month < 12 else 31
    max_dias_anterior = ultimo_dia_mes_anterior.day
    max_dias_plot = max(max_dias_atual, max_dias_anterior)
    dias_x = list(range(1, max_dias_plot + 1))
    
    y_atual = [emitidas_atual.get(d, 0) for d in dias_x]
    y_anterior = [emitidas_anterior.get(d, 0) for d in dias_x]
    emitidas_atual_cum = np.cumsum(y_atual)
    emitidas_anterior_cum = np.cumsum(y_anterior)

    dias_atual_plot = dias_x[:hoje_data.day]
    y_atual_plot = emitidas_atual_cum[:hoje_data.day]

    ax_plot3.plot(dias_atual_plot, y_atual_plot, marker='o', color=COR_AZUL, linewidth=2, label="Mês Atual", zorder=3)
    ax_plot3.plot(dias_x, emitidas_anterior_cum, marker='o', color="#BDC3C7", linewidth=2, label="Mês Anterior", zorder=2)

    ax_plot3.legend(loc="upper left", bbox_to_anchor=(0.0, 1.15), frameon=False, fontsize=8)
    ax_plot3.set_xticks(dias_x)
    
    buf = BytesIO()
    plt.savefig(buf, format="pdf", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf.read()

@app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_acompanhamento_diretoria(self):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    logger.info("Gerando relatorio PDF...")
    try:
        pdf_data = generate_pdf()
    except Exception as exc:
        logger.error("Erro ao gerar relatorio PDF: %s", exc)
        return {"status": "error", "details": str(exc)}

    resultados = []
    for nome, chat_id in TELEGRAM_CHATS.items():
        dados = {
            "chat_id": chat_id,
            "caption": "Acompanhamento diario de vendas e faturamento.",
        }
        logger.info("Tentando enviar relatorio para %s (ID %s)...", nome, chat_id)
        try:
            arquivos = {"document": ("relatorio_diario.pdf", pdf_data)}
            resposta = requests.post(url, data=dados, files=arquivos, timeout=15)
            if resposta.status_code == 200:
                logger.info("Enviado com sucesso para %s.", nome)
                resultados.append({"nome": nome, "status": "success"})
            else:
                logger.error("Falha ao enviar para %s: %s", nome, resposta.json())
                resultados.append({"nome": nome, "status": "error", "details": resposta.json()})
        except Exception as exc:
            logger.error("Erro ao enviar para %s: %s", nome, exc)
            resultados.append({"nome": nome, "status": "error", "details": str(exc)})

    if any(r.get("status") == "error" for r in resultados):
        logger.warning("Envio concluido com erros: %s", resultados)
        return {"status": "partial_success_or_error", "details": resultados}

    return {"status": "success", "details": resultados}