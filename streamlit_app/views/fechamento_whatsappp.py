import streamlit as st
import pandas as pd
import io
import plotly.express as px
from database import chatwoot, oracle

EMAILS_FECHAMENTO_WHATSAPPP = [
    "pablo.ti@caiuas.com.br",
    "kathie.sampaio@caiuas.com.br",
]


def _get_links_campanha():
    query = """
select
    c.custom_attributes->>'link_campanha' as link_campanha
from conversations c
left join contacts c2 on c2.id = c.contact_id
where c.custom_attributes->>'link_campanha' is not null
  and lower(c.custom_attributes->>'link_campanha') like 'https://hondacaiuas.com.br/campanha_%'
group by c.custom_attributes->>'link_campanha'
order by 1
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
        return [row[0] for row in result if row[0]]
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _get_fechamento(links_selecionados):
    filtro_links = ""
    if links_selecionados:
        escaped = [f"'{str(v).replace(chr(39), chr(39) + chr(39))}'" for v in links_selecionados]
        filtro_links = f"  AND c.custom_attributes->>'link_campanha' IN ({', '.join(escaped)})"

    query = f"""
SELECT
    c2.phone_number AS telefone,
    COUNT(c.id) AS qtd_conversas
FROM conversations c
LEFT JOIN contacts c2 ON c2.id = c.contact_id
WHERE c.custom_attributes->>'link_campanha' IS NOT NULL
  AND lower(c.custom_attributes->>'link_campanha') LIKE 'https://hondacaiuas.com.br/campanha_%'
  AND c2.phone_number IS NOT NULL
  AND c2.phone_number <> ''
{filtro_links}
GROUP BY c2.phone_number
ORDER BY qtd_conversas DESC, telefone ASC
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _get_atendimentos_por_campanha(links_selecionados):
    filtro_links = ""
    if links_selecionados:
        escaped = [f"'{str(v).replace(chr(39), chr(39) + chr(39))}'" for v in links_selecionados]
        filtro_links = f"  AND c.custom_attributes->>'link_campanha' IN ({', '.join(escaped)})"

    query = f"""
SELECT
    c.custom_attributes->>'link_campanha' AS link_campanha,
    COUNT(c.id) AS qtd_atendimentos,
    COUNT(*) FILTER (
        WHERE c.custom_attributes->>'evento_nbs' IS NOT NULL
          AND c.custom_attributes->>'evento_nbs' <> ''
    ) AS qtd_evento_nbs
FROM conversations c
WHERE c.custom_attributes->>'link_campanha' IS NOT NULL
  AND lower(c.custom_attributes->>'link_campanha') LIKE 'https://hondacaiuas.com.br/campanha_%'
{filtro_links}
GROUP BY c.custom_attributes->>'link_campanha'
ORDER BY qtd_atendimentos DESC
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _get_eventos_nbs(links_selecionados):
    filtro_links = ""
    if links_selecionados:
        escaped = [f"'{str(v).replace(chr(39), chr(39) + chr(39))}'" for v in links_selecionados]
        filtro_links = f"  AND c.custom_attributes->>'link_campanha' IN ({', '.join(escaped)})"

    query = f"""
SELECT DISTINCT c.custom_attributes->>'evento_nbs' AS evento_nbs
FROM conversations c
WHERE c.custom_attributes->>'link_campanha' IS NOT NULL
  AND lower(c.custom_attributes->>'link_campanha') LIKE 'https://hondacaiuas.com.br/campanha_%'
  AND c.custom_attributes->>'evento_nbs' IS NOT NULL
  AND c.custom_attributes->>'evento_nbs' <> ''
{filtro_links}
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    eventos = set()
    for row in result:
        valor = row[0]
        if valor and str(valor).strip():
            evento = str(valor).split("?")[0].split("/")[-1].strip()
            if evento:
                eventos.add(evento)
    return sorted(eventos)


