from flask import Blueprint, jsonify, request, Response
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd
import io
import xlsxwriter
load_dotenv()

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/api/reports/crm_agenda', methods=['GET'])
def get_crm_agenda():
    conn_oracle, cur_oracle = oracle()
    query = """
    SELECT pb.COD_EMPRESA_FILTRO, cet.desc_tipo_evento, count(*)
    FROM OS_AGENDA oa 
    LEFT JOIN CRM_EVENTOS ce ON 1=1
        AND ce.COD_EMPRESA = oa.COD_EMPRESA
        AND ce.COD_EVENTO = oa.CRM_COD_EVENTO
    LEFT JOIN clientes c ON c.COD_CLIENTE = oa.COD_CLIENTE
    LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
        AND cet.cod_tipo_evento = ce.COD_TIPO_EVENTO
    LEFT JOIN PRISMA_BOX pb ON 1=1
                AND pb.prisma = oa.PRISMA
    WHERE 1=1
        AND to_date(oa.DATA_AGENDADA) >= TO_DATE('2025-06-28', 'YYYY-MM-DD')
        AND to_date(oa.DATA_AGENDADA) <= TO_DATE('2025-06-28', 'YYYY-MM-DD')
        AND ce.TEM_CHIP_SERVICO = 'S'
    GROUP BY pb.COD_EMPRESA_FILTRO, cet.desc_tipo_evento
    ORDER BY 1, 2
    """
    cur_oracle.execute(query)
    result_oracle = cur_oracle.fetchall()
    cur_oracle.close()
    conn_oracle.close()

    # Monta HTML
    html = '''
    <html>
    <head><title>Relatório CRM Agenda</title></head>
    <body>
    <h2>Relatório CRM Agenda</h2>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>cod_empresa_filtro</th>
            <th>desc_tipo_evento</th>
            <th>count</th>
        </tr>
    '''
    for row in result_oracle:
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[1]}</td>
            <td>{row[2]}</td>
        </tr>
        """
    html += """
    </table>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@reports_bp.route('/api/reports/fechamento_agendamento', methods=['GET'])
