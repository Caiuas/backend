import pandas as pd
import streamlit as st
from datetime import datetime

from database import oracle


EMAILS_PROCESSOS = [
	"pablo.ti@caiuas.com.br",
    "franciele.mayer@caiuas.com.br",
    "vanessa.vilela@caiuas.com.br"
]


def render():
	st.title("Relatório de processos de veículos")

	data_inicial = st.sidebar.date_input(
		"Data inicial",
		datetime.now().replace(day=1).date(),
		key="processos_data_inicial",
	)
	data_final = st.sidebar.date_input(
		"Data final",
		datetime.now().date(),
		key="processos_data_final",
	)

	if data_inicial > data_final:
		st.error("A data inicial não pode ser maior que a data final.")
		return

	query = f"""
		SELECT DISTINCT
			v.CHASSI_COMPLETO AS chassi_completo,
			cvp.COD_PROPOSTA AS proposta,
			cvp.ID_PROCESSO AS id_processo,
			c.NOME AS nome_cliente,
			NVL(eu.NOME_COMPLETO, cvp.RESPONSIBLE) AS vendedor,
			vp.EMISSAO AS data_emissao_proposta,
			cvpe.CATEGORIA AS categoria,
			cvpe.STATUS AS status_etapa
		FROM CAIUAS_VEIC_PROC cvp
		INNER JOIN CAIUAS_VEIC_PROC_ETAPAS cvpe
			ON cvpe.ID_PROCESSO = cvp.ID_PROCESSO
		LEFT JOIN CLIENTES c
			ON c.COD_CLIENTE = cvp.COD_CLIENTE
		LEFT JOIN VEICULOS_PROPOSTAS vp
			ON vp.COD_PROPOSTA = cvp.COD_PROPOSTA
		LEFT JOIN VEICULOS v
			ON v.CHASSI_RESUMIDO = vp.CHASSI_RESUMIDO
		LEFT JOIN EMPRESAS_USUARIOS eu
			ON eu.NOME = vp.VENDEDOR
		WHERE cvp.ATIVO = 1
		  AND (vp.VENDEDOR IS NULL OR UPPER(TRIM(vp.VENDEDOR)) <> 'DIRETORIA')

		ORDER BY vp.EMISSAO DESC, cvp.COD_PROPOSTA
	"""

	conn = None
	cur = None
	try:
		conn, cur = oracle()
		cur.execute(query)
		rows = cur.fetchall()
		columns = [description[0].lower() for description in cur.description]
	except Exception as e:
		st.error(f"Erro ao carregar o relatório: {e}")
		return
	finally:
		if cur:
			cur.close()
		if conn:
			conn.close()

	df = pd.DataFrame(rows, columns=columns)
	if df.empty:
		st.info("Nenhum processo encontrado no período selecionado.")
		return

	df["categoria"] = df["categoria"].fillna("Sem categoria")
	df["categoria"] = df["categoria"].str.split(",")
	df = df.explode("categoria")
	df["categoria"] = df["categoria"].str.strip()
	df["status_categoria"] = df["status_etapa"].eq("Autorizado")

	colunas_processo = [
		"chassi_completo",
		"proposta",
		"id_processo",
		"nome_cliente",
		"vendedor",
		"data_emissao_proposta",
	]
	df = (
		df.groupby(colunas_processo + ["categoria"], dropna=False)["status_categoria"]
		.all()
		.reset_index()
	)
	df["status_categoria"] = df["status_categoria"].map(
		{True: "Concluído", False: "Pendente"}
	)

	df_relatorio = (
		df.pivot_table(
			index=[
				"chassi_completo",
				"proposta",
				"id_processo",
				"nome_cliente",
				"vendedor",
				"data_emissao_proposta",
			],
			columns="categoria",
			values="status_categoria",
			aggfunc="first",
		)
		.reset_index()
	)
	df_relatorio.columns.name = None
	df_relatorio = df_relatorio.fillna("")

	colunas_base = [
		"chassi_completo",
		"proposta",
		"id_processo",
		"nome_cliente",
		"vendedor",
		"data_emissao_proposta",
	]
	colunas_prioritarias = [
		"FATURAMENTO",
        "LIBERACAO",		
        "DOCUMENTACAO",
		"ENTREGA",
	]
	for coluna in colunas_prioritarias:
		if coluna not in df_relatorio.columns:
			df_relatorio[coluna] = ""

	colunas_outras = sorted(
		coluna for coluna in df_relatorio.columns
		if coluna not in colunas_base and coluna not in colunas_prioritarias
	)
	df_relatorio = df_relatorio[
		colunas_base + colunas_prioritarias + colunas_outras
	]

	df_relatorio["data_emissao_proposta"] = pd.to_datetime(
		df_relatorio["data_emissao_proposta"], errors="coerce"
	).dt.strftime("%d/%m/%Y")

	df_relatorio["proposta"] = df_relatorio.apply(
		lambda row: (
			f'https://app.caiuas.com.br/veiculos/processos/{row["id_processo"]}?proposta={row["proposta"]}'
			if pd.notna(row["proposta"]) and pd.notna(row["id_processo"])
			else ""
		),
		axis=1,
	)
	df_relatorio = df_relatorio.drop(columns=["id_processo"])

	colunas_categoria = [
		coluna for coluna in df_relatorio.columns
		if coluna not in {
			"chassi_completo",
			"proposta",
			"nome_cliente",
			"vendedor",
			"data_emissao_proposta",
		}
	]

	def destacar_status(dataframe):
		estilos = pd.DataFrame("", index=dataframe.index, columns=dataframe.columns)
		for coluna in colunas_categoria:
			estilos.loc[dataframe[coluna] == "Concluído", coluna] = (
				"background-color: #c6efce; color: #006100;"
			)
			estilos.loc[dataframe[coluna] == "Pendente", coluna] = (
				"background-color: #ffeb9c; color: #9c6500;"
			)
		return estilos

	st.dataframe(
		df_relatorio.style.apply(destacar_status, axis=None),
		column_config={
			"proposta": st.column_config.LinkColumn(
				"proposta",
				display_text=r"\?proposta=(.*)$",
				validate="^https://app\.caiuas\.com\.br/veiculos/processos/",
			)
		},
		hide_index=True,
		use_container_width=True,
	)
