import os
import logging
import datetime
import requests
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import numpy as np
from app import app
from database import oracle

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
}
LOGO_PATH = "images/logo_honda.png"

# Paleta
COR_VERMELHO = "#D50000"
COR_AZUL = "#337AB7"
COR_CINZA_BORDA = "#D8DCE3"
COR_CINZA_FUNDO = "#F8F9FA"
COR_FUNDO_CARD = "#FFFFFF"
COR_TEXTO = "#2C3E50"

CORES_PIZZA = [
    "#337AB7", "#E74C3C", "#27AE60", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2980B9", "#C0392B", "#16A085",
    "#8E44AD", "#D35400", "#2ECC71", "#3498DB", "#E91E63",
]

QUERY = """
SELECT
    eu.NOME_COMPLETO responsavel,
    cet.DESC_TIPO_EVENTO tipo_evento,
    count(*) quantidade
FROM
    CRM_EVENTOS ce
LEFT JOIN EMPRESAS_USUARIOS eu ON
    1 = 1
    AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
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
LEFT JOIN caiuas_crm_eventos_descartados ced ON ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
WHERE
    1 = 1
    AND ce.cod_tipo_evento in ('829','831','795','793','797','799','819','821','785','807','815','817','810','812')
    AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE)
    AND ce.status IN ('P','CV','CR','CA')
GROUP BY eu.NOME_COMPLETO, cet.DESC_TIPO_EVENTO
ORDER BY 1
"""


def _fetch_data():
    conn, cursor = oracle()
    try:
        cursor.execute(QUERY)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(result, columns=columns)
        df["RESPONSAVEL"] = df["RESPONSAVEL"].fillna("Sem Responsável").replace("", "Sem Responsável")
        return df
    finally:
        cursor.close()
        conn.close()


def _formatar_tabela(t, header_color="#E9ECEF"):
    t.auto_set_font_size(False)
    t.set_fontsize(7)
    for key, cell in t.get_celld().items():
        cell.set_edgecolor(COR_CINZA_BORDA)
        cell.set_linewidth(0.5)
        if key[0] == 0:
            cell.set_text_props(weight="bold", color="#333333")
            cell.set_facecolor(header_color)
        else:
            cell.set_facecolor(COR_FUNDO_CARD)
            cell.set_text_props(color=COR_TEXTO)
        if key[1] == 0:
            cell.set_text_props(ha="left")
            text_obj = cell.get_text()
            if not text_obj.get_text().startswith("  "):
                text_obj.set_text("   " + text_obj.get_text())
        else:
            cell.set_text_props(ha="center")


def _setup_card(ax):
    ax.set_facecolor(COR_FUNDO_CARD)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(COR_CINZA_BORDA)
        spine.set_linewidth(1.0)


def _setup_bar(ax):
    ax.set_facecolor(COR_FUNDO_CARD)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(COR_CINZA_BORDA)
    ax.grid(axis="y", linestyle="--", color=COR_CINZA_BORDA, alpha=0.7, zorder=0)
    ax.tick_params(axis="y", colors="#7F8C8D", labelsize=8, length=0)
    ax.tick_params(axis="x", colors=COR_TEXTO, labelsize=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))