def reports_fechamento_agendamento():
    try:
        initial_date = request.args.get('initial_date')
        final_date = request.args.get('final_date')
        if not initial_date or not final_date:
            return jsonify({'message': 'Initial and final dates are required.'}), 400
        
        try:
            initial_date = datetime.strptime(initial_date, '%Y-%m-%d')
            final_date = datetime.strptime(final_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        
        if (final_date - initial_date).days > 30:
            return jsonify({'message': 'Não pode pesquisar mais de 30 dias'}), 400
        
        initial_date_str = initial_date.strftime('%Y-%m-%d')
        final_date_str = final_date.strftime('%Y-%m-%d')
        
        conn_oracle, cur_oracle = oracle()
        query = f"""
                select 
                s.cod_empresa, 
                s.cod_os_agenda, 
                c.NOME,
                s.CRM_COD_EVENTO,
                --ce.RESPONSAVEL_PELO_EVENTO,
                --eu.NOME_COMPLETO,
                oa.QUEM_ABRIU,
                eu3.NOME_COMPLETO,
                pb.DESCRICAO,
                oa.PLACA,
                pm.DESCRICAO_MODELO,
                oa.PRISMA,
                s.data_comeca, 
                s.data_fim,
                o.numero_os,
                oa.consultor,
                eu2.COD_FUNCAO,
                eu2.nome_completo,
                oa.SERVICO_EXPRESSO,
                oa.status_agenda,
                (SELECT LISTAGG(srv.DESCRICAO_SERVICO, ', ') WITHIN GROUP (ORDER BY srv.DESCRICAO_SERVICO)
			        FROM OS_SERVICOS oss
			        LEFT JOIN servicos srv ON srv.cod_servico = oss.cod_servico
			        WHERE oss.NUMERO_OS = o.NUMERO_OS
			          AND oss.COD_EMPRESA = o.COD_EMPRESA) servicos,
                oa.chassi,
                (SELECT LISTAGG(oar.descricao, ', ') WITHIN GROUP (ORDER BY oar.descricao)
                FROM OS_AGENDA_RECLAMACAO oar
                	WHERE 1=1
                		AND s.COD_OS_AGENDA  = oar.COD_OS_AGENDA 
			          	AND s.COD_EMPRESA = oar.COD_EMPRESA) reclamacoes
            from os_agenda_servicos s
            LEFT JOIN CRM_EVENTOS ce ON 1=1
                AND ce.COD_EMPRESA = s.crm_cod_empresa 
                AND ce.COD_EVENTO = s.CRM_COD_EVENTO 
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND oa.COD_EMPRESA = s.COD_EMPRESA 
                AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA 
            LEFT JOIN CLIENTES c ON 1=1
                AND c.COD_CLIENTE = oa.cod_cliente
            LEFT JOIN PRISMA_BOX pb ON 1=1
                AND pb.PRISMA = oa.PRISMA 
            LEFT JOIN produtos p ON 1=1
                AND p.COD_PRODUTO = oa.COD_PRODUTO 
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = oa.COD_PRODUTO 
                AND pm.COD_MODELO = oa.COD_MODELO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN os o ON 1=1
                AND oa.COD_EMPRESA = o.COD_EMPRESA 
                AND oa.COD_OS_AGENDA = o.COD_OS_AGENDA
                --and o.complemento <> 'S'
                AND o.ORCAMENTO <> 'S'
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.NOME = oa.CONSULTOR
            LEFT JOIN empresas_usuarios eu3 ON 1=1
	            AND eu3.NOME = oa.quem_abriu
            where 
                1=1
            --            pb.COD_EMPRESA_FILTRO = 11
                AND oa.PRISMA IS NOT null
                and   trunc(s.data_fim) >= trunc(TO_DATE('{initial_date_str}', 'YYYY-MM-DD'))
                and   trunc(s.data_comeca) <=  trunc(TO_DATE('{final_date_str}', 'YYYY-MM-DD'))
            order by s.data_comeca
            """
        # return query
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        if len(result) == 0:
            return jsonify({'message': 'Não tem agendamento no período.'}), 404
        df = pd.DataFrame(result, columns=[
            'cod_empresa',
            'cod_os_agenda',
            'nome_cliente',
            'crm_cod_evento',
            'responsavel_pelo_evento',
            'agente_sac',
            'descricao_prisma_box',
            'placa',
            'descricao_modelo',
            'prisma',
            'data_comeca',
            'data_fim',
            'numero_os',
            'consultor',
            'cod_funcao',
            'nome_completo_consultor',
            'servico_express',
            'status_agenda',
            'servicos',
            'chassi',
            'reclamacoes'
        ])
        agenda_por_responsavel = pd.pivot_table(
            df,
            index=['agente_sac'],
            values=['numero_os'],
            aggfunc=lambda x: x.count(),
            fill_value=0
        )
        # agenda_por_responsavel_empresa = pd.pivot_table(
        #     df,
        #     index=['agente_sac'],
        #     values=['numero_os'],
        #     aggfunc=lambda x: x.count(),
        #     fill_value=0
        # )
        agenda_por_responsavel = agenda_por_responsavel[agenda_por_responsavel['numero_os'] > 0]
        df = df[['cod_empresa', 
                'cod_os_agenda', 
                'nome_cliente', 
                'crm_cod_evento',
                'agente_sac', 
                'descricao_prisma_box',
                'placa', 
                'descricao_modelo', 
                'data_comeca', 
                'numero_os', 
                'nome_completo_consultor', 
                'servicos',
                'chassi',
                'reclamacoes'
                ]]
        df = df.fillna('')
        df['data_comeca'] = pd.to_datetime(df['data_comeca'], errors='coerce')

        agenda_por_responsavel.rename(columns={'numero_os': 'quantidade_os'}, inplace=True)
        agenda_por_responsavel.reset_index(inplace=True)

        file_memory = io.BytesIO()
        workbook = xlsxwriter.Workbook(file_memory, {'in_memory': True})
        date_format = workbook.add_format({'border': 1, 'bg_color': 'white', 'num_format': 'dd/mm/yyyy hh:mm', 'font_size': 10, 'valign': 'vcenter'})

        worksheet = workbook.add_worksheet('Agenda por Responsavel')
        worksheet.merge_range('A1:B1', 'Agenda por Responsavel', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'AGENTE_SAC', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'QUANTIDADE_OS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        cont = 0
        for i, row in agenda_por_responsavel.iterrows():
            cont += 1
            worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'B{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        worksheet.add_table(f'A2:B{cont+2}', {'columns': [{'header': 'AGENTE_SAC'},
                                                        {'header': 'QUANTIDADE_OS'}],
                                                        'name': 'Agenda_por_Responsavel',
                                                        'autofilter': True
                                                        })
        worksheet.set_landscape()
        worksheet.print_area(f'A1:B{cont+2}')
        worksheet.set_column('A:A', 30.00)
        worksheet.set_column('B:B', 20.00)
        
        # worksheet = workbook.add_worksheet('Ag - Resp - Empresa')
        # worksheet.merge_range('A1:B1', 'Agenda por Responsavel - Empresa', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'}))
        # worksheet.write('A2', 'COD_EMPRESA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        # worksheet.write('B2', 'AGENTE_SAC', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        # worksheet.write('C2', 'QUANTIDADE_OS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        # cont = 0
        # for i, row in agenda_por_responsavel_empresa.iterrows():
        #     cont += 1
        #     worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        #     worksheet.write(f'B{cont+2}', row.name, workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        #     worksheet.write(f'C{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        # worksheet.add_table(f'A2:C{cont+2}', {'columns': [{'header': 'COD_EMPRESA'},
        #                                                   {'header': 'AGENTE_SAC'},
        #                                                   {'header': 'QUANTIDADE_OS'}],
        #                                                 'name': 'Agenda_por_Responsavel_Empresa',
        #                                                 'autofilter': True
        #                                                 })
        # worksheet.set_landscape()
        # worksheet.set_column('A:A', 10.00)
        # worksheet.set_column('B:B', 30.00)
        # worksheet.set_column('C:C', 20.00)
        

        worksheet = workbook.add_worksheet('Agenda')
        worksheet.merge_range('A1:M1', 'Agenda', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'EMP', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'COD_OS_AGENDA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('C2', 'NOME_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('D2', 'CRM_COD_EVENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('E2', 'AGENTE_SAC', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('F2', 'DESCRICAO_PRISMA_BOX', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))  
        worksheet.write('G2', 'PLACA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('H2', 'DESCRICAO_MODELO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('I2', 'DATA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('J2', 'NUMERO_OS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('K2', 'CONSULTOR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('L2', 'SERVIÇOS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('M2', 'RECLAMACOES', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        cont = 0
        for i, row in df.iterrows():
            cont += 1
            worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'B{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'C{cont+2}', row.iloc[2], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'D{cont+2}', row.iloc[3], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'E{cont+2}', row.iloc[4], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'F{cont+2}', row.iloc[5], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'G{cont+2}', row.iloc[6], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'H{cont+2}', row.iloc[7], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            if isinstance(row.iloc[8], datetime):
                worksheet.write_datetime(f'I{cont+2}', row.iloc[8], date_format)
            else:
                worksheet.write(f'I{cont+2}', row.iloc[8], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'J{cont+2}', row.iloc[9], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'K{cont+2}', row.iloc[10], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'L{cont+2}', row.iloc[11], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'M{cont+2}', row.iloc[13], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        worksheet.add_table(f'A2:M{cont+2}', {'columns': [{'header': 'COD_EMPRESA'},
                                                        {'header': 'COD_OS_AGENDA'},
                                                        {'header': 'NOME_CLIENTE'},
                                                        {'header': 'CRM_COD_EVENTO'},
                                                        {'header': 'AGENTE_SAC'},
                                                        {'header': 'DESCRICAO_PRISMA_BOX'},
                                                        {'header': 'PLACA'},
                                                        {'header': 'DESCRICAO_MODELO'},
                                                        {'header': 'DATA'},
                                                        {'header': 'NUMERO_OS'},
                                                        {'header': 'CONSULTOR'},
                                                        {'header': 'SERVIÇOS'},
                                                        {'header': 'RECLAMAÇÕES'},
                                                        ],
                                                        'name': 'Agenda',
                                                        'autofilter': True
                                                        })
        worksheet.set_landscape()
        worksheet.print_area(f'A1:Q{cont+2}')
        worksheet.set_column('A:A', 6.57)
        worksheet.set_column('B:B', 18.14)
        worksheet.set_column('C:C', 34.00)
        worksheet.set_column('D:D', 8.30)
        worksheet.set_column('E:E', 15.00)
        worksheet.set_column('F:F', 17.00)
        worksheet.set_column('G:G', 8.00)
        worksheet.set_column('H:H', 32.00)
        worksheet.set_column('I:I', 15.00)
        worksheet.set_column('J:J', 14.00)
        worksheet.set_column('K:K', 32.00)
        worksheet.set_column('L:L', 50.00)
        worksheet.set_column('M:M', 10.00)
        workbook.close()
        # retorna o arquivo
        file_memory.seek(0)
        response = Response(file_memory.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers.set('Content-Disposition', 'attachment', filename='fechamento_agendamento.xlsx')
        response.headers.set('Content-Length', str(file_memory.tell()))
        return response, 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 400
    
@reports_bp.route('/api/reports/pesquisa_satisfacao', methods=['GET'])
def reports_pesquisa_satisfacao():
    try:
        initial_date = request.args.get('initial_date')
        final_date = request.args.get('final_date')
        if not initial_date or not final_date:
            return jsonify({'message': 'Initial and final dates are required.'}), 400
        
        try:
            initial_date = datetime.strptime(initial_date, '%Y-%m-%d')
            final_date = datetime.strptime(final_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        
        if (final_date - initial_date).days > 30:
            return jsonify({'message': 'Não pode pesquisar mais de 30 dias'}), 400
        
        initial_date_str = initial_date.strftime('%Y-%m-%d')
        final_date_str = final_date.strftime('%Y-%m-%d')
        
        query = f"""
            SELECT ce.cod_evento, e.nome empresa, cet.desc_tipo_evento tipo_evento, c.nome cliente, o.numero_os, eu.NOME_COMPLETO nome_consultor, cp.PERGUNTA, co.OPCAO a, ce.cod_proposta
            FROM CRM_EVENTOS ce 
            LEFT JOIN EMPRESAS e ON 1=1
                AND e.COD_EMPRESA = ce.COD_EMPRESA
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = ce.COD_CLIENTE
            LEFT JOIN os o ON 1=1
                AND o.NUMERO_OS = ce.NUMERO_OS
                AND o.COD_EMPRESA = ce.COD_EMPRESA
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = o.NOME
            LEFT JOIN CRM_RESPOSTAS cr ON 1=1
                AND cr.cod_empresa = ce.cod_empresa
                AND cr.cod_evento = ce.cod_evento
            LEFT JOIN CRM_PERGUNTAS cp ON 1=1
                AND cp.COD_PERGUNTA = cr.COD_PERGUNTA 
                AND cp.COD_QUESTIONARIO = cr.COD_QUESTIONARIO 
            LEFT JOIN CRM_OPCOES co ON 1=1
	            AND co.COD_OPCOES = cr.COD_OPCOES
            WHERE 1=1
                AND ce.COD_TIPO_EVENTO IN (22,180,30)
                AND ce.COD_TIPO_FECHAMENTO = 1
                --AND ce.cod_evento = 1728505
                and   trunc(ce.DATA_ENCERRAMENTO) >= trunc(TO_DATE('{initial_date_str}', 'YYYY-MM-DD')) 
                and   trunc(ce.DATA_ENCERRAMENTO) <=  trunc(TO_DATE('{final_date_str}', 'YYYY-MM-DD'))
            ORDER BY cod_evento desc
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        if len(result) == 0:
            return jsonify({'message': 'Não tem pesquisa de satisfação no período.'}), 404
        df = pd.DataFrame(result, columns=[
            'cod_evento',
            'empresa',
            'tipo_evento',
            'cliente',
            'numero_os',
            'nome_consultor',
            'pergunta',
            'nota',
            'cod_proposta'
        ])
        df = df.fillna('')
        df = df.sort_values(by='cod_evento', ascending=False)
        
        file_memory = io.BytesIO()
        workbook = xlsxwriter.Workbook(file_memory, {'in_memory': True})
        worksheet = workbook.add_worksheet('Pesquisa Satisfacao')
        worksheet.merge_range('A1:H1', 'Pesquisa Satisfacao - Detalhe', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'COD_EVENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'EMPRESA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('C2', 'TIPO_EVENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('D2', 'CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('E2', 'NUMERO_OS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('F2', 'NOME_CONSULTOR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('G2', 'PERGUNTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('H2', 'NOTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('I2', 'COD_PROPOSTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        cont = 0
        cod_evento = None
        usar_amarelo = True
        for i, row in df.iterrows():
            cont += 1
            n_cod_evento = row.iloc[0]
            if cod_evento != n_cod_evento:
                # Mudou o cod_evento, alterna a cor
                cor_celula = '#DCE6F1' if usar_amarelo else '#F2DCDB'
                usar_amarelo = not usar_amarelo  # Alterna para a próxima vez
                cod_evento = n_cod_evento
            worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'B{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'C{cont+2}', row.iloc[2], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'D{cont+2}', row.iloc[3], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'E{cont+2}', row.iloc[4], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'F{cont+2}', row.iloc[5], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'G{cont+2}', row.iloc[6], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'H{cont+2}', row.iloc[7], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'I{cont+2}', row.iloc[8], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
        worksheet.add_table(f'A2:I{cont+2}', {'columns': [{'header': 'COD_EVENTO'},
                                                        {'header': 'EMPRESA'},
                                                        {'header': 'TIPO_EVENTO'},
                                                        {'header': 'CLIENTE'},
                                                        {'header': 'NUMERO_OS'},
                                                        {'header': 'NOME_CONSULTOR'},
                                                        {'header': 'PERGUNTA'},
                                                        {'header': 'NOTA'},
                                                        {'header': 'COD_PROPOSTA'}],
                                                        'name': 'Pesquisa_Satisfacao',
                                                        'autofilter': True
                                                        })
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.set_column('A:A', 15.00)
        worksheet.set_column('B:B', 20.00)
        worksheet.set_column('C:C', 30.00)
        worksheet.set_column('D:D', 30.00)
        worksheet.set_column('E:E', 15.00)
        worksheet.set_column('F:F', 24.00)
        worksheet.set_column('G:G', 80.00)
        worksheet.set_column('H:H', 8.00)
        worksheet.set_column('I:I', 8.00)
        worksheet.print_area(f'A1:I{cont+2}')
        # imprimir em apenas uma pagina na horizontal
        worksheet.fit_to_pages(1, 0)  # Ajusta para uma página de largura e sem limite de altura
        
        workbook.close()
        file_memory.seek(0)
        response = Response(file_memory.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers.set('Content-Disposition', 'attachment', filename='pesquisa_satisfacao.xlsx')
        response.headers.set('Content-Length', str(file_memory.tell()))
        return response, 200
        
        
        
    except Exception as e:
        return jsonify({'message': str(e)}), 400
    
@reports_bp.route('/api/reports/estoque', methods=['GET'])
def reports_estoque():
    try:
        aguarda_faturamento = request.args.get('aguarda_faturamento', False)
        filtro_aguarda_faturamento = ''
        if aguarda_faturamento and aguarda_faturamento.lower() == 'true':
            filtro_aguarda_faturamento = f"""AND v.cod_proposta <> 0
                                        AND v.cod_proposta IS NOT null"""
        query = f"""
            SELECT 
                v.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
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
                    ELSE
                        'Novo'
                END novo_usado,
                CASE
                    WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                    WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                    ELSE cid_cob.DESCRICAO 
                END cidade
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
            LEFT JOIN cidades cid_res ON 1=1
                AND cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON 1=1
                AND cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON 1=1
                AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            WHERE v.status = 'E'
                {filtro_aguarda_faturamento}
            ORDER BY pm.DESCRICAO_MODELO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        
        file_memory = io.BytesIO()
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        workbook = xlsxwriter.Workbook(file_memory, {'in_memory': True})
        worksheet = workbook.add_worksheet('Estoque de veiculos')
        worksheet.merge_range(f'A1:P1', f'Estoque de veiculos - Gerado em {data_atual}', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('A2', 'COD_PROPOSTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'DATA_PROPOSTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('C2', 'COD_VENDEDOR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('D2', 'NOME_VENDEDOR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('E2', 'MODELO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('F2', 'COR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('G2', 'ANO_MODELO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('H2', 'CHASSI_COMPLETO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('I2', 'EMPRESA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('J2', 'EMISSAO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('K2', 'PATIO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('L2', 'COD_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('M2', 'NOME_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('N2', 'NOVO_USADO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('O2', 'CIDADE_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('P2', 'ANDAMENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('Q2', 'TEM_USADO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        
        cont = 0
        for row in result:
            if row[0] and str(row[0]) != "0":
                worksheet.write(cont + 2, 0, row[0], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 0, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            # Corrigindo o tratamento da data_proposta
            if row[1]:  # Verifica se não é None
                try:
                    # Se for string, converte para datetime
                    if isinstance(row[1], str):
                        date_obj = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
                        worksheet.write_datetime(cont + 2, 1, date_obj, workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy hh:mm'}))
                    # Se for datetime do Oracle, converte
                    elif hasattr(row[1], 'year'):  # Verifica se é um objeto de data
                        date_obj = datetime(row[1].year, row[1].month, row[1].day, 
                                          getattr(row[1], 'hour', 0), 
                                          getattr(row[1], 'minute', 0), 
                                          getattr(row[1], 'second', 0))
                        worksheet.write_datetime(cont + 2, 1, date_obj, workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy hh:mm'}))
                    else:
                        # Se não conseguir converter, escreve como string
                        worksheet.write(cont + 2, 1, str(row[1]), workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
                except:
                    # Em caso de erro na conversão, escreve como string
                    worksheet.write(cont + 2, 1, str(row[1]), workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 1, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 2, row[2], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 3, row[3], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 4, row[4], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 5, row[5], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 6, row[6], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 7, row[7], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 8, row[8], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            # Corrigindo o tratamento da data de emissão também
            if row[9]:  # DATA_NOTA emissao
                try:
                    if isinstance(row[9], str):
                        date_obj = datetime.strptime(row[9], '%Y-%m-%d %H:%M:%S')
                        worksheet.write_datetime(cont + 2, 9, date_obj, workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy'}))
                    elif hasattr(row[9], 'year'):
                        date_obj = datetime(row[9].year, row[9].month, row[9].day, 
                                          getattr(row[9], 'hour', 0), 
                                          getattr(row[9], 'minute', 0), 
                                          getattr(row[9], 'second', 0))
                        worksheet.write_datetime(cont + 2, 9, date_obj, workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy'}))
                    else:
                        worksheet.write(cont + 2, 9, str(row[9]), workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
                except:
                    worksheet.write(cont + 2, 9, str(row[9]), workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 9, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 10, row[10], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            if row[11] and str(row[11]) != "0":
                worksheet.write(cont + 2, 11, str(row[11]), workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 11, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 12, row[12], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 13, row[13], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(cont + 2, 14, row[14], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            
            query = f"""
            SELECT cav.DESCRICAO  FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{row[7]}'
                AND created_at = (SELECT max(created_at) FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{row[7]}')
                ORDER BY created_at DESC
            """
            cur_oracle.execute(query)
            result_andamento = cur_oracle.fetchone()
            if result_andamento and result_andamento[0]:
                worksheet.write(cont + 2, 15, result_andamento[0], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 15, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            
            query = f"""
                SELECT count(*) FROM VEIC_FORMAS_PAGAMENTO vfp
                LEFT JOIN FORMA_PGTO fp ON 1=1
                    AND fp.cod_empresa = vfp.COD_EMPRESA 
                    AND fp.COD_FORMA_PGTO = vfp.COD_FORMA_PGTO 
                WHERE 1=1
                    AND vfp.cod_proposta = '{row[0]}'
                    AND lower(descricao) LIKE ('%usado%')
            """
            cur_oracle.execute(query)
            usado_result = cur_oracle.fetchone()
            if usado_result and usado_result[0] and usado_result[0] > 0:
                worksheet.write(cont + 2, 16, 'Sim', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 16, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))


            cont += 1

        worksheet.add_table(f'A2:Q{cont+2}', {
            'columns': [
                {'header': 'COD_PROPOSTA'},
                {'header': 'DATA_PROPOSTA'},
                {'header': 'COD_VENDEDOR'},
                {'header': 'NOME_VENDEDOR'},
                {'header': 'MODELO'},
                {'header': 'COR'},
                {'header': 'ANO_MODELO'},
                {'header': 'CHASSI_COMPLETO'},
                {'header': 'EMPRESA'},
                {'header': 'EMISSAO'},
                {'header': 'PATIO'},
                {'header': 'COD_CLIENTE'},
                {'header': 'NOME_CLIENTE'},
                {'header': 'NOVO_USADO'},
                {'header': 'CIDADE_CLIENTE'},
                {'header': 'ULTIMO_ANDAMENTO'},
                {'header': 'TEM_USADO'},
            ],
            'name': 'Estoque_Veiculos',
            'autofilter': True
        })
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.set_column('A:A', 17.40)
        worksheet.set_column('B:B', 18.14)
        worksheet.set_column('C:C', 17.43)
        worksheet.set_column('D:D', 27.00)
        worksheet.set_column('E:E', 53.00)
        worksheet.set_column('F:F', 17.00)
        worksheet.set_column('G:G', 15.70)
        worksheet.set_column('H:H', 20.00)
        worksheet.set_column('I:I', 21.43)
        worksheet.set_column('J:J', 10.71)
        worksheet.set_column('K:K', 30.00)
        worksheet.set_column('L:L', 14.43)
        worksheet.set_column('M:M', 37.00)
        worksheet.set_column('N:N', 15.71)
        worksheet.set_column('O:O', 15.71)
        worksheet.set_column('P:P', 30.00)
        worksheet.set_column('Q:Q', 10.00)
        worksheet.print_area(f'A1:O{cont+2}')
        # imprimir em apneas uma pagina na horizontal
        worksheet.fit_to_pages(1, 0)  # Ajusta para uma página de largura e sem limite de altura
        
        workbook.close()
        file_memory.seek(0)
        response = Response(file_memory.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers.set('Content-Disposition', 'attachment', filename='estoque_veiculos.xlsx')
        response.headers.set('Content-Length', str(file_memory.tell()))
        cur_oracle.close()
        conn_oracle.close()
        return response, 200

    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'message': str(e)}), 400

@reports_bp.route('/api/reports/faturamento_veiculos', methods=['GET'])
def reports_faturamento_veiculos():
    try:
        initial_date = request.args.get('initial_date')
        final_date = request.args.get('final_date')
        if not initial_date or not final_date:
            return jsonify({'message': 'Initial and final dates are required.'}), 400
        
        try:
            initial_date = datetime.strptime(initial_date, '%Y-%m-%d')
            final_date = datetime.strptime(final_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        
        if (final_date - initial_date).days > 30:
            return jsonify({'message': 'Não pode pesquisar mais de 30 dias'}), 400
        
        initial_date_str = initial_date.strftime('%Y-%m-%d')
        final_date_str = final_date.strftime('%Y-%m-%d')
        
        query = f"""
            SELECT 
                e.NOME nome_empresa,
                v.COD_PROPOSTA, 
                v.COD_CLIENTE,
                c.NOME,
                v.CHASSI_COMPLETO, 
                pm.DESCRICAO_MODELO modelo_veiculo,
                v.DATA_VENDA, 
                CASE
                    mhv.status
                    WHEN 'O' THEN 'Sucesso'
                    WHEN 'P' THEN 'Pendente'
                    WHEN 'E' THEN 'Erro'
                    WHEN 'R' THEN 'Rejeitado'
                END status_envio_myhonda,
                MHV.data_atualizacao data_envio_myhonda
            from veiculos v
            left join clientes c on 1=1
                AND c.cod_cliente=v.cod_cliente
            LEFT JOIN my_honda_mov mhv ON 1=1
                AND MHV.cod_proposta = v.COD_PROPOSTA
                AND mhv.COD_EMPRESA = v.COD_EMPRESA
            LEFT JOIN empresas e ON e.COD_EMPRESA = v.COD_EMPRESA
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1	
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            WHERE 1=1
                AND v.STATUS  = 'V'
                and trunc(v.data_venda) >= TO_DATE('{initial_date_str}', 'YYYY-MM-DD')
                and (V.data_venda) <= TO_DATE('{final_date_str}', 'YYYY-MM-DD')
            ORDER BY v.data_venda
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        if len(result) == 0:
            return jsonify({'message': 'Não tem pesquisa de satisfação no período.'}), 404
        df = pd.DataFrame(result, columns=[
            'nome_empresa',
            'cod_proposta',
            'cod_cliente',
            'nome_cliente',
            'chassi_completo',
            'modelo_veiculo',
            'data_venda',
            'status_envio_myhonda',
            'data_envio_myhonda'
        ])
        df = df.fillna('')
        
        
        file_memory = io.BytesIO()
        workbook = xlsxwriter.Workbook(file_memory, {'in_memory': True})
        worksheet = workbook.add_worksheet('Veículos Faturados')
        worksheet.merge_range('A1:H1', 'Veículos Faturados - Detalhe', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'NOME_EMPRESA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'COD_PROPOSTA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('C2', 'COD_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('D2', 'NOME_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('E2', 'CHASSI_COMPLETO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('F2', 'MODELO_VEICULO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('G2', 'DATA_VENDA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('H2', 'STATUS_ENVIO_MYHONDA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('I2', 'DATA_ENVIO_MYHONDA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        cont = 0
        
        for i, row in df.iterrows():
            cont += 1
            worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'B{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'C{cont+2}', str(row.iloc[2]), workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'D{cont+2}', row.iloc[3], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'E{cont+2}', row.iloc[4], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'F{cont+2}', row.iloc[5], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'G{cont+2}', row.iloc[6], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'H{cont+2}', row.iloc[7], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'I{cont+2}', row.iloc[8], workbook.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}))
        worksheet.add_table(f'A2:I{cont+2}', {'columns': [{'header': 'NOME_EMPRESA'},
                                                        {'header': 'COD_PROPOSTA'},
                                                        {'header': 'COD_CLIENTE'},
                                                        {'header': 'NOME_CLIENTE'},
                                                        {'header': 'CHASSI_COMPLETO'},
                                                        {'header': 'MODELO_VEICULO'},
                                                        {'header': 'DATA_VENDA'},
                                                        {'header': 'STATUS_ENVIO_MYHONDA'},
                                                        {'header': 'DATA_ENVIO_MYHONDA'}],
                                                        'name': 'veiculos_faturados',
                                                        'autofilter': True
                                                        })
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.set_column('A:A', 18.43)
        worksheet.set_column('B:B', 17.14)
        worksheet.set_column('C:C', 14.43)
        worksheet.set_column('D:D', 46.71)
        worksheet.set_column('E:E', 20.00)
        worksheet.set_column('F:F', 34.00)
        worksheet.set_column('G:G', 17.00)
        worksheet.set_column('H:H', 27.29)
        worksheet.set_column('I:I', 25.29)
        worksheet.print_area(f'A1:I{cont+2}')
        # imprimir em apenas uma pagina na horizontal
        worksheet.fit_to_pages(1, 0)  # Ajusta para uma página de largura e sem limite de altura
        
        workbook.close()
        file_memory.seek(0)
        response = Response(file_memory.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers.set('Content-Disposition', 'attachment', filename='veiculos_faturados.xlsx')
        response.headers.set('Content-Length', str(file_memory.tell()))
        return response, 200
        
        
        
    except Exception as e:
        return jsonify({'message': str(e)}), 400
