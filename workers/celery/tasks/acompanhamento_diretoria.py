import os
import logging
import datetime
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import numpy as np
from app import app
from database import oracle

logger = logging.getLogger(__name__)

# ==========================================
# 1. SUAS CONFIGURAÇÕES
# ==========================================
TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
    "Cristiane": "8703967479",
    # Adicione outros números aqui seguindo o modelo:
    # "Nome do Diretor": "ID_AQUI",
}
LOGO_PATH = "images/logo_honda.png"
CAMINHO_ARQUIVO = "relatorio_diario.pdf"

def get_data():
    query = """
    SELECT 
        eu.cod_empresa,
        to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
        vp.EMISSAO data_proposta, 
        upper(eu.NOME_COMPLETO) nome_vendedor, 
        pm.DESCRICAO_MODELO modelo, 
        COALESCE(ce_veic.DESCRICAO, ce_ped.DESCRICAO, ce_fic.DESCRICAO) AS cor, 
        v.CHASSI_COMPLETO, 
        c.NOME nome_cliente,
        CASE 
            WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
            WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
            WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
            WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
        END AS telefone,
        c.EMAIL_NFE email,
        CASE 
            WHEN v.novo_usado = 'U' THEN 'Usado'
            ELSE 'Novo'
        END novo_usado,
        CASE
            WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO 
            WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
            ELSE cid_cob.DESCRICAO 
        END cidade,
        'Aguardando Faturamento' Status,
        concat(cev.cod_empresa, cev.COD_EVENTO) evento
    FROM VEICULOS_PROPOSTAS vp 
    LEFT JOIN produtos pr ON 1=1
        AND pr.COD_PRODUTO = vp.COD_PRODUTO  
    LEFT JOIN produtos_modelos pm ON 1=1
        AND pm.COD_PRODUTO = vp.COD_PRODUTO 
        AND pm.COD_MODELO = vp.COD_MODELO 
    LEFT JOIN VEICULOS v ON 1=1
        AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
        AND vp.COD_PRODUTO = v.COD_PRODUTO      
        AND vp.COD_MODELO = v.COD_MODELO        
        AND vp.cod_empresa = v.cod_empresa      
        AND v.status = 'E' 
    LEFT JOIN VEICULOS_PEDIDOS vped ON 1=1
        AND vp.COD_PEDIDO = vped.COD_PEDIDO
    LEFT JOIN PROP_FICTICIA_DADOS pfd ON 1=1
        AND vp.COD_FICTICIO = pfd.COD_FICTICIO
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
    LEFT JOIN CORES_EXTERNAS ce_veic ON 1=1          
        AND ce_veic.COR_EXTERNA = v.COR_EXTERNA
    LEFT JOIN CORES_EXTERNAS ce_ped ON 1=1         
        AND ce_ped.COR_EXTERNA = vped.COR_EXTERNA
    LEFT JOIN CORES_EXTERNAS ce_fic ON 1=1         
        AND ce_fic.COR_EXTERNA = pfd.COR_EXTERNA
    LEFT JOIN crm_eventos cev ON 1=1            
        AND cev.COD_PROPOSTA = vp.COD_PROPOSTA
        AND cev.status <> 'D'
        AND cev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
    WHERE 1=1
        AND vp.status_proposta in ('A','V')
        AND TRUNC(vp.EMISSAO) >= TRUNC(SYSDATE) - 6
    """
    conn, cursor = oracle()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        cursor.close()
        conn.close()