def generate_pdf(df):
    tipos = sorted(df["TIPO_EVENTO"].dropna().unique().tolist())
    n_tipos = len(tipos)

    # Layout: cabeçalho + pizza + 1 gráfico por linha (largura total) + tabela
    n_tabela_rows = len(df) + 2
    tabela_height = max(3.0, min(n_tabela_rows * 0.30, 10.0))

    fig_height = 1.0 + 3.5 + n_tipos * 2.8 + tabela_height + 0.5
    fig = plt.figure(figsize=(11.0, fig_height), facecolor=COR_CINZA_FUNDO)

    # GridSpec dinâmico: 1 coluna (cada gráfico ocupa a linha inteira)
    height_ratios = [0.6, 3.5] + [2.5] * n_tipos + [tabela_height]
    gs = GridSpec(
        2 + n_tipos + 1, 1,
        figure=fig,
        height_ratios=height_ratios,
        top=0.97, bottom=0.02,
        left=0.05, right=0.95,
        hspace=0.45,
    )

    # ---- CABEÇALHO ----
    ax_header = fig.add_subplot(gs[0, 0])
    ax_header.axis("off")
    ax_header.text(
        0.5, 0.6, "EVENTOS CRM EM ATRASO — POR RESPONSÁVEL E TIPO",
        fontsize=16, ha="center", weight="bold",
        color=COR_VERMELHO, transform=ax_header.transAxes,
    )
    ax_header.text(
        0.5, 0.1,
        f"Relatório gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
        fontsize=9, ha="center", color="#7F8C8D", transform=ax_header.transAxes,
    )

    # ---- PIZZA: total por responsável ----
    ax_pizza_card = fig.add_subplot(gs[1, 0])
    _setup_card(ax_pizza_card)
    ax_pizza_card.text(
        0.5, 0.95, "EVENTOS EM ATRASO POR RESPONSÁVEL (TOTAL)",
        fontsize=12, ha="center", weight="bold", color=COR_TEXTO,
        transform=ax_pizza_card.transAxes,
    )

    total_por_resp = (
        df.groupby("RESPONSAVEL")["QUANTIDADE"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    ax_pizza = ax_pizza_card.inset_axes([0.15, 0.05, 0.70, 0.82])
    ax_pizza.set_facecolor(COR_FUNDO_CARD)

    labels_pizza = total_por_resp["RESPONSAVEL"].tolist()
    valores_pizza = total_por_resp["QUANTIDADE"].tolist()
    cores_pizza = [CORES_PIZZA[i % len(CORES_PIZZA)] for i in range(len(labels_pizza))]

    wedges, texts, autotexts = ax_pizza.pie(
        valores_pizza,
        labels=None,
        colors=cores_pizza,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 2.0 else "",
        startangle=140,
        pctdistance=0.80,
        wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
    )
    for at in autotexts:
        at.set_fontsize(7)
        at.set_color("white")
        at.set_weight("bold")

    # Legenda ao lado
    legend_labels = [
        f"{r['RESPONSAVEL']} ({int(r['QUANTIDADE'])})"
        for _, r in total_por_resp.iterrows()
    ]
    ax_pizza.legend(
        wedges, legend_labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=7.5,
        frameon=False,
        title="Responsável (total)",
        title_fontsize=8,
    )

    # ---- GRÁFICOS DE BARRA POR TIPO DE EVENTO ----
    for idx, tipo in enumerate(tipos):
        row = 2 + idx

        df_tipo = (
            df[df["TIPO_EVENTO"] == tipo]
            .groupby("RESPONSAVEL")["QUANTIDADE"].sum()
            .sort_values(ascending=False)
            .reset_index()
        )

        ax_card = fig.add_subplot(gs[row, 0])
        _setup_card(ax_card)
        titulo_tipo = tipo[:80] if tipo else "Sem tipo"
        ax_card.text(
            0.02, 0.93, titulo_tipo,
            fontsize=9, weight="bold", color=COR_TEXTO,
            transform=ax_card.transAxes, va="top",
        )

        ax_bar = ax_card.inset_axes([0.02, 0.10, 0.96, 0.75])
        _setup_bar(ax_bar)

        responsaveis = df_tipo["RESPONSAVEL"].tolist()
        quantidades = df_tipo["QUANTIDADE"].tolist()
        x_pos = np.arange(len(responsaveis))

        cor_idx = idx % len(CORES_PIZZA)
        bars = ax_bar.bar(x_pos, quantidades, color=CORES_PIZZA[cor_idx], width=0.55, zorder=3)

        ax_bar.set_xticks(x_pos)
        ax_bar.set_xticklabels(responsaveis, rotation=30, ha="right", fontsize=8)

        ymax = max(quantidades) if quantidades else 1
        ax_bar.set_ylim(0, ymax * 1.3)
        for bar, v in zip(bars, quantidades):
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2.0,
                v + ymax * 0.02,
                str(int(v)),
                ha="center", va="bottom", fontsize=8, weight="bold", color=COR_TEXTO,
            )

    # ---- TABELA ----
    row_tabela = 2 + n_tipos
    ax_tab_card = fig.add_subplot(gs[row_tabela, 0])
    _setup_card(ax_tab_card)
    ax_tab_card.text(
        0.04, 0.97, "DETALHAMENTO — EVENTOS EM ATRASO POR RESPONSÁVEL E TIPO",
        fontsize=10, weight="bold", color=COR_TEXTO,
        transform=ax_tab_card.transAxes, va="top",
    )

    ax_tab = ax_tab_card.inset_axes([0.01, 0.02, 0.98, 0.88])
    ax_tab.axis("off")

    df_tabela = df[["RESPONSAVEL", "TIPO_EVENTO", "QUANTIDADE"]].copy()
    df_tabela["RESPONSAVEL"] = df_tabela["RESPONSAVEL"].str[:40]
    df_tabela["TIPO_EVENTO"] = df_tabela["TIPO_EVENTO"].fillna("").str[:50]
    df_tabela["QUANTIDADE"] = df_tabela["QUANTIDADE"].astype(int)
    df_tabela = df_tabela.sort_values(["RESPONSAVEL", "TIPO_EVENTO"])

    cell_text = df_tabela.values.tolist()
    t = ax_tab.table(
        cellText=cell_text,
        colLabels=["Responsável", "Tipo de Evento", "Quantidade"],
        colWidths=[0.35, 0.50, 0.15],
        loc="upper center",
        bbox=[0, 0, 1, 1],
    )
    _formatar_tabela(t)

    buf = BytesIO()
    plt.savefig(buf, format="pdf", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf.read()


@app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_crm_eventos_atraso(self):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    logger.info("Gerando relatório de eventos CRM em atraso...")
    try:
        df = _fetch_data()
        if df.empty:
            logger.warning("Nenhum evento em atraso encontrado.")
            return {"status": "no_data"}
        pdf_data = generate_pdf(df)
    except Exception as exc:
        logger.error("Erro ao gerar relatório de eventos CRM em atraso: %s", exc)
        raise self.retry(exc=exc)

    resultados = []
    for nome, chat_id in TELEGRAM_CHATS.items():
        dados = {
            "chat_id": chat_id,
            "caption": (
                "📋 EVENTOS CRM EM ATRASO\n\n"
                "Relatório com eventos em atraso por responsável e tipo de evento.\n"
                f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
        }
        try:
            resp = requests.post(
                url,
                data=dados,
                files={"document": ("crm_eventos_atraso.pdf", pdf_data)},
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info("Enviado com sucesso para %s.", nome)
                resultados.append({"nome": nome, "status": "success"})
            else:
                logger.error("Falha ao enviar para %s: %s", nome, resp.json())
                resultados.append({"nome": nome, "status": "error", "details": resp.json()})
        except Exception as exc:
            logger.error("Erro ao enviar para %s: %s", nome, exc)
            resultados.append({"nome": nome, "status": "error", "details": str(exc)})

    if any(r.get("status") == "error" for r in resultados):
        return {"status": "partial_error", "details": resultados}

    return {"status": "success", "details": resultados}