def _get_eventos_por_andamento(eventos):
    if not eventos:
        return pd.DataFrame(columns=["andamento", "qtd_eventos"])

    escaped = [f"'{str(e).replace(chr(39), chr(39) + chr(39))}'" for e in eventos]
    in_clause = ", ".join(escaped)

    query = f"""
SELECT
    CASE
        WHEN UPPER(ce.STATUS) = 'D' THEN 'Descartado'
        ELSE NVL(ca.ANDAMENTO, 'Não informado')
    END AS andamento,
    COUNT(*) AS qtd_eventos
FROM crm_eventos ce
LEFT JOIN CRM_ANDAMENTO ca ON 1=1
    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
WHERE concat(ce.COD_EMPRESA, ce.COD_EVENTO) IN ({in_clause})
GROUP BY
    CASE
        WHEN UPPER(ce.STATUS) = 'D' THEN 'Descartado'
        ELSE NVL(ca.ANDAMENTO, 'Não informado')
    END
ORDER BY qtd_eventos DESC
"""
    conn, cur = oracle()
    try:
        cur.execute(query)
        result = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _get_bloqueados():
    query = """
select c.phone_number, c.name, c.updated_at from contacts c
where 1=1
    and c.blocked = true
order by c.updated_at desc
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _get_sem_campanha():
    query = """
select c.phone_number, c.name, c.updated_at from contacts c
where 1=1
    and coalesce(c.blocked, false) = false
    and c.phone_number is not null
    and c.phone_number <> ''
    and not exists (
        select 1 from conversations conv
        where conv.contact_id = c.id
          and conv.custom_attributes->>'link_campanha' is not null
          and lower(conv.custom_attributes->>'link_campanha') like 'https://hondacaiuas.com.br/campanha_%'
    )