def get_faturamento_data():
    query = """
    SELECT 
        eu.cod_empresa,
        to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
        vp.EMISSAO data_proposta, 
        upper(eu.NOME_COMPLETO) nome_vendedor, 
        pm.DESCRICAO_MODELO modelo, 
        COALESCE(ce_veic.DESCRICAO, ce_ped.DESCRICAO, ce_fic.DESCRICAO) AS cor, 
        v.CHASSI_COMPLETO, 
        c.NOME nome_cliente,
        CASE 
            WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
            WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
            WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
            WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
        END AS telefone,
        c.EMAIL_NFE email,
        CASE 
            WHEN v.novo_usado = 'U' THEN 'Usado'
            ELSE 'Novo'
        END novo_usado,
        CASE
            WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO 
            WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
            ELSE cid_cob.DESCRICAO 
        END cidade,
        'Faturado' Status,
        concat(cev.cod_empresa, cev.COD_EVENTO) evento
    FROM VEICULOS_PROPOSTAS vp 
    LEFT JOIN produtos pr ON 1=1
        AND pr.COD_PRODUTO = vp.COD_PRODUTO  
    LEFT JOIN produtos_modelos pm ON 1=1
        AND pm.COD_PRODUTO = vp.COD_PRODUTO 
        AND pm.COD_MODELO = vp.COD_MODELO 
    LEFT JOIN VEICULOS v ON 1=1
        AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
        AND vp.COD_PRODUTO = v.COD_PRODUTO      
        AND vp.COD_MODELO = v.COD_MODELO        
        AND vp.cod_empresa = v.cod_empresa      
        AND v.status = 'V' 
    LEFT JOIN VEICULOS_PEDIDOS vped ON 1=1
        AND vp.COD_PEDIDO = vped.COD_PEDIDO
    LEFT JOIN PROP_FICTICIA_DADOS pfd ON 1=1
        AND vp.COD_FICTICIO = pfd.COD_FICTICIO
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
    LEFT JOIN CORES_EXTERNAS ce_veic ON 1=1          
        AND ce_veic.COR_EXTERNA = v.COR_EXTERNA
    LEFT JOIN CORES_EXTERNAS ce_ped ON 1=1         
        AND ce_ped.COR_EXTERNA = vped.COR_EXTERNA
    LEFT JOIN CORES_EXTERNAS ce_fic ON 1=1         
        AND ce_fic.COR_EXTERNA = pfd.COR_EXTERNA
    LEFT JOIN crm_eventos cev ON 1=1            
        AND cev.COD_PROPOSTA = vp.COD_PROPOSTA
        AND cev.status <> 'D'
        AND cev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
    WHERE 1=1
        AND vp.status_proposta = 'V'
        AND TRUNC(vp.EMISSAO) = TRUNC(SYSDATE)
    """
    conn, cursor = oracle()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        cursor.close()
        conn.close()

