import streamlit as st
import pandas as pd
import io
from database import chatwoot

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