order by c.updated_at desc
"""
    conn, cur = chatwoot()
    try:
        cur.execute(query)
        result = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def render():
    st.title("Fechamento Whatsapp")

    try:
        opcoes_link = _get_links_campanha()
    except Exception as e:
        st.error(f"Erro ao carregar links de campanha: {e}")
        return

    if not opcoes_link:
        st.info("Nenhum link de campanha encontrado.")
        return

    filtro_links = st.multiselect(
        "Filtrar por link_campanha",
        options=opcoes_link,
        default=[],
        key="fw_link_campanha",
        help="Inicialmente sem filtro (traz tudo). Selecione para restringir.",
    )

    try:
        with st.spinner("Buscando atendimentos por campanha..."):
            df_campanha = _get_atendimentos_por_campanha(filtro_links)
    except Exception as e:
        st.error(f"Erro ao carregar atendimentos por campanha: {e}")
        df_campanha = pd.DataFrame()

    if not df_campanha.empty:
        df_campanha["qtd_atendimentos"] = df_campanha["qtd_atendimentos"].astype(int)
        df_campanha["qtd_evento_nbs"] = df_campanha["qtd_evento_nbs"].astype(int)
        df_campanha["campanha"] = df_campanha["link_campanha"].str.replace(
            "https://hondacaiuas.com.br/", "", regex=False
        )
        df_campanha["pct_evento_nbs"] = (
            df_campanha["qtd_evento_nbs"]
            / df_campanha["qtd_atendimentos"].replace(0, pd.NA)
            * 100
        ).fillna(0)

        df_plot = df_campanha.melt(
            id_vars="campanha",
            value_vars=["qtd_atendimentos", "qtd_evento_nbs"],
            var_name="Tipo",
            value_name="Quantidade",
        )
        df_plot["Tipo"] = df_plot["Tipo"].map(
            {"qtd_atendimentos": "Atendimentos", "qtd_evento_nbs": "Com evento NBS"}
        )

        pct_por_campanha = df_campanha.set_index("campanha")["pct_evento_nbs"]

        def _texto_barra(row):
            if row["Tipo"] == "Com evento NBS":
                pct = pct_por_campanha.get(row["campanha"], 0)
                return f'{row["Quantidade"]} ({pct:.1f}%)'
            return f'{row["Quantidade"]}'

        df_plot["texto"] = df_plot.apply(_texto_barra, axis=1)

        fig_campanha = px.bar(
            df_plot,
            x="campanha",
            y="Quantidade",
            color="Tipo",
            barmode="group",
            text="texto",
            title="Atendimentos por campanha x Eventos no NBS",
            color_discrete_map={"Atendimentos": "#3498db", "Com evento NBS": "#2ecc71"},
        )
        fig_campanha.update_traces(textposition="outside")
        fig_campanha.update_layout(xaxis_title="", yaxis_title="Quantidade", legend_title="")
        st.plotly_chart(fig_campanha, use_container_width=True)

        total_atend = int(df_campanha["qtd_atendimentos"].sum())
        total_nbs = int(df_campanha["qtd_evento_nbs"].sum())
        pct_geral = (total_nbs / total_atend * 100) if total_atend else 0
        st.caption(
            f"Comparativo geral: {total_nbs} de {total_atend} atendimentos com evento no NBS "
            f"({pct_geral:.1f}%)"
        )

    try:
        with st.spinner("Buscando eventos por andamento..."):
            eventos_nbs = _get_eventos_nbs(filtro_links)
            df_andamento = _get_eventos_por_andamento(eventos_nbs)
    except Exception as e:
        st.error(f"Erro ao carregar eventos por andamento: {e}")
        df_andamento = pd.DataFrame()

    if df_andamento.empty:
        st.info("Nenhum evento NBS encontrado para o filtro selecionado.")
    else:
        df_andamento["qtd_eventos"] = df_andamento["qtd_eventos"].astype(int)
        df_andamento = df_andamento.sort_values("qtd_eventos", ascending=True)

        fig_andamento = px.bar(
            df_andamento,
            x="qtd_eventos",
            y="andamento",
            orientation="h",
            text="qtd_eventos",
            title="Eventos no NBS por andamento",
            color="qtd_eventos",
            color_continuous_scale="Blues",
        )
        fig_andamento.update_traces(textposition="outside")
        fig_andamento.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            xaxis_title="Quantidade de eventos",
            yaxis_title="",
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_andamento, use_container_width=True)

    try:
        with st.spinner("Buscando dados..."):
            df = _get_fechamento(filtro_links)
    except Exception as e:
        st.error(f"Erro ao carregar fechamento: {e}")
        return

    if df.empty:
        st.info("Nenhum dado encontrado para o filtro selecionado.")
    else:
        df["qtd_conversas"] = df["qtd_conversas"].astype(int)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Telefones", len(df))
        with col2:
            st.metric("Total de conversas", int(df["qtd_conversas"].sum()))

        st.subheader("Conversas por telefone")
        st.caption(f"{len(df)} telefone(s)")
        st.dataframe(df, hide_index=True, use_container_width=True)

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name="Fechamento")
        excel_buffer.seek(0)
        st.download_button(
            label=f"📥 Download da planilha ({len(df)} linhas)",
            data=excel_buffer,
            file_name=f"fechamento_whatsapp_{len(df)}_linhas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_fechamento_whatsapp",
        )

    st.divider()
    st.subheader("Contatos bloqueados")
    try:
        with st.spinner("Buscando bloqueados..."):
            df_block = _get_bloqueados()
    except Exception as e:
        st.error(f"Erro ao carregar bloqueados: {e}")
        return

    if df_block.empty:
        st.info("Nenhum contato bloqueado.")
    else:
        st.metric("Contatos bloqueados", len(df_block))
        st.caption(f"{len(df_block)} contato(s)")
        st.dataframe(
            df_block,
            hide_index=True,
            use_container_width=True,
            column_config={
                "updated_at": st.column_config.DatetimeColumn("Atualizado em", format="DD/MM/YYYY HH:mm"),
            },
        )

        excel_block = io.BytesIO()
        df_block.to_excel(excel_block, index=False, sheet_name="Bloqueados")
        excel_block.seek(0)
        st.download_button(
            label=f"📥 Download bloqueados ({len(df_block)} linhas)",
            data=excel_block,
            file_name=f"contatos_bloqueados_{len(df_block)}_linhas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_fechamento_bloqueados",
        )

    st.divider()
    st.subheader("Contatos que nunca receberam campanha")
    try:
        with st.spinner("Buscando contatos sem campanha..."):
            df_sem = _get_sem_campanha()
    except Exception as e:
        st.error(f"Erro ao carregar contatos sem campanha: {e}")
        return

    if df_sem.empty:
        st.info("Nenhum contato sem campanha.")
        return

    st.metric("Contatos sem campanha", len(df_sem))
    st.caption(f"{len(df_sem)} contato(s)")
    st.dataframe(
        df_sem,
        hide_index=True,
        use_container_width=True,
        column_config={
            "updated_at": st.column_config.DatetimeColumn("Atualizado em", format="DD/MM/YYYY HH:mm"),
        },
    )

    excel_sem = io.BytesIO()
    df_sem.to_excel(excel_sem, index=False, sheet_name="SemCampanha")
    excel_sem.seek(0)
    st.download_button(
        label=f"📥 Download sem campanha ({len(df_sem)} linhas)",
        data=excel_sem,
        file_name=f"contatos_sem_campanha_{len(df_sem)}_linhas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_fechamento_sem_campanha",
    )