def generate_pdf():
    df = get_data()
    df_fat = get_faturamento_data()
    
    # Preprocessamento das datas
    df['DATA_PROPOSTA'] = pd.to_datetime(df['DATA_PROPOSTA']).dt.date
    if not df_fat.empty:
        df_fat['DATA_PROPOSTA'] = pd.to_datetime(df_fat['DATA_PROPOSTA']).dt.date
        
    hoje = datetime.date.today()
    
    # HOJE VENDAS
    df_hoje = df[df['DATA_PROPOSTA'] == hoje]
    vendas_hoje = len(df_hoje)
    
    # EVOLUCAO 7 DIAS VENDAS
    vendas_por_dia = df.groupby('DATA_PROPOSTA').size()
    dias = [hoje - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    valores = [vendas_por_dia.get(dia, 0) for dia in dias]
    labels_dias = [dia.strftime('%d/%m') for dia in dias]
    
    # Criacao do PDF expandido (12x14)
    fig = plt.figure(figsize=(12, 14), facecolor='#F4F7F6')
    
    # ==========================================
    # SESSÃO 1: CABEÇALHO E GRÁFICOS (HOJE vs 7D)
    # ==========================================
    
    try:
        logo_pil = Image.open(LOGO_PATH).convert("RGBA")
        logo = np.array(logo_pil)
        ax_logo = fig.add_axes([0.05, 0.92, 0.15, 0.05], anchor='NW', zorder=1)
        ax_logo.imshow(logo)
        ax_logo.axis('off')
    except Exception as e:
        logger.warning(f"Não foi possível carregar a logo: {e}")
    
    fig.text(0.5, 0.95, "Acompanhamento Diário de Vendas", fontsize=24, ha='center', weight='bold', color='#2C3E50', family='sans-serif')
    fig.text(0.5, 0.92, f"Relatório gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", fontsize=11, ha='center', color='#7F8C8D', style='italic')
    
    # QUADRO VENDAS HOJE
    ax_quadro = fig.add_axes([0.05, 0.55, 0.35, 0.32])
    ax_quadro.axis('off')
    
    box = FancyBboxPatch((0.05, 0.05), 0.9, 0.9, boxstyle="round,pad=0.05", 
                         fill=True, color='white', ec='#E0E4E8', lw=1.5, zorder=0)
    ax_quadro.add_patch(box)
    
    ax_quadro.text(0.5, 0.85, "VENDAS HOJE", ha='center', va='center', fontsize=16, weight='bold', color='#7F8C8D')
    ax_quadro.text(0.5, 0.65, f"{vendas_hoje}", ha='center', va='center', fontsize=65, weight='bold', color='#2980B9')
    ax_quadro.plot([0.2, 0.8], [0.48, 0.48], color='#ECF0F1', lw=2)
    
    col_empresa_hoje = next((c for c in df_hoje.columns if c.upper() == 'COD_EMPRESA'), None)
    empresas_map = {'11': "Sorocaba", '33': "Indaiatuba", '111': "Seminovos"}
    
    if col_empresa_hoje:
        y_pos = 0.35
        for cod, nome in empresas_map.items():
            qtd = len(df_hoje[df_hoje[col_empresa_hoje].astype(str).str.extract(r'(\d+)', expand=False) == cod])
            ax_quadro.text(0.25, y_pos, f"{nome}", ha='left', va='center', fontsize=14, color='#34495E', weight='medium')
            ax_quadro.text(0.75, y_pos, f"{qtd}", ha='right', va='center', fontsize=16, color='#2C3E50', weight='bold')
            y_pos -= 0.12
            
    # GRÁFICO 7 DIAS
    ax_bar = fig.add_axes([0.48, 0.55, 0.45, 0.32])
    ax_bar.set_facecolor('#F4F7F6')
    bars = ax_bar.bar(labels_dias, valores, color='#3498DB', edgecolor='none', width=0.6, zorder=3)
    ax_bar.spines['top'].set_visible(False)
    ax_bar.spines['right'].set_visible(False)
    ax_bar.spines['left'].set_visible(False)
    ax_bar.spines['bottom'].set_color('#BDC3C7')
    ax_bar.grid(axis='y', linestyle='--', color='#BDC3C7', alpha=0.7, zorder=0)
    ax_bar.set_title("Evolução dos Últimos 7 Dias", fontsize=16, weight='bold', color='#2C3E50', pad=20)
    
    if max(valores) > 0:
        ax_bar.set_ylim(0, max(valores) * 1.2)
    else:
        ax_bar.set_ylim(0, 5)
        
    ax_bar.tick_params(axis='y', colors='#7F8C8D', labelsize=11, length=0)
    ax_bar.tick_params(axis='x', colors='#34495E', labelsize=11)
    for i, v in enumerate(valores):
        ax_bar.text(i, v + (max(valores)*0.03 if max(valores) > 0 else 0.1), str(v), ha='center', va='bottom', fontsize=13, weight='bold', color='#2C3E50')

    # ==========================================
    # SESSÃO 2: TABELAS DETALHADAS 
    # ==========================================
    
    # 1) Agrupamentos: Vendas por Vendedor
    col_vendedor = next((c for c in df_hoje.columns if c.upper() == 'NOME_VENDEDOR'), None)
    if col_vendedor and not df_hoje.empty:
        vendas_vend = df_hoje.groupby(col_vendedor).size().sort_values(ascending=False)
        vendas_vend = vendas_vend[vendas_vend > 0]
    else:
        vendas_vend = pd.Series(dtype=int)

    # 2) Agrupamentos: Faturamento por Vendedor
    col_vendedor_fat = next((c for c in df_fat.columns if c.upper() == 'NOME_VENDEDOR'), None)
    if col_vendedor_fat and not df_fat.empty:
        faturamento_vend = df_fat.groupby(col_vendedor_fat).size().sort_values(ascending=False)
        faturamento_vend = faturamento_vend[faturamento_vend > 0]
    else:
        faturamento_vend = pd.Series(dtype=int)
        
    # 3) Agrupamentos: Faturamento por Empresa
    col_empresa_fat = next((c for c in df_fat.columns if c.upper() == 'COD_EMPRESA'), None)
    fat_empresa_data = []
    if col_empresa_fat and not df_fat.empty:
        for cod, nome in empresas_map.items():
            qtd = len(df_fat[df_fat[col_empresa_fat].astype(str).str.extract(r'(\d+)', expand=False) == cod])
            if qtd > 0:
                fat_empresa_data.append([nome, qtd])
        fat_empresa_data = sorted(fat_empresa_data, key=lambda x: x[1], reverse=True)

    def formatar_tabela(t, cor_header):
        t.auto_set_font_size(False)
        t.set_fontsize(10)
        t.scale(1, 1.8)
        for key, cell in t.get_celld().items():
            cell.set_edgecolor('#ECF0F1')
            if key[0] == 0:
                cell.set_text_props(weight='bold', color='white', family='sans-serif')
                cell.set_facecolor(cor_header)
            else:
                cell.set_facecolor('white')
                cell.set_text_props(color='#2C3E50', family='sans-serif')

    # DESENHAR TABELA 1
    ax_t1 = fig.add_axes([0.05, 0.05, 0.28, 0.40])
    ax_t1.axis('off')
    ax_t1.set_title("Vendas Vendedor (HOJE)", fontsize=14, weight='bold', color='#2C3E50', pad=10)
    if not vendas_vend.empty:
        cellText1 = [[v[:22], q] for v, q in vendas_vend.items()]
        t1 = ax_t1.table(cellText=cellText1, colLabels=["Vendedor", "Qtd"], colWidths=[0.75, 0.25], loc='upper center', cellLoc='center')
        formatar_tabela(t1, '#3498DB')
    else:
        ax_t1.text(0.5, 0.8, "Nenhuma venda", ha='center', va='center', fontsize=12, color='#7F8C8D')

    # DESENHAR TABELA 2
    ax_t2 = fig.add_axes([0.36, 0.05, 0.28, 0.40])
    ax_t2.axis('off')
    ax_t2.set_title("Faturamento Vendedor (HOJE)", fontsize=14, weight='bold', color='#2C3E50', pad=10)
    if not faturamento_vend.empty:
        cellText2 = [[v[:22], q] for v, q in faturamento_vend.items()]
        t2 = ax_t2.table(cellText=cellText2, colLabels=["Vendedor", "Qtd"], colWidths=[0.75, 0.25], loc='upper center', cellLoc='center')
        formatar_tabela(t2, '#27AE60') # Verde para faturamento
    else:
        ax_t2.text(0.5, 0.8, "Nenhum faturamento", ha='center', va='center', fontsize=12, color='#7F8C8D')

    # DESENHAR TABELA 3
    ax_t3 = fig.add_axes([0.67, 0.05, 0.28, 0.40])
    ax_t3.axis('off')
    ax_t3.set_title("Faturamento Loja (HOJE)", fontsize=14, weight='bold', color='#2C3E50', pad=10)
    if fat_empresa_data:
        t3 = ax_t3.table(cellText=fat_empresa_data, colLabels=["Empresa", "Qtd"], colWidths=[0.75, 0.25], loc='upper center', cellLoc='center')
        formatar_tabela(t3, '#27AE60')
    else:
        ax_t3.text(0.5, 0.8, "Nenhum faturamento", ha='center', va='center', fontsize=12, color='#7F8C8D')

    plt.savefig(CAMINHO_ARQUIVO, format='pdf', bbox_inches='tight')
    plt.close()

@app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_acompanhamento_diretoria(self):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    logger.info(f"Gerando relatorio PDF...")
    try:
        generate_pdf()
    except Exception as exc:
        logger.error(f"Erro ao gerar relatorio PDF: {exc}")
        return {"status": "error", "details": str(exc)}
    
    # Lendo o arquivo uma vez na memória para poder enviar a todos
    try:
        with open(CAMINHO_ARQUIVO, "rb") as arquivo:
            pdf_data = arquivo.read()
    except Exception as exc:
        logger.error(f"Erro ao ler o arquivo PDF gerado: {exc}")
        return {"status": "error", "details": str(exc)}

    resultados = []
    
    for nome, chat_id in TELEGRAM_CHATS.items():
        dados = {
            "chat_id": chat_id,
            "caption": "Aqui está o relatório para acompanhamento de vendas e faturamento Diário."
        }
        
        logger.info(f"Tentando enviar relatorio para {nome} (ID {chat_id})...")
        try:
            # Recriamos a tupla do arquivo para cada request
            arquivos = {"document": ("relatorio_diario.pdf", pdf_data)}
            resposta = requests.post(url, data=dados, files=arquivos, timeout=15)
            if resposta.status_code == 200:
                logger.info(f"✅ Sucesso! Mensagem foi entregue para {nome}.")
                resultados.append({"nome": nome, "status": "success"})
            else:
                logger.error(f"❌ Ops, algo deu errado para {nome}. Detalhes: {resposta.json()}")
                resultados.append({"nome": nome, "status": "error", "details": resposta.json()})
        except Exception as exc:
            logger.error(f"❌ Erro na requisição para {nome}: {exc}")
            resultados.append({"nome": nome, "status": "error", "details": str(exc)})
            
    # Checar se pelo menos um falhou para status final (opcional)
    if any(r.get('status') == 'error' for r in resultados):
        logger.warning(f"Envio concluído com alguns erros: {resultados}")
        return {"status": "partial_success_or_error", "details": resultados}

    return {"status": "success", "details": resultados}
