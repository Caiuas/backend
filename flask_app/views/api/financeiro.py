from io import StringIO, BytesIO
from flask import Blueprint, jsonify, request, send_file
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
import pandas as pd
import xlsxwriter
import re
load_dotenv()

financeiro_bp = Blueprint('financeiro', __name__)

@financeiro_bp.route('/api/financeiro/lcontas', methods=['GET'])
@token_required
def get_financeiro_lcontas():
    try:
        token_data = request.token_data
        email = token_data['email']
        cod_conta_corrente = request.args.get('cod_conta_corrente', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        consiliado = request.args.get('consiliado', None)
        gera_planilha = request.args.get('gera_planilha', 'N').upper() == 'S'
        retorno = {}
        
        query_consiliado = ""
        if consiliado:
            if consiliado.upper() not in ['S', 'N']:
                return jsonify({'status': 'error', 'message': 'Consiliado parameter must be S or N.'}), 400
            if consiliado.upper() == 'S':
                query_consiliado = " AND clc.updated_at IS NOT null"
            else:
                query_consiliado = " AND clc.updated_at IS null"
        
        if not initial_date or not final_date:
            # initial_date e final_date é primeiro e ultimo dia do mês atual
            initial_date = datetime.now().strftime('%Y-%m-%d')#datetime.now().replace(day=1).strftime('%Y-%m-%d')
            final_date = datetime.now().strftime('%Y-%m-%d')
            # return jsonify({'status': 'error', 'message': 'Initial date and final date are required.'}), 400
        
        # checa se initial_date e final_date estão no formato correto YYYY-MM-DD
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not date_pattern.match(initial_date) or not date_pattern.match(final_date):
            return jsonify({'status': 'error', 'message': 'Dates must be in YYYY-MM-DD format.'}), 400
        
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT cod_classificacao, nome FROM caiuas_classificacao
        """
        cur_oracle.execute(query)
        classificacoes = cur_oracle.fetchall()
        dict_classificacoes = []
        for row in classificacoes:
            dict_classificacoes.append({'cod_classificacao': row[0], 'nome': row[1]})
        
        query = f"""
            SELECT cod_centro_custo, nome FROM caiuas_centro_custo
        """
        cur_oracle.execute(query)
        centros_custo = cur_oracle.fetchall()
        dict_centros_custo = []
        for row in centros_custo:
            dict_centros_custo.append({'centro_custo': row[0], 'nome': row[1]})
        
        query = f"""
            SELECT cod_empresa, nome FROM empresas WHERE LOCAL = 'N'
        """
        cur_oracle.execute(query)
        empresas = cur_oracle.fetchall()
        dict_empresas = []
        for row in empresas:
            dict_empresas.append({'cod_empresa': row[0], 'nome': row[1]})
        # query = f"""
        #             SELECT 
        #                 e.COD_EMPRESA, e.nome, lc.COD_CONTA_CORRENTE, cc.DESCRICAO,
        #                 SUM(CASE 
        #                     WHEN lc.db_cr = 'C' THEN lc.valor
        #                     ELSE lc.valor * -1
        #                 END) AS saldo_total
        #             FROM CONTA_CORRENTE cc
        #             LEFT JOIN lcontas lc ON 1=1
        #                 AND cc.COD_EMPRESA = lc.COD_EMPRESA 
        #                 AND cc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
        #             LEFT JOIN empresas e ON 1=1
        #                 AND e.cod_empresa = lc.COD_EMPRESA 
        #             WHERE 1=1
        #                 AND cc.ATIVA = 'S'
        #                 AND TRUNC(lc.data) < TO_DATE('{initial_date}', 'YYYY-MM-DD')
        #             GROUP BY e.COD_EMPRESA, e.nome, lc.COD_CONTA_CORRENTE, cc.DESCRICAO
        # """
        # # return query
        # cur_oracle.execute(query)
        # rows = cur_oracle.fetchall()
        # df_saldos_anteriores = pd.DataFrame(rows, columns=['cod_empresa', 'nome_empresa', 'cod_conta_corrente', 'nome_conta', 'saldo_anterior'], dtype=object)
        

        # cur_oracle.close()
        # conn_oracle.close()
        # return df_saldos_anteriores.to_json(orient='records'), 200

        query = f"""
                SELECT 
                    lc.data,
                    CASE 
                        WHEN clc.cod_empresa_gerencial is NULL THEN lc.COD_EMPRESA
                        ELSE clc.cod_empresa_gerencial
                    END COD_EMPRESA,
                    CASE 
                        WHEN clc.cod_empresa_gerencial is NULL THEN e.nome
                        ELSE e2.NOME
                    END nome,
                    lc.COD_CONTA_CORRENTE,
                    cc.NUM_AGENCIA, 
                    cc.NUM_CONTA, 
                    cc.DESCRICAO nome_conta,
                    lc.LANC,
                    lc.COD_ORIGEM_LANC ,
                    lc.HISTORICO,
                    ol.DESCRICAO origem_lancamento,
                    lc.nome responsavel,
                    CASE 
                        WHEN lc.db_cr = 'C' THEN lc.valor
                        ELSE lc.valor * -1
                    END valor,
                    CASE
                        WHEN clc.updated_at IS NOT NULL THEN 'S'
                        ELSE 'N'
                    END consiliado,
                    clc.cod_classificacao,
                    cac.nome classificacao,
                    clc.cod_centro_custo,
                    ccc.nome centro_custo,
                    lc.COD_EMPRESA cod_empresa_real,
                    clc.nome_cliente,
                    clc.nome_cliente
                FROM lcontas lc
                LEFT JOIN CONTA_CORRENTE cc ON 1=1
                    AND cc.COD_EMPRESA = lc.COD_EMPRESA 
                    AND cc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
                LEFT JOIN OPERACAO_TESOURARIA ot ON 1=1
                    AND ot.COD_OPERACAO_TESOURARIA = lc.COD_OPERACAO_TESOURARIA
                    AND ot.COD_EMPRESA = lc.COD_EMPRESA 
                LEFT JOIN ORIGEM_LANCAMENTO ol ON 1=1
                    AND ol.COD_ORIGEM_LANC = lc.COD_ORIGEM_LANC 
                LEFT JOIN EMPRESAS e ON 1=1
                    AND e.COD_EMPRESA = lc.COD_EMPRESA
                LEFT JOIN caiuas_lcontas clc ON 1=1
                    AND clc.cod_empresa = lc.cod_empresa
                    AND clc.cod_conta_corrente = lc.COD_CONTA_CORRENTE 
                    AND clc.DATA = lc.DATA
                    AND clc.lanc = lc.lanc
                LEFT JOIN empresas e2 ON 1=1
    	            AND e2.COD_EMPRESA = clc.cod_empresa_gerencial
                LEFT JOIN caiuas_centro_custo ccc ON 1=1
    	        	AND ccc.cod_centro_custo = clc.cod_centro_custo
    	        LEFT JOIN caiuas_classificacao cac ON 1=1
    	        	AND cac.cod_classificacao = clc.cod_classificacao
                WHERE 1=1
                    {query_consiliado}
                    AND trunc(lc."DATA") BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
                    AND (lc.COD_EMPRESA, lc.COD_CONTA_CORRENTE) IN (
                        SELECT ucc.COD_EMPRESA, ucc.COD_CONTA_CORRENTE 
                        FROM usuario_conta_corrente ucc
                        LEFT JOIN EMPRESAS_USUARIOS eu ON ucc.USUARIO = eu.NOME 
                        WHERE 1=1
                        and lc.cod_conta_corrente not in (2,3,7,424)
                        and lower(eu.email) = '{email.lower()}'
                    )
                    ORDER BY lc.COD_CONTA_CORRENTE, lc."DATA"  DESC
        """
        cur_oracle.execute(query)
        lancamentos = cur_oracle.fetchall()
        df_lancamentos = pd.DataFrame(lancamentos, columns=['data','cod_empresa', 'nome', 'cod_conta_corrente', 'num_agencia', 'num_conta', 'nome_conta', 'num_lanc', 'cod_origem_lanc', 'historico', 'origem_lancamento', 'responsavel', 'valor', 'consiliado', 'cod_classificacao', 'classificacao', 'cod_centro_custo', 'centro_custo', 'cod_empresa_real', 'cliente','nome_cliente_conciliado'], dtype=object)

        query = f"""
            SELECT 
                COD_EMPRESA,
                COD_CONTA_CORRENTE,
                LANC, 
                data,
                NOME  
            FROM (
                SELECT 
                    bc.COD_EMPRESA,
                    bc.COD_CONTA_CORRENTE,
                    bc.LANC, 
                    c3.NOME,
                    bc.data,
                    ROW_NUMBER() OVER (
                        PARTITION BY bc.COD_EMPRESA, bc.COD_CONTA_CORRENTE, bc.LANC 
                        ORDER BY bc.LANCAMENTO DESC, bc.PARCELA DESC
                    ) as rn
                FROM BAIXA_CONTA_PAGAR bc
                LEFT JOIN CONTA_PAGAR cp ON 
                    cp.LANCAMENTO = bc.LANCAMENTO 
                    AND cp.COD_EMPRESA = bc.COD_EMPRESA 
                    AND cp.ANO_PPAG = bc.ANO_PPAG 
                    AND cp.PARCELA = bc.PARCELA 
                    AND cp.PARCIAL = bc.PARCIAL 
                LEFT JOIN clientes c3 ON 
                    c3.COD_CLIENTE = cp.COD_CLIENTE 
                WHERE TRUNC(bc."DATA") >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(bc."DATA") <= TO_DATE('{final_date}', 'YYYY-MM-DD')
            )
            WHERE rn = 1
        """
        cur_oracle.execute(query)
        baixas = cur_oracle.fetchall()
        df_baixas = pd.DataFrame(baixas, columns=['cod_empresa', 'cod_conta_corrente', 'num_lanc','data', 'cliente'], dtype=object)

        query = f"""
            SELECT 
                COD_EMPRESA_BAIXA,
                COD_CONTA_BAIXA,
                LANC_BAIXA,
                DATA_BAIXA,
                nome
            FROM (
                SELECT 
                    ba.COD_EMPRESA_BAIXA,
                    ba.COD_CONTA_BAIXA,
                    ba.LANC_BAIXA,
                    ba.DATA_BAIXA,
                    c3.nome,
                    ROW_NUMBER() OVER (
                        PARTITION BY ba.COD_EMPRESA_BAIXA, ba.COD_CONTA_BAIXA, ba.LANC_BAIXA, TRUNC(ba.DATA_BAIXA)
                        ORDER BY ba.LANC DESC
                    ) as rn
                FROM BAIXA_ADIANTAMENTO ba 
                LEFT JOIN ADIANTAMENTO a ON 
                    a.COD_EMPRESA = ba.COD_EMPRESA
                    AND a.COD_CONTA_CORRENTE = ba.COD_CONTA_CORRENTE
                    AND a."DATA" = ba."DATA" 
                    AND a.LANC = ba.LANC
                LEFT JOIN CLIENTES c3 ON 
                    c3.COD_CLIENTE = a.COD_CLIENTE
                WHERE TRUNC(ba.DATA_BAIXA) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(ba.DATA_BAIXA) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
            )
            WHERE rn = 1
        """
        cur_oracle.execute(query)
        baixas_adiantamentos = cur_oracle.fetchall()
        df_baixas_adiantamentos = pd.DataFrame(baixas_adiantamentos, columns=['cod_empresa', 'cod_conta_corrente', 'num_lanc', 'data', 'cliente'], dtype=object)

        query = f"""
            SELECT v.COD_EMPRESA, vc."DATA", vc.LANC, c.NOME , vc.COD_CONTA_CORRENTE
            FROM VENDAS_CAIXA vc 
            LEFT JOIN vendas v ON 1=1
                AND v.CONTROLE = vc.CONTROLE 
                AND v.SERIE = vc.SERIE 
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = v.COD_CLIENTE
            WHERE TRUNC(vc.DATA) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(vc.DATA) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        vendas_caixa = cur_oracle.fetchall()
        df_vendas_caixa = pd.DataFrame(vendas_caixa, columns=['cod_empresa', 'data', 'num_lanc', 'cliente', 'cod_conta_corrente'], dtype=object)
        cur_oracle.close()
        conn_oracle.close()
        # converte para data nesse formato 2025-11-06 00:00:00
        df_vendas_caixa['data'] = pd.to_datetime(df_vendas_caixa['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_baixas_adiantamentos['data'] = pd.to_datetime(df_baixas_adiantamentos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_baixas['data'] = pd.to_datetime(df_baixas['data']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # une df_lancamentos se cod_origem_lancamento for 7 une com df_vendas_caixa
        # df_lancamentos = df_lancamentos.merge(
        # df_vendas_caixa[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
        #     how='left', 
        #     on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc']
        # )
        
        df_lancamentos = df_lancamentos.merge(
            df_baixas[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_baixa')
        )

        df_lancamentos = df_lancamentos.merge(
            df_baixas_adiantamentos[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_baixa_adiantamento')
        )

        df_lancamentos = df_lancamentos.merge(
            df_vendas_caixa[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_venda')
        )

        df_lancamentos['nome_cliente'] = df_lancamentos['cliente_venda'].combine_first(
        df_lancamentos['cliente_baixa_adiantamento']
        ).combine_first(df_lancamentos['cliente'])

        # Remove as colunas individuais de cliente
        df_lancamentos.drop(columns=['cliente', 'cliente_baixa_adiantamento', 'cliente_venda'], inplace=True, errors='ignore')
        # fill na para None
        df_lancamentos['nome_cliente'] = df_lancamentos['nome_cliente'].replace({pd.NA: None, float('nan'): None})
        
        # transforma a data em iso format
        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # se nome_cliente_consiliado não for nulo atualize 'cliente' com esse valor
        df_lancamentos['nome_cliente'] = df_lancamentos.apply(
            lambda row: row['nome_cliente_conciliado'] if pd.notna(row['nome_cliente_conciliado']) else row['nome_cliente'], 
            axis=1
        )

        # Atualiza responsavel com cliente apenas quando cod_origem_lanc = 7 e cliente não é nulo
        # df_lancamentos.loc[
        #     (df_lancamentos['cod_origem_lanc'] == 7) & (df_lancamentos['cliente'].notna()), 
        #     'responsavel'
        # ] = df_lancamentos['cliente']

        # df_lancamentos.drop(columns=['cliente'], inplace=True, errors='ignore')
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        if gera_planilha:
            # gera planilha excel em memória
            filename = f'contas_{now}.xlsx'
            
            # Cria um buffer de memória
            buffer = BytesIO()
            
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # df_saldos_anteriores.to_excel(writer, sheet_name='Saldos Anteriores', index=False)
                df_lancamentos.to_excel(writer, sheet_name='Lançamentos', index=False)
                df_baixas.to_excel(writer, sheet_name='Baixas', index=False)
                df_baixas_adiantamentos.to_excel(writer, sheet_name='Baixas e Adiantamentos', index=False)
                df_vendas_caixa.to_excel(writer, sheet_name='Vendas em Caixa', index=False)
            
            # Move o ponteiro para o início do buffer
            buffer.seek(0)
            
            # Retorna o arquivo direto da memória
            return send_file(
                buffer, 
                as_attachment=True, 
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        retorno = {
            # 'saldos_anteriores': df_saldos_anteriores.to_dict(orient='records'),
            'lancamentos': df_lancamentos.to_dict(orient='records'),
            'classificacoes': dict_classificacoes,
            'centros_custo': dict_centros_custo,
            'empresas': dict_empresas,
        }

        return jsonify(retorno), 200

        retorno = {
            'saldos_anteriores': df_saldos_anteriores.to_dict(orient='records'),
            'lancamentos': df_lancamentos.to_dict(orient='records'),
        }


        return jsonify(retorno), 200

    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
            
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@financeiro_bp.route('/api/financeiro/download_lcontas', methods=['GET'])
@token_required
def get_financeiro_download_lcontas():
    try:
        token_data = request.token_data
        email = token_data['email']
        cod_conta_corrente = request.args.get('cod_conta_corrente', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        consiliado = request.args.get('consiliado', None)
        gera_planilha = request.args.get('gera_planilha', 'N').upper() == 'S'
        usuarios_autorizados = [
            'pablo.ti@caiuas.com.br',
            'marcelotcf@caiuas.com.br',
            'amelise.teixeira@caiuas.com.br',
            'zenilda@caiuas.com.br',
            'ricardo.camargo@caiuas.com.br',
            'vanessa.vilela@caiuas.com.br'
            ]
        
        if email.lower() not in usuarios_autorizados:
            return jsonify({'status': 'error', 'message': 'Usuário não autorizado.'}), 403
        retorno = {}
        
        de_para = [
                    {'nome_conta_original': 'Banco Bradesco AG 3372 Aplicacao 11400-6', 'nome_conta_novo': 'Banco Bradesco AG 3372 Aplicacao 11400-6'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 Aplicação 11221-6', 'nome_conta_novo': 'Banco Bradesco AG 3372 Aplicação 11221-6'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 C/C -11400-6', 'nome_conta_novo': 'Indmar Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 C/C 11221-6', 'nome_conta_novo': 'Camargo Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 CC 11601-7', 'nome_conta_novo': 'Corretora Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 CC 1227-0', 'nome_conta_novo': 'L.L.A. Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco AG 3372 Garantida 11220-8', 'nome_conta_novo': 'Camargo Bradesco Vinculada'},
                    {'nome_conta_original': 'Banco Bradesco Aplicação CC 1227-0', 'nome_conta_novo': 'Banco Bradesco Aplicação CC 1227-0'},
                    {'nome_conta_original': 'Banco Bradesco C/C - 185200-0', 'nome_conta_novo': 'Carmaf Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C - 185400-3', 'nome_conta_novo': 'Caiupar Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C -11223-2', 'nome_conta_novo': 'Motos Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C / 11200-3', 'nome_conta_novo': 'Deck Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C / 185500-0', 'nome_conta_novo': 'Granfort Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C 11.224-0', 'nome_conta_novo': 'ITA Bradesco'},
                    {'nome_conta_original': 'Banco Bradesco C/C 185300-7', 'nome_conta_novo': 'Auto Nautica Bradesco'},
                    {'nome_conta_original': 'Banco CEF AG 0367 CC 1292 577076686-3', 'nome_conta_novo': 'Corretora Caixa'},
                    {'nome_conta_original': 'Banco CEF AG 0367 CC 577321333-4', 'nome_conta_novo': 'Laymar Caixa'},
                    {'nome_conta_original': 'Banco CEF AG 0367 OP 1292 CC 577271488-7', 'nome_conta_novo': 'Camargo Caixa'},
                    {'nome_conta_original': 'Banco CEF AG 0367 OP 1292 CC 577271489-5', 'nome_conta_novo': 'Indmar Caixa'},
                    {'nome_conta_original': 'Banco CEF AG 0367 OP 1292 CC 577271491-7', 'nome_conta_novo': 'Akla Caixa'},
                    {'nome_conta_original': 'Banco CEF AG 0367 OP 1292 CC 579270868-8', 'nome_conta_novo': 'L.L.A. Caixa Nova'},
                    {'nome_conta_original': 'Banco Daycoval AG 0001-9 CC 732461-0', 'nome_conta_novo': 'Indcar Daycoval'},
                    {'nome_conta_original': 'Banco Daycoval CASH 612212-6', 'nome_conta_novo': 'Camargo Daycoval Garantida 2'},
                    {'nome_conta_original': 'Banco Daycoval CASH 612848-5', 'nome_conta_novo': 'LLA Daycoval Garantida'},
                    {'nome_conta_original': 'Banco Daycoval CC 1513930-3', 'nome_conta_novo': 'Indmar Daycoval CC'},
                    {'nome_conta_original': 'Banco Daycoval CC 151661-3', 'nome_conta_novo': 'Camargo Daycoval CC'},
                    {'nome_conta_original': 'Banco Daycoval CC 721150-5', 'nome_conta_novo': 'L.L.A. Daycoval'},
                    {'nome_conta_original': 'Banco Daycoval GARANTIDA 911131-1', 'nome_conta_novo': 'Camargo Daycoval Garantida'},
                    {'nome_conta_original': 'Banco Daycoval Garantida 612665-2', 'nome_conta_novo': 'Indmar Daycoval Garantida'},
                    {'nome_conta_original': 'Banco Itau AG 0513 CC 55381-8', 'nome_conta_novo': 'Camargo Itaú'},
                    {'nome_conta_original': 'Banco Itaú AG 0513 CC 98739-6', 'nome_conta_novo': 'L.L.A. Itaú'},
                    {'nome_conta_original': 'Banco Safra AG 0041 CC 23941-1', 'nome_conta_novo': 'Camargo Safra'},
                    {'nome_conta_original': 'Banco Safra AG 0041 CC 29119-6', 'nome_conta_novo': 'Indmar Safra'},
                    {'nome_conta_original': 'Banco Safra AG 0041 CC 585593-4', 'nome_conta_novo': 'L.L.A. SAFRA'},
                    {'nome_conta_original': 'Banco Safra Aplicação / 23941-1', 'nome_conta_novo': 'Banco Safra Aplicação / 23941-1'},
                    {'nome_conta_original': 'Banco Safra Vinculada 8791970 E 1846957', 'nome_conta_novo': 'Camargo Safra Vinculada'},
                    {'nome_conta_original': 'Banco Sofisa AG 00426 Corrente 9740', 'nome_conta_novo': 'Indmar Sofisa'},
                    {'nome_conta_original': 'Banco Sofisa AG 00426 Vinculada 9758', 'nome_conta_novo': 'Indmar Sofisa Vinculada'},
                    {'nome_conta_original': 'Banco Sofisa Aplicação CC 10420', 'nome_conta_novo': 'Banco Sofisa Aplicação CC 10420'},
                    {'nome_conta_original': 'Banco Sofisa CC 1042-0', 'nome_conta_novo': 'L.L.A. Sofisa'},
                    {'nome_conta_original': 'Banco Sofisa Cheque Empresa CC 11426', 'nome_conta_novo': 'Indmar Sofisa Cheque Empresa'},
                    {'nome_conta_original': 'Banco do Brasil  Aplicação CC 74918-4', 'nome_conta_novo': 'L.L.A BB Garantida'},
                    {'nome_conta_original': 'Banco do Brasil CC 74918-4', 'nome_conta_novo': 'L.L.A BB'},
                    {'nome_conta_original': 'C/C Honda 1018523', 'nome_conta_novo': 'C/C Honda 1018523'},
                    {'nome_conta_original': 'C/C Honda 1614562', 'nome_conta_novo': 'C/C Honda 1614562'},
                    {'nome_conta_original': 'Caixa Caiuas-CX9999', 'nome_conta_novo': 'Caixa Caiuas-CX9999'},
                    {'nome_conta_original': 'Caixa operacional', 'nome_conta_novo': 'Caixa operacional'},
                    {'nome_conta_original': 'Tesouraria - Matriz', 'nome_conta_novo': 'Tesouraria - Matriz'},
                    {'nome_conta_original': 'Transitoria', 'nome_conta_novo': 'Transitoria'},
                    {'nome_conta_original': 'Transitoria - Matriz', 'nome_conta_novo': 'Transitoria - Matriz'},
                    {'nome_conta_original': 'Transitoria -Matriz', 'nome_conta_novo': 'Transitoria -Matriz'},
                    {'nome_conta_original': 'Transitória', 'nome_conta_novo': 'Transitória'},
                    {'nome_conta_original': 'Transitória - HL', 'nome_conta_novo': 'Transitória - HL'}
        ]

        query_consiliado = ""
        if consiliado:
            if consiliado.upper() not in ['S', 'N']:
                return jsonify({'status': 'error', 'message': 'Consiliado parameter must be S or N.'}), 400
            if consiliado.upper() == 'S':
                query_consiliado = " AND clc.updated_at IS NOT null"
            else:
                query_consiliado = " AND clc.updated_at IS null"
        
        if not initial_date or not final_date:
            # initial_date e final_date é primeiro e ultimo dia do mês atual
            initial_date = datetime.now().strftime('%Y-%m-%d')#datetime.now().replace(day=1).strftime('%Y-%m-%d')
            final_date = datetime.now().strftime('%Y-%m-%d')
            # return jsonify({'status': 'error', 'message': 'Initial date and final date are required.'}), 400
        
        # checa se initial_date e final_date estão no formato correto YYYY-MM-DD
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not date_pattern.match(initial_date) or not date_pattern.match(final_date):
            return jsonify({'status': 'error', 'message': 'Dates must be in YYYY-MM-DD format.'}), 400
        
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT cod_classificacao, nome FROM caiuas_classificacao
        """
        cur_oracle.execute(query)
        classificacoes = cur_oracle.fetchall()
        dict_classificacoes = []
        for row in classificacoes:
            dict_classificacoes.append({'cod_classificacao': row[0], 'nome': row[1]})
        
        query = f"""
            SELECT cod_centro_custo, nome FROM caiuas_centro_custo
        """
        cur_oracle.execute(query)
        centros_custo = cur_oracle.fetchall()
        dict_centros_custo = []
        for row in centros_custo:
            dict_centros_custo.append({'centro_custo': row[0], 'nome': row[1]})
        
        query = f"""
            SELECT cod_empresa, nome FROM empresas WHERE LOCAL = 'N'
        """
        cur_oracle.execute(query)
        empresas = cur_oracle.fetchall()
        dict_empresas = []
        for row in empresas:
            dict_empresas.append({'cod_empresa': row[0], 'nome': row[1]})
        # query = f"""
        #             SELECT 
        #                 e.COD_EMPRESA, e.nome, lc.COD_CONTA_CORRENTE, cc.DESCRICAO,
        #                 SUM(CASE 
        #                     WHEN lc.db_cr = 'C' THEN lc.valor
        #                     ELSE lc.valor * -1
        #                 END) AS saldo_total
        #             FROM CONTA_CORRENTE cc
        #             LEFT JOIN lcontas lc ON 1=1
        #                 AND cc.COD_EMPRESA = lc.COD_EMPRESA 
        #                 AND cc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
        #             LEFT JOIN empresas e ON 1=1
        #                 AND e.cod_empresa = lc.COD_EMPRESA 
        #             WHERE 1=1
        #                 AND cc.ATIVA = 'S'
        #                 AND TRUNC(lc.data) < TO_DATE('{initial_date}', 'YYYY-MM-DD')
        #             GROUP BY e.COD_EMPRESA, e.nome, lc.COD_CONTA_CORRENTE, cc.DESCRICAO
        # """
        # # return query
        # cur_oracle.execute(query)
        # rows = cur_oracle.fetchall()
        # df_saldos_anteriores = pd.DataFrame(rows, columns=['cod_empresa', 'nome_empresa', 'cod_conta_corrente', 'nome_conta', 'saldo_anterior'], dtype=object)
        

        # cur_oracle.close()
        # conn_oracle.close()
        # return df_saldos_anteriores.to_json(orient='records'), 200

        query = f"""
                SELECT 
                    lc.data,
                    CASE 
                        WHEN clc.cod_empresa_gerencial is NULL THEN lc.COD_EMPRESA
                        ELSE clc.cod_empresa_gerencial
                    END COD_EMPRESA,
                    CASE 
                        WHEN clc.cod_empresa_gerencial is NULL THEN e.nome
                        ELSE e2.NOME
                    END nome,
                    lc.COD_CONTA_CORRENTE,
                    cc.NUM_AGENCIA, 
                    cc.NUM_CONTA, 
                    cc.DESCRICAO nome_conta,
                    lc.LANC,
                    lc.COD_ORIGEM_LANC ,
                    lc.HISTORICO,
                    ol.DESCRICAO origem_lancamento,
                    lc.nome responsavel,
                    CASE 
                        WHEN lc.db_cr = 'C' THEN lc.valor
                        ELSE lc.valor * -1
                    END valor,
                    CASE
                        WHEN clc.updated_at IS NOT NULL THEN 'S'
                        ELSE 'N'
                    END consiliado,
                    clc.cod_classificacao,
                    cac.nome classificacao,
                    clc.cod_centro_custo,
                    ccc.nome centro_custo,
                    lc.COD_EMPRESA cod_empresa_real,
                    clc.nome_cliente,
                    clc.nome_cliente,
                    clc.updated_at
                FROM lcontas lc
                LEFT JOIN CONTA_CORRENTE cc ON 1=1
                    AND cc.COD_EMPRESA = lc.COD_EMPRESA 
                    AND cc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
                LEFT JOIN OPERACAO_TESOURARIA ot ON 1=1
                    AND ot.COD_OPERACAO_TESOURARIA = lc.COD_OPERACAO_TESOURARIA
                    AND ot.COD_EMPRESA = lc.COD_EMPRESA 
                LEFT JOIN ORIGEM_LANCAMENTO ol ON 1=1
                    AND ol.COD_ORIGEM_LANC = lc.COD_ORIGEM_LANC 
                LEFT JOIN EMPRESAS e ON 1=1
                    AND e.COD_EMPRESA = lc.COD_EMPRESA
                LEFT JOIN caiuas_lcontas clc ON 1=1
                    AND clc.cod_empresa = lc.cod_empresa
                    AND clc.cod_conta_corrente = lc.COD_CONTA_CORRENTE 
                    AND clc.DATA = lc.DATA
                    AND clc.lanc = lc.lanc
                LEFT JOIN empresas e2 ON 1=1
    	            AND e2.COD_EMPRESA = clc.cod_empresa_gerencial
                LEFT JOIN caiuas_centro_custo ccc ON 1=1
    	        	AND ccc.cod_centro_custo = clc.cod_centro_custo
    	        LEFT JOIN caiuas_classificacao cac ON 1=1
    	        	AND cac.cod_classificacao = clc.cod_classificacao
                WHERE 1=1
                    {query_consiliado}
                    AND trunc(lc."DATA") BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
                    ORDER BY lc.COD_CONTA_CORRENTE, lc."DATA"  DESC
        """
        cur_oracle.execute(query)
        lancamentos = cur_oracle.fetchall()
        df_lancamentos = pd.DataFrame(lancamentos, columns=['data','cod_empresa', 'nome', 'cod_conta_corrente', 'num_agencia', 'num_conta', 'nome_conta', 'num_lanc', 'cod_origem_lanc', 'historico', 'origem_lancamento', 'responsavel', 'valor', 'consiliado', 'cod_classificacao', 'classificacao', 'cod_centro_custo', 'centro_custo', 'cod_empresa_real', 'cliente','nome_cliente_conciliado','updated_at'], dtype=object)
        # if not null 'S' else 'N'
        df_lancamentos['consiliado'] = df_lancamentos['updated_at'].apply(lambda x: 'S' if pd.notna(x) else 'N')
        query = f"""
            SELECT 
                COD_EMPRESA,
                COD_CONTA_CORRENTE,
                LANC, 
                data,
                NOME  
            FROM (
                SELECT 
                    bc.COD_EMPRESA,
                    bc.COD_CONTA_CORRENTE,
                    bc.LANC, 
                    c3.NOME,
                    bc.data,
                    ROW_NUMBER() OVER (
                        PARTITION BY bc.COD_EMPRESA, bc.COD_CONTA_CORRENTE, bc.LANC 
                        ORDER BY bc.LANCAMENTO DESC, bc.PARCELA DESC
                    ) as rn
                FROM BAIXA_CONTA_PAGAR bc
                LEFT JOIN CONTA_PAGAR cp ON 
                    cp.LANCAMENTO = bc.LANCAMENTO 
                    AND cp.COD_EMPRESA = bc.COD_EMPRESA 
                    AND cp.ANO_PPAG = bc.ANO_PPAG 
                    AND cp.PARCELA = bc.PARCELA 
                    AND cp.PARCIAL = bc.PARCIAL 
                LEFT JOIN clientes c3 ON 
                    c3.COD_CLIENTE = cp.COD_CLIENTE 
                WHERE TRUNC(bc."DATA") >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(bc."DATA") <= TO_DATE('{final_date}', 'YYYY-MM-DD')
            )
            WHERE rn = 1
        """
        cur_oracle.execute(query)
        baixas = cur_oracle.fetchall()
        df_baixas = pd.DataFrame(baixas, columns=['cod_empresa', 'cod_conta_corrente', 'num_lanc','data', 'cliente'], dtype=object)

        query = f"""
            SELECT 
                COD_EMPRESA_BAIXA,
                COD_CONTA_BAIXA,
                LANC_BAIXA,
                DATA_BAIXA,
                nome
            FROM (
                SELECT 
                    ba.COD_EMPRESA_BAIXA,
                    ba.COD_CONTA_BAIXA,
                    ba.LANC_BAIXA,
                    ba.DATA_BAIXA,
                    c3.nome,
                    ROW_NUMBER() OVER (
                        PARTITION BY ba.COD_EMPRESA_BAIXA, ba.COD_CONTA_BAIXA, ba.LANC_BAIXA, TRUNC(ba.DATA_BAIXA)
                        ORDER BY ba.LANC DESC
                    ) as rn
                FROM BAIXA_ADIANTAMENTO ba 
                LEFT JOIN ADIANTAMENTO a ON 
                    a.COD_EMPRESA = ba.COD_EMPRESA
                    AND a.COD_CONTA_CORRENTE = ba.COD_CONTA_CORRENTE
                    AND a."DATA" = ba."DATA" 
                    AND a.LANC = ba.LANC
                LEFT JOIN CLIENTES c3 ON 
                    c3.COD_CLIENTE = a.COD_CLIENTE
                WHERE TRUNC(ba.DATA_BAIXA) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(ba.DATA_BAIXA) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
            )
            WHERE rn = 1
        """
        cur_oracle.execute(query)
        baixas_adiantamentos = cur_oracle.fetchall()
        df_baixas_adiantamentos = pd.DataFrame(baixas_adiantamentos, columns=['cod_empresa', 'cod_conta_corrente', 'num_lanc', 'data', 'cliente'], dtype=object)

        query = f"""
            SELECT v.COD_EMPRESA, vc."DATA", vc.LANC, c.NOME , vc.COD_CONTA_CORRENTE
            FROM VENDAS_CAIXA vc 
            LEFT JOIN vendas v ON 1=1
                AND v.CONTROLE = vc.CONTROLE 
                AND v.SERIE = vc.SERIE 
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = v.COD_CLIENTE
            WHERE TRUNC(vc.DATA) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(vc.DATA) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        vendas_caixa = cur_oracle.fetchall()
        df_vendas_caixa = pd.DataFrame(vendas_caixa, columns=['cod_empresa', 'data', 'num_lanc', 'cliente', 'cod_conta_corrente'], dtype=object)
        cur_oracle.close()
        conn_oracle.close()
        # converte para data nesse formato 2025-11-06 00:00:00
        df_vendas_caixa['data'] = pd.to_datetime(df_vendas_caixa['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_baixas_adiantamentos['data'] = pd.to_datetime(df_baixas_adiantamentos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_baixas['data'] = pd.to_datetime(df_baixas['data']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # une df_lancamentos se cod_origem_lancamento for 7 une com df_vendas_caixa
        # df_lancamentos = df_lancamentos.merge(
        # df_vendas_caixa[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
        #     how='left', 
        #     on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc']
        # )
        
        df_lancamentos = df_lancamentos.merge(
            df_baixas[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_baixa')
        )

        df_lancamentos = df_lancamentos.merge(
            df_baixas_adiantamentos[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_baixa_adiantamento')
        )

        df_lancamentos = df_lancamentos.merge(
            df_vendas_caixa[['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc', 'cliente']], 
            how='left', 
            on=['cod_empresa', 'cod_conta_corrente', 'data', 'num_lanc'],
            suffixes=('', '_venda')
        )

        df_lancamentos['nome_cliente'] = df_lancamentos['cliente_venda'].combine_first(
        df_lancamentos['cliente_baixa_adiantamento']
        ).combine_first(df_lancamentos['cliente'])

        # Remove as colunas individuais de cliente
        df_lancamentos.drop(columns=['cliente', 'cliente_baixa_adiantamento', 'cliente_venda'], inplace=True, errors='ignore')
        # fill na para None
        df_lancamentos['nome_cliente'] = df_lancamentos['nome_cliente'].replace({pd.NA: None, float('nan'): None})
        
        # transforma a data em iso format
        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # se nome_cliente_consiliado não for nulo atualize 'cliente' com esse valor
        df_lancamentos['nome_cliente'] = df_lancamentos.apply(
            lambda row: row['nome_cliente_conciliado'] if pd.notna(row['nome_cliente_conciliado']) else row['nome_cliente'], 
            axis=1
        )

        # Atualiza responsavel com cliente apenas quando cod_origem_lanc = 7 e cliente não é nulo
        # df_lancamentos.loc[
        #     (df_lancamentos['cod_origem_lanc'] == 7) & (df_lancamentos['cliente'].notna()), 
        #     'responsavel'
        # ] = df_lancamentos['cliente']

        # muda nome do nome_conta usando o de_para
        for item in de_para:
            df_lancamentos.loc[
                df_lancamentos['nome_conta'] == item['nome_conta_original'], 
                'nome_conta'
            ] = item['nome_conta_novo']


        # df_lancamentos.drop(columns=['cliente'], inplace=True, errors='ignore')
        df_lancamentos['mes_ano'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%m/%Y')
        df_lancamentos = df_lancamentos[['data','valor','classificacao','centro_custo','historico','nome_cliente','mes_ano','nome_conta','nome','consiliado']]
        # renomeia coluna nome para nome_empresa
        df_lancamentos.rename(columns={'nome': 'nome_empresa'}, inplace=True)
        # converte data para o formato dd/mm/yyyy
        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data']).dt.strftime('%d/%m/%Y')
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        df_controle = pd.pivot_table(
            df_lancamentos,
            index=['nome_conta'],
            columns=['consiliado'],
            values='valor',
            aggfunc='count',
            fill_value=0
            )
        if gera_planilha:
            filename = f'contas_{now}.xlsx'
            buffer = BytesIO()
            
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Primeiro cria o sheet de controle
                df_controle.to_excel(writer, sheet_name='Controle de Conciliação')
                
                # Depois os outros sheets
                df_lancamentos.to_excel(writer, sheet_name='Consolidados', index=False)
                for nome_conta in df_lancamentos['nome_conta'].unique():
                    if pd.notna(nome_conta):
                        df_conta = df_lancamentos[df_lancamentos['nome_conta'] == nome_conta]
                        sheet_name = re.sub(r'[\\/*?:\[\]]', '_', str(nome_conta))[:31]
                        df_conta.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Formatação
                workbook = writer.book
                date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                # date_format = workbook.add_format({'border': 1, 'bg_color': 'white', 'num_format': 'dd/mm/yyyy', 'font_size': 14, 'valign': 'vcenter'})
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    # date_format = workbook.add_format({'border': 1, 'bg_color': 'white', 'num_format': 'dd/mm/yyyy', 'font_size': 14, 'valign': 'vcenter'})
                    if sheet_name != 'Controle de Conciliação':
                        max_row, max_col = worksheet.dim_rowmax, worksheet.dim_colmax
                        worksheet.add_table(0, 0, max_row, max_col, {'columns': [{'header': col} for col in df_lancamentos.columns]})
                        # worksheet.set_column(0, 0, 18.14, add_format={'num_format': 'yyyy-mm-dd'})
                        worksheet.set_column(0, 0, 18.14, date_format)
                        # worksheet.add_format({'num_format': 'yyyy-mm-dd'})
                        worksheet.set_column(1, 1, 9)
                        worksheet.set_column(2, 2, 35)
                        worksheet.set_column(3, 3, 14)
                        worksheet.set_column(4, 4, 54)
                        worksheet.set_column(5, 5, 64)
                        worksheet.set_column(7, 7, None, None, {'hidden': True})
                    
                    
            
            # Move o ponteiro para o início do buffer
            buffer.seek(0)
            
            # Retorna o arquivo direto da memória
            return send_file(
                buffer, 
                as_attachment=True, 
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        retorno = {
            # 'saldos_anteriores': df_saldos_anteriores.to_dict(orient='records'),
            'lancamentos': df_lancamentos.to_dict(orient='records'),
            'classificacoes': dict_classificacoes,
            'centros_custo': dict_centros_custo,
            'empresas': dict_empresas,
        }

        return jsonify(retorno), 200

        retorno = {
            'saldos_anteriores': df_saldos_anteriores.to_dict(orient='records'),
            'lancamentos': df_lancamentos.to_dict(orient='records'),
        }


        return jsonify(retorno), 200

    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
            
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@financeiro_bp.route('/api/financeiro/remove_conciliacao_lcontas', methods=['POST'])
@token_required
def remove_conciliacao_lcontas():
    try:
        token_data = request.token_data
        email = token_data['email']
        dados = request.get_json()
        cod_empresa = dados.get('cod_empresa', None)
        cod_conta_corrente = dados.get('cod_conta_corrente', None)
        lanc = dados.get('lanc', None)
        data = dados.get('data', None)
        if not cod_empresa or not cod_conta_corrente or not lanc or not data:
            return jsonify({'status': 'error', 'message': 'cod_empresa, cod_conta_corrente, lanc and data are required.'}), 400
        conn_oracle, cur_oracle = oracle()
        query = f"""
            select count(*) from caiuas_lcontas 
            where cod_empresa = {cod_empresa}
                and cod_conta_corrente = {cod_conta_corrente}
                and cod_empresa = {cod_empresa}
                and lanc = {lanc}
                and data = TO_DATE('{data}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()
        count = row[0]
        if count == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Lançamento não conciliado.'}), 400
        query = f"""
            DELETE FROM caiuas_lcontas 
            WHERE cod_empresa = {cod_empresa}
                AND cod_conta_corrente = {cod_conta_corrente}
                AND lanc = {lanc}
                AND data = TO_DATE('{data}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Lançamento removido com sucesso.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@financeiro_bp.route('/api/financeiro/adiciona_conciliacao', methods=['POST'])
@token_required
def adiciona_conciliacao_lcontas():
    try:
        dados = request.get_json()
        token_data = request.token_data
        email = token_data['email']
        cod_empresa = dados.get('cod_empresa', None)
        cod_conta_corrente = dados.get('cod_conta_corrente', None)
        lanc = dados.get('lanc', None)
        data = dados.get('data', None)
        cod_centro_custo = dados.get('cod_centro_custo', None)
        cod_classificacao = dados.get('cod_classificacao', None)
        cod_empresa_gerencial = dados.get('cod_empresa_gerencial', None)
        nome_cliente = dados.get('nome_cliente', None)
        
        if not cod_empresa or not cod_conta_corrente or not lanc or not data:
            return jsonify({'status': 'error', 'message': 'cod_empresa, cod_conta_corrente, lanc and data are required.'}), 400
        conn_oracle, cur_oracle = oracle()
        query = f"""
            select count(*) from lcontas lc
            where cod_empresa = {cod_empresa}
                and cod_conta_corrente = {cod_conta_corrente}
                and lanc = {lanc}
                and data = TO_DATE('{data}', 'YYYY-MM-DD')
                AND (lc.COD_EMPRESA, lc.COD_CONTA_CORRENTE) IN (
                        SELECT ucc.COD_EMPRESA, ucc.COD_CONTA_CORRENTE 
                        FROM usuario_conta_corrente ucc
                        LEFT JOIN EMPRESAS_USUARIOS eu ON ucc.USUARIO = eu.NOME 
                        WHERE lower(eu.email) = '{email.lower()}'
                    )
                    """
        
        cur_oracle.execute(query)   
        row = cur_oracle.fetchone()
        count = row[0]
        if count == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Lançamento não encontrado ou acesso negado.'}), 400
        query = f"""
            delete from caiuas_lcontas 
            where cod_empresa = {cod_empresa}
                and cod_conta_corrente = {cod_conta_corrente}
                and lanc = {lanc}
                and data = TO_DATE('{data}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        
        query = f"""
                INSERT INTO caiuas_lcontas (
                    cod_empresa, 
                    cod_conta_corrente, 
                    DATA, lanc, 
                    cod_empresa_gerencial, 
                    cod_centro_custo, 
                    cod_classificacao, 
                    updated_at,
                    nome_cliente)
                VALUES (
                    {cod_empresa},
                    {cod_conta_corrente},
                    TO_DATE('{data}','YYYY-MM-DD'),
                    {lanc}, 
                    {cod_empresa_gerencial}, 
                    {cod_centro_custo}, 
                    {cod_classificacao},
                    SYSTIMESTAMP,
                    '{nome_cliente}')
        """
        query = query.replace("'None'", "NULL")
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Lançamento conciliado com sucesso.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    