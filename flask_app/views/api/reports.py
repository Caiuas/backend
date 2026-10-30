from flask import Blueprint, jsonify, request, Response, send_file
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd
import io
import xlsxwriter
from auth import token_required
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
                oa.ano,
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
			          	AND s.COD_EMPRESA = oar.COD_EMPRESA) reclamacoes,
                CASE
			    	WHEN oa.tipo_atendimento = 'R' THEN 'Receptivo' 
			    	WHEN oa.tipo_atendimento = 'P' THEN 'Passivo'
			    	WHEN oa.tipo_atendimento = 'A' THEN 'Ativo'
			    	ELSE 'Não classificado'
			    END tipo_atendimento
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
            'ano',
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
            'reclamacoes',
            'tipo_atendimento'
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
                'tipo_atendimento',
                'nome_cliente', 
                'crm_cod_evento',
                'agente_sac', 
                'descricao_prisma_box',
                'placa', 
                'descricao_modelo', 
                'ano',
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
        worksheet.merge_range('A1:P1', 'Agenda', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'EMP', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('B2', 'COD_OS_AGENDA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('C2', 'TIPO_ATENDIMENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('D2', 'NOME_CLIENTE', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('E2', 'CRM_COD_EVENTO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('F2', 'AGENTE_SAC', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('G2', 'DESCRICAO_PRISMA_BOX', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))  
        worksheet.write('H2', 'PLACA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('I2', 'DESCRICAO_MODELO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('J2', 'ANO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('K2', 'DATA', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('L2', 'NUMERO_OS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('M2', 'CONSULTOR', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('N2', 'SERVIÇOS', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('O2', 'RECLAMACOES', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        worksheet.write('P2', 'REVISAO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))
        cont = 0
        for i, row in df.iterrows():
            cont += 1
            servico = str(row.iloc[13]).lower()
            servico = str(servico).replace('ã','a')
            servico = str(servico).replace('kms','')
            servico = str(servico).replace('km','')
            servico = str(servico).replace(' mil ','.000')
            # remove espaços duplos
            servico = ' '.join(servico.split())
            revisao = 'Não'
            if 'revisao' in servico or 'revisão' in servico:
                revisao = 'Sim'
                if '10.000' in servico:
                    revisao = '10.000'
                if '20.000' in servico:
                    revisao = '20.000'
                if '30.000' in servico:
                    revisao = '30.000'
                if '40.000' in servico:
                    revisao = '40.000'
                if '50.000' in servico:
                    revisao = '50.000'
                if '60.000' in servico:
                    revisao = '60.000'
                if '70.000' in servico:
                    revisao = '70.000'
                if '80.000' in servico:
                    revisao = '80.000'
                if '90.000' in servico:
                    revisao = '90.000'
                if '100.000' in servico:
                    revisao = '100.000'
                if '110.000' in servico:
                    revisao = '110.000'
                if '120.000' in servico:
                    revisao = '120.000'
                if '130.000' in servico:
                    revisao = '130.000'
                if '140.000' in servico:
                    revisao = '140.000'
                if '150.000' in servico:
                    revisao = '150.000'
                if '160.000' in servico:
                    revisao = '160.000'
                if '170.000' in servico:
                    revisao = '170.000'
                if '180.000' in servico:
                    revisao = '180.000'
                if 'recall' in str(servico).lower():
                    revisao = 'RECALL'
                    
                    
                if 'revisao de 10.000' in servico:
                    revisao = '10.000'
                if 'revisao de 20.000' in servico:
                    revisao = '20.000'
                if 'revisao de 30.000' in servico:
                    revisao = '30.000'
                if 'revisao de 40.000' in servico:
                    revisao = '40.000'
                if 'revisao de 50.000' in servico:
                    revisao = '50.000'
                if 'revisao de 60.000' in servico:
                    revisao = '60.000'
                if 'revisao de 70.000' in servico:
                    revisao = '70.000'
                if 'revisao de 80.000' in servico:
                    revisao = '80.000'
                if 'revisao de 90.000' in servico:
                    revisao = '90.000'
                if 'revisao de 100.000' in servico:
                    revisao = '100.000'
                if 'revisao de 110.000' in servico:
                    revisao = '110.000'
                if 'revisao de 120.000' in servico:
                    revisao = '120.000'
                if 'revisao de 130.000' in servico:
                    revisao = '130.000'
                if 'revisao de 140.000' in servico:
                    revisao = '140.000'
                if 'revisao de 150.000' in servico:
                    revisao = '150.000'
                if 'revisao de 160.000' in servico:
                    revisao = '160.000'
                if 'revisao de 170.000' in servico:
                    revisao = '170.000'
                if 'revisao de 10 mil' in servico:
                    revisao = '10 mil'
                if 'revisao de 20 mil' in servico:
                    revisao = '20 mil'
                if 'revisao de 30 mil' in servico:
                    revisao = '30 mil'
                if 'revisao de 40 mil' in servico:
                    revisao = '40 mil'
                if 'revisao de 50 mil' in servico:
                    revisao = '50 mil'
                if 'revisao de 60 mil' in servico:
                    revisao = '60 mil'
                if 'revisao de 70 mil' in servico:
                    revisao = '70 mil'
                if 'revisao de 80 mil' in servico:
                    revisao = '80 mil'
                if 'revisao de 90 mil' in servico:
                    revisao = '90 mil'
            worksheet.write(f'A{cont+2}', row.iloc[0], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'B{cont+2}', row.iloc[1], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'C{cont+2}', row.iloc[2], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'D{cont+2}', row.iloc[3], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'E{cont+2}', row.iloc[4], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'F{cont+2}', row.iloc[5], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'G{cont+2}', row.iloc[6], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'H{cont+2}', row.iloc[7], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'I{cont+2}', row.iloc[8], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'J{cont+2}', row.iloc[9], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            if isinstance(row.iloc[10], datetime):
                worksheet.write_datetime(f'K{cont+2}', row.iloc[10], date_format)
            else:
                worksheet.write(f'K{cont+2}', row.iloc[10], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'L{cont+2}', row.iloc[11], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'M{cont+2}', row.iloc[12], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'N{cont+2}', servico, workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'O{cont+2}', row.iloc[15], workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
            worksheet.write(f'P{cont+2}', revisao, workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'}))
        worksheet.add_table(f'A2:P{cont+2}', {'columns': [{'header': 'COD_EMPRESA'},
                                                        {'header': 'COD_OS_AGENDA'},
                                                        {'header': 'TIPO_ATENDIMENTO'},
                                                        {'header': 'NOME_CLIENTE'},
                                                        {'header': 'CRM_COD_EVENTO'},
                                                        {'header': 'AGENTE_SAC'},
                                                        {'header': 'DESCRICAO_PRISMA_BOX'},
                                                        {'header': 'PLACA'},
                                                        {'header': 'DESCRICAO_MODELO'},
                                                        {'header': 'ANO'},
                                                        {'header': 'DATA'},
                                                        {'header': 'NUMERO_OS'},
                                                        {'header': 'CONSULTOR'},
                                                        {'header': 'SERVIÇOS'},
                                                        {'header': 'RECLAMAÇÕES'},
                                                        {'header': 'REVISÃO'}
                                                        ],
                                                        'name': 'Agenda',
                                                        'autofilter': True
                                                        })
        worksheet.set_landscape()
        worksheet.print_area(f'A1:P{cont+2}')
        worksheet.set_column('A:A', 3.30)
        worksheet.set_column('B:B', 7.43)
        worksheet.set_column('C:C', 13.30)
        worksheet.set_column('D:D', 20.60)
        worksheet.set_column('E:E', 7.80)
        worksheet.set_column('F:F', 12.80)
        worksheet.set_column('G:G', 25.80)
        worksheet.set_column('H:H', 8.80)
        worksheet.set_column('I:I', 22.80)
        worksheet.set_column('J:J', 15.00)
        worksheet.set_column('K:K', 8.00)
        worksheet.set_column('L:L', 32.00)
        worksheet.set_column('M:M', 19.00)
        worksheet.set_column('N:N', 19.00)
        worksheet.set_column('O:O', 10.00)
        worksheet.set_column('P:P', 10.00)
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
                vp.COD_PROPOSTA, 
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
                END cidade,
                v.PLACA_USADO
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
        # return (query)
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        # return str(result)
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
        worksheet.write('R2', 'PLACA_USADO', workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'}))

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
            worksheet.write(cont + 2, 17, row[15], workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            
            
            query = f"""
            SELECT cav.DESCRICAO  FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{row[7]}'
                AND created_at = (SELECT max(created_at) FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{row[7]}')
                ORDER BY created_at DESC
            """
            # return(query)
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
            query = query.replace("'None'", "'0'")
            # return(query)
            cur_oracle.execute(query)
            usado_result = cur_oracle.fetchone()
            if usado_result and usado_result[0] and usado_result[0] > 0:
                worksheet.write(cont + 2, 16, 'Sim', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            else:
                worksheet.write(cont + 2, 16, '', workbook.add_format({'align': 'center', 'valign': 'vcenter'}))
            
            


            cont += 1
        # return('oi')
        worksheet.add_table(f'A2:R{cont+2}', {
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
                {'header': 'PLACA_USADO'},
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
        worksheet.set_column('R:R', 11.00)
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

@reports_bp.route('/api/reports/passagens_oficina', methods=['GET'])
@token_required
def reports_passagens_oficina():
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
                os.COD_EMPRESA, 
                os.NUMERO_OS, 
                eu.NOME_COMPLETO consultor,   
                os.TIPO,
                ot.DESCRICAO tipo_os,
                c.NOME cliente, 
                os.DATA_EMISSAO, 
                (
                    SELECT LISTAGG(upper(s.DESCRICAO_SERVICO), ', ') WITHIN GROUP (ORDER BY s.DESCRICAO_SERVICO)
                    FROM OS_SERVICOS oos 
                    LEFT JOIN servicos s ON s.COD_SERVICO = oos.COD_SERVICO 
                    WHERE oos.NUMERO_OS = os.NUMERO_OS 
                        AND oos.COD_EMPRESA = os.COD_EMPRESA 
                ) AS DESCRICAO_SERVICOS
            FROM os os
            LEFT JOIN OS_DADOS_VEICULOS odv 
                ON odv.COD_EMPRESA = os.COD_EMPRESA 
            AND odv.NUMERO_OS = os.NUMERO_OS 
            LEFT JOIN CLIENTES c 
                ON c.COD_CLIENTE = os.cod_cliente
            LEFT JOIN os_tipos ot ON 1=1
                AND ot.TIPO = os.TIPO 
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = os.CONSULTOR_RECEPCAO 
            WHERE os.NUMERO_OS > 0
                AND os.STATUS_OS <> 2 
                AND os.COMPLEMENTO = 'N'
            AND trunc(os.DATA_EMISSAO) >= to_date('{initial_date_str}', 'YYYY-MM-DD')
            AND trunc(os.DATA_EMISSAO) <= to_date('{final_date_str}', 'YYYY-MM-DD')
            ORDER BY os.DATA_EMISSAO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        if len(result) == 0:
            return jsonify({'message': 'Não tem passagens de oficina no período.'}), 404
        df = pd.DataFrame(result, columns=[
            'cod_empresa',
            'numero_os',
            'consultor',
            'tipo',
            'tipo_os',
            'cliente',
            'data_emissao',
            'descricao_servicos'
        ])
        
        file_memory = io.BytesIO()
        workbook = xlsxwriter.Workbook(file_memory, {'in_memory': True})
        cell_format = workbook.add_format({'border': 1, 'bg_color': 'white', 'font_size': 10, 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'})
        date_format = workbook.add_format({'border': 1, 'bg_color': 'white', 'num_format': 'dd/mm/yyyy', 'font_size': 10, 'valign': 'vcenter'})
        worksheet = workbook.add_worksheet('Passagens de Oficina')
        worksheet.merge_range('A1:I1', 'Passagens de Oficina - Detalhe', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
        worksheet.write('A2', 'COD_EMPRESA', header_format)
        worksheet.write('B2', 'NUMERO_OS', header_format)
        worksheet.write('C2', 'CONSULTOR', header_format)
        worksheet.write('D2', 'TIPO', header_format)
        worksheet.write('E2', 'TIPO_OS', header_format)
        worksheet.write('F2', 'CLIENTE', header_format)
        worksheet.write('G2', 'DATA_EMISSAO', header_format)
        worksheet.write('H2', 'DESCRICAO_SERVICOS', header_format)
        worksheet.write('I2', 'Tipo de revisão', header_format)
        cont = 0
        for index, row in df.iterrows():
            servico = str(row['descricao_servicos']).lower()
            servico = str(servico).replace('ã', 'a')
            servico = str(servico).replace('kms', '')
            servico = str(servico).replace('km', '')
            servico = str(servico).replace(' mil ', '.000')
            servico = ' '.join(servico.split())
            tipo_revisao = 'Não'
            if 'revisao' in servico or 'revisão' in servico:
                tipo_revisao = 'Sim'
                if '10.000' in servico or 'revisao de 10.000' in servico:
                    tipo_revisao = '10.000'
                if '20.000' in servico or 'revisao de 20.000' in servico:
                    tipo_revisao = '20.000'
                if '30.000' in servico or 'revisao de 30.000' in servico:
                    tipo_revisao = '30.000'
                if '40.000' in servico or 'revisao de 40.000' in servico:
                    tipo_revisao = '40.000'
                if '50.000' in servico or 'revisao de 50.000' in servico:
                    tipo_revisao = '50.000'
                if '60.000' in servico or 'revisao de 60.000' in servico:
                    tipo_revisao = '60.000'
                if '70.000' in servico or 'revisao de 70.000' in servico:
                    tipo_revisao = '70.000'
                if '80.000' in servico or 'revisao de 80.000' in servico:
                    tipo_revisao = '80.000'
                if '90.000' in servico or 'revisao de 90.000' in servico:
                    tipo_revisao = '90.000'
                if '100.000' in servico or 'revisao de 100.000' in servico:
                    tipo_revisao = '100.000'
                if '110.000' in servico or 'revisao de 110.000' in servico:
                    tipo_revisao = '110.000'
                if '120.000' in servico or 'revisao de 120.000' in servico:
                    tipo_revisao = '120.000'
                if '130.000' in servico or 'revisao de 130.000' in servico:
                    tipo_revisao = '130.000'
                if '140.000' in servico or 'revisao de 140.000' in servico:
                    tipo_revisao = '140.000'
                if '150.000' in servico or 'revisao de 150.000' in servico:
                    tipo_revisao = '150.000'
                if '160.000' in servico or 'revisao de 160.000' in servico:
                    tipo_revisao = '160.000'
                if '170.000' in servico or 'revisao de 170.000' in servico:
                    tipo_revisao = '170.000'
                if '180.000' in servico or 'revisao de 180.000' in servico:
                    tipo_revisao = '180.000'
                if 'recall' in servico:
                    tipo_revisao = 'RECALL'
            data_emissao = row['data_emissao']
            if pd.notna(data_emissao):
                if isinstance(data_emissao, datetime):
                    worksheet.write_datetime(cont + 2, 6, data_emissao, date_format)
                else:
                    try:
                        worksheet.write_datetime(cont + 2, 6, datetime.strptime(str(data_emissao)[:19], '%Y-%m-%d %H:%M:%S'), date_format)
                    except ValueError:
                        worksheet.write(cont + 2, 6, str(data_emissao)[:10], cell_format)
            else:
                worksheet.write(cont + 2, 6, '', cell_format)
            worksheet.write(cont + 2, 0, row['cod_empresa'], cell_format)
            worksheet.write(cont + 2, 1, row['numero_os'], cell_format)
            worksheet.write(cont + 2, 2, row['consultor'], cell_format)
            worksheet.write(cont + 2, 3, row['tipo'], cell_format)
            worksheet.write(cont + 2, 4, row['tipo_os'], cell_format)
            worksheet.write(cont + 2, 5, row['cliente'], cell_format)
            worksheet.write(cont + 2, 7, row['descricao_servicos'], cell_format)
            worksheet.write(cont + 2, 8, tipo_revisao, cell_format)
            cont += 1
        worksheet.add_table(f'A2:I{cont+2}', {'columns': [
            {'header': 'COD_EMPRESA'},
            {'header': 'NUMERO_OS'},
            {'header': 'CONSULTOR'},
            {'header': 'TIPO'},
            {'header': 'TIPO_OS'},
            {'header': 'CLIENTE'},
            {'header': 'DATA_EMISSAO'},
            {'header': 'DESCRICAO_SERVICOS'},
            {'header': 'TIPO_DE_REVISAO'},
        ], 'name': 'Passagens_Oficina', 'autofilter': True})
        worksheet.set_landscape()
        worksheet.set_paper(9)
        worksheet.set_column('A:A', 12.00)
        worksheet.set_column('B:B', 14.00)
        worksheet.set_column('C:C', 24.00)
        worksheet.set_column('D:D', 10.00)
        worksheet.set_column('E:E', 14.00)
        worksheet.set_column('F:F', 28.00)
        worksheet.set_column('G:G', 14.00)
        worksheet.set_column('H:H', 60.00)
        worksheet.set_column('I:I', 14.00)
        worksheet.print_area(f'A1:I{cont+2}')
        worksheet.fit_to_pages(1, 0)
        workbook.close()
        file_memory.seek(0)
        return send_file(file_memory, download_name='passagens_de_oficina.xlsx', as_attachment=True)
    except Exception as e:
        return jsonify({'message': str(e)}), 400


@reports_bp.route('/api/reports/dashboard_showroom', methods=['GET'])
@token_required
def reports_dashboard_showroom():
    usuarios_permitidos = {'franciele.mayer', 'pablo.ti', 'tais.schrepel', 'marcelotcf'}

    token_data = request.token_data
    email = (token_data.get('email') or '').strip().lower()
    usuario = email.split('@')[0]
    if usuario not in usuarios_permitidos:
        return jsonify({'message': 'Usuário não autorizado a gerar este relatório.'}), 403

    ano = request.args.get('ano')
    mes = request.args.get('mes')
    if not ano or not mes:
        return jsonify({'message': 'Os parâmetros ano e mes são obrigatórios.'}), 400
    try:
        ano = int(ano)
        mes = int(mes)
    except (TypeError, ValueError):
        return jsonify({'message': 'Ano e mês devem ser números.'}), 400
    if ano < 2000 or not 1 <= mes <= 12:
        return jsonify({'message': 'Ano ou mês inválidos.'}), 400

    try:
        _buffer, filename = gerar_dashboard_showroom(ano, mes)
    except Exception as e:
        return jsonify({'message': str(e)}), 400

    return send_file(
        _buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


def gerar_dashboard_showroom(ano, mes, data_inicial=None, data_final=None):
    try:
        import calendar
        import datetime
        import os
        import sys
        from pathlib import Path
        import pandas as pd

        try:
            from database import oracle
        except ModuleNotFoundError:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from database import oracle

        conn, cur = oracle()

        _ini = (data_inicial or datetime.date(ano, mes, 1)).strftime('%Y-%m-%d')
        _fim = (data_final or datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])).strftime('%Y-%m-%d')

        # Veiculos Faturados

        query = f"""
            SELECT
                pr.descricao_produto familia_veiculo,
                vp.cod_proposta,
                vp.cod_cliente,
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                eu.cod_empresa empresa_vendedor,
                pm.DESCRICAO_MODELO modelo, 
                COALESCE(ce.DESCRICAO, ce2.DESCRICAO) cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                    ELSE
                        'Novo'
                END novo_usado
            FROM veiculos v 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN prop_ficticia_dados pfd ON 1=1
                AND pfd.COD_FICTICIO = vp.COD_FICTICIO
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
                AND ce2.COR_EXTERNA = pfd.COR_EXTERNA
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA
            LEFT JOIN CLIENTES_FROTA cf ON 1=1
                AND cf.chassi = v.CHASSI_COMPLETO 
                AND cf.COD_CLIENTE = c.COD_CLIENTE  
                AND cf.nome = vp.VENDEDOR 
            LEFT JOIN cidades cid_res ON 1=1
                AND cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON 1=1
                AND cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON 1=1
                AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            LEFT JOIN ev_agendados ea ON 1=1
                AND ea.STATUS NOT IN ('C')
                --AND ea.QUEM_CANCELOU IS NULL
                AND TO_CHAR(ea.COD_PROPOSTA) = TO_CHAR(vp.COD_PROPOSTA)
                AND TO_CHAR(ea.CHASSI_RESUMIDO) = TO_CHAR(v.CHASSI_RESUMIDO)
            left join EV_SALAS es on 1=1
                and es.cod_sala = ea.cod_sala
            left join caiuas_veic_proc cvp on 1=1
                and cvp.cod_proposta = vp.cod_proposta
            LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
                AND crv.cod_modelo = v.COD_MODELO 
                AND crv.cod_produto = v.COD_PRODUTO 
                AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                AND crv.cod_empresa = v.COD_EMPRESA
            WHERE v.status = 'V'
                AND TO_CHAR(v.cod_cliente) <> '22534303000127'
                AND vp.VENDEDOR <> 'DIRETORIA'
                AND vp.COD_EMPRESA_VENDA IN (11,33)
                AND (cvp.REPASSE IS NULL OR cvp.REPASSE <> 'S')
                AND TRUNC(vp.data_venda ) >= TO_DATE('{_ini}', 'YYYY-MM-DD')
                AND TRUNC(vp.data_venda ) <= TO_DATE('{_fim}', 'YYYY-MM-DD')
        """
        cur.execute(query)
        result = cur.fetchall()
        faturados = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # Venda Estoque

        query = f"""
                SELECT 
                pr.descricao_produto familia_veiculo,
                        vp.COD_PROPOSTA, 
                        vp.EMISSAO data_proposta, 
                        vp.VENDEDOR cod_vendedor, 
                        eu.NOME_COMPLETO nome_vendedor, 
                        eu.cod_empresa empresa_vendedor,
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
                            WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                            ELSE
                                'Novo'
                        END novo_usado,
                        crv.quem_recebeu,
                        crv.created_at data_recebimento
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
                    LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
                        AND crv.cod_modelo = v.COD_MODELO 
                        AND crv.cod_produto = v.COD_PRODUTO 
                        AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                        AND crv.cod_empresa = v.COD_EMPRESA
                    WHERE v.status = 'E'
                        AND v.novo_usado = 'N'
                    ORDER BY pm.DESCRICAO_MODELO
        """
        cur.execute(query)
        result = cur.fetchall()
        venda_estoque = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])
        venda_estoque = venda_estoque[venda_estoque['EMPRESA'].isin(['CAMARGO - SOROCABA', 'INDMAR'])]
        venda_estoque = venda_estoque[venda_estoque['NOVO_USADO'] == 'Novo']
        venda_estoque = venda_estoque[venda_estoque['COD_PROPOSTA'].notnull()]

        # Venda grade
        query = f"""
            SELECT 
                pr.descricao_produto familia_veiculo,
                        vp.COD_PROPOSTA, 
                        vp.EMISSAO data_proposta, 
                        vp.VENDEDOR cod_vendedor, 
                        eu.NOME_COMPLETO nome_vendedor, 
                        eu.cod_empresa empresa_vendedor,
                        pm.DESCRICAO_MODELO modelo, 
                        COALESCE(ce.DESCRICAO, ce2.DESCRICAO) cor, 
                        v.ANO_MODELO, 
                        v.CHASSI_COMPLETO, 
                        e.NOME empresa, 
                        v.DATA_NOTA emissao,
                        p.DESCRICAO patio,
                        c.COD_CLIENTE, 
                        c.NOME nome_cliente,
                        CASE 
                            WHEN v.novo_usado = 'U' THEN 'Usado'
                            WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
                            ELSE
                                'Novo'
                        END novo_usado,
                        COALESCE(cid_com.DESCRICAO, cid_res.DESCRICAO, cid_cob.DESCRICAO) cidade,
                        cvp.ID_PROCESSO,
                        cvp.status,
                        vp.DATA_VENDA,
                        ea.DATA_AGENDADA,
                        ea.DATA_BAIXA,
                        cvp.OBS_FATURAMENTO,
                        cvp.OBS_ENTREGA,
                        cvp.OBS_LIBERACAO,
                        cvp.OBS_DOCUMENTACAO,
                        cvp.REPASSE,
                        NVL(etapas.json_etapas, '[]') AS status_processo_etapas,
                        ea.local_entrega,
                        cvp.OBS_ISENCAO,
                        cvp.OBS_ACESSORIOS,
                        cvp.DATA_SOLICITACAO,
                        crv.quem_recebeu,
                        crv.created_at data_recebimento,
                        vp2.NUMERO_FABRICA pedido_fabrica,
                        vp.COD_EMPRESA cod_empresa
                    FROM VEICULOS_PROPOSTAS vp
                    LEFT JOIN veiculos v ON 1=1
                        AND v.CHASSI_RESUMIDO = vp.CHASSI_RESUMIDO 
                        AND v.STATUS = 'E'
                    LEFT JOIN produtos pr ON 1=1
                        AND pr.COD_PRODUTO = vp.COD_PRODUTO 
                    LEFT JOIN prop_ficticia_dados pfd ON 1=1
                        AND pfd.COD_FICTICIO = vp.COD_FICTICIO
                    LEFT JOIN CORES_EXTERNAS ce ON 1=1
                        AND ce.COR_EXTERNA = v.COR_EXTERNA 
                    LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
                        AND ce2.COR_EXTERNA = pfd.COR_EXTERNA
                    LEFT JOIN produtos_modelos pm ON 1=1
                        AND pm.COD_PRODUTO = vp.COD_PRODUTO 
                        AND pm.COD_MODELO = vp.COD_MODELO 
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
                    LEFT JOIN (
                        SELECT
                            ea.COD_PROPOSTA,
                            MAX(ea.DATA_AGENDADA) DATA_AGENDADA,
                            MAX(ea.DATA_BAIXA) DATA_BAIXA,
                            MAX(es.DESCRICAO_SALA) local_entrega
                        FROM EV_AGENDADOS ea
                        LEFT JOIN EV_SALAS es ON 1=1
                            AND es.cod_sala = ea.COD_SALA
                        WHERE ea.STATUS <> 'C'
                        GROUP BY ea.COD_PROPOSTA
                    ) ea ON 1=1
                        AND ea.COD_PROPOSTA = vp.COD_PROPOSTA
                    left join caiuas_veic_proc cvp on 1=1
                        and cvp.cod_proposta = vp.cod_proposta
                    LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
                        AND crv.cod_modelo = v.COD_MODELO 
                        AND crv.cod_produto = v.COD_PRODUTO 
                        AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
                        AND crv.cod_empresa = v.COD_EMPRESA
                    LEFT JOIN veiculos_pedidos vp2 ON 1=1
                        AND vp2.cod_pedido = vp.cod_pedido
                    LEFT JOIN (
                        SELECT
                            ID_PROCESSO,
                            '[' || LISTAGG('{{"categoria":"' || CATEGORIA || '","status":"' || status_categoria || '"}}', ',')
                                   WITHIN GROUP (ORDER BY CATEGORIA) || ']' AS json_etapas
                        FROM (
                            SELECT
                                ID_PROCESSO,
                                CATEGORIA,
                                CASE
                                    WHEN COUNT(CASE WHEN STATUS <> 'Autorizado' OR STATUS IS NULL THEN 1 END) = 0
                                    THEN 'Autorizado'
                                    ELSE 'Pendente'
                                END AS status_categoria
                            FROM CAIUAS_VEIC_PROC_ETAPAS
                            WHERE ID_PROCESSO IS NOT NULL
                            GROUP BY ID_PROCESSO, CATEGORIA
                        )
                        GROUP BY ID_PROCESSO
                    ) etapas ON 1=1
                        AND etapas.ID_PROCESSO = cvp.ID_PROCESSO
                    WHERE vp.STATUS_PROPOSTA NOT IN ('C','V')
                        AND TRUNC(vp.EMISSAO ) >= TO_DATE('2024-01-01', 'YYYY-MM-DD')
                    ORDER BY CASE WHEN v.CHASSI_COMPLETO IS NOT NULL THEN 0 ELSE 1 END,
                    cvp.DATA_SOLICITACAO,vp.EMISSAO DESC
        """

        cur.execute(query)
        result = cur.fetchall()
        venda_grade = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])
        venda_grade = venda_grade[venda_grade['PEDIDO_FABRICA'].notnull()]
        todos = pd.concat([faturados, venda_grade, venda_estoque], ignore_index=True)
        varejo = todos[todos['NOVO_USADO'] == 'Novo']
        vd = todos[todos['NOVO_USADO'] == 'Direta']
        LX = todos[todos['MODELO'].str.contains(" LX", na=False)]
        todos.loc[todos['MODELO'].str.contains(" LX", na=False), 'FAMILIA_VEICULO'] = 'LX'
        todos['MODELO'] = todos['MODELO'].str.replace('AUTO - ', '', regex=False)
        col_familia = next((c for c in todos.columns if c.lower() == 'familia_veiculo'), None)
        todos[col_familia] = todos[col_familia].apply(
            lambda x: x.split('-')[1].strip() if isinstance(x, str) and len(x.split('-')) > 1 else x
        )

        Sorocaba = todos[todos['EMPRESA_VENDEDOR'] == 11]
        Indaiatuba = todos[todos['EMPRESA_VENDEDOR'] == 33]
        ordem_familias = lambda df: sorted(df.index, key=lambda x: (x != 'LX', str(x)))
        fechamento_sorocaba = Sorocaba.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
        fechamento_sorocaba = fechamento_sorocaba.reindex(ordem_familias(fechamento_sorocaba))
        fechamento_indaiatuba = Indaiatuba.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
        fechamento_indaiatuba = fechamento_indaiatuba.reindex(ordem_familias(fechamento_indaiatuba))
        todos = todos[todos['FAMILIA_VEICULO'].isin(fechamento_sorocaba.index) | todos['FAMILIA_VEICULO'].isin(fechamento_indaiatuba.index)]
        fechamento_geral = todos.groupby(['FAMILIA_VEICULO', 'NOVO_USADO']).size().unstack(fill_value=0)
        fechamento_geral = fechamento_geral.reindex(ordem_familias(fechamento_geral))

        query = f"""
            SELECT nome COD_VENDEDOR, sum(qtd) qtd_meta
            FROM caiuas_comissoes_vendedores
            WHERE 1=1
            AND EXTRACT(YEAR FROM data) = {ano}
            AND EXTRACT(month FROM data) = {mes}
            GROUP BY nome
        """
        cur.execute(query)
        result = cur.fetchall()
        meta = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # agrupa por vendedor e sua meta que é o que está em comissao
        fechamento_vendedores = pd.pivot_table(todos, index=['EMPRESA_VENDEDOR','COD_VENDEDOR','NOME_VENDEDOR'], aggfunc='size').reset_index()
        fechamento_vendedores.columns = ['EMPRESA_VENDEDOR','COD_VENDEDOR','NOME_VENDEDOR', 'Total']
        fechamento_vendedores = pd.merge(fechamento_vendedores, meta, left_on='COD_VENDEDOR', right_on='COD_VENDEDOR', how='left').fillna(0)
        fechamento_vendedores['% Meta'] = (fechamento_vendedores['Total'] / fechamento_vendedores['QTD_META']) * 100
        fechamento_vendedores['% Meta'] = fechamento_vendedores['% Meta'].round(2)

        fechamento_empresa = pd.pivot_table(fechamento_vendedores, index='EMPRESA_VENDEDOR', values=['Total', 'QTD_META'], aggfunc='sum').reset_index()
        fechamento_empresa['% Meta'] = (fechamento_empresa['Total'] / fechamento_empresa['QTD_META']) * 100
        fechamento_empresa['% Meta'] = fechamento_empresa['% Meta'].round(2)

        fechamento_empresa = fechamento_empresa.replace({'EMPRESA_VENDEDOR': {11: 'Sorocaba', 33: 'Indaiatuba'}})

        col_cliente = next((c for c in todos.columns if c.lower() == 'cod_cliente'), None)
        clientes_repetidos = todos.dropna(subset=[col_cliente])
        clientes_repetidos = clientes_repetidos[clientes_repetidos.duplicated(subset=[col_cliente], keep=False)]
        clientes_repetidos = clientes_repetidos.sort_values(by=col_cliente)

        col_modelo = next((c for c in todos.columns if c.lower() == 'familia_veiculo'), None)
        col_novo_usado = next((c for c in todos.columns if c.lower() == 'novo_usado'), None)

        query = f"""
            SELECT 
            TO_CHAR(TRUNC(f.DATA), 'YYYY-MM-DD') AS ano_mes,
        	TRUNC(f.DATA)                     AS data_feriado,
        	LISTAGG(f.MOTIVO, ', ') WITHIN GROUP (ORDER BY f.MOTIVO) AS motivos
        FROM feriado f
        WHERE 1=1
        	AND EXTRACT(YEAR FROM data) = {ano}
        	AND EXTRACT(month FROM data) = {mes}
        GROUP BY
            TO_CHAR(TRUNC(f.DATA), 'YYYY-MM-DD'),
            TRUNC(f.DATA)
        ORDER BY 
            data_feriado
        """

        cur.execute(query)
        result = cur.fetchall()
        feriados = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # quantidade de dias do mês
        qtd_dias_mes = calendar.monthrange(ano, mes)[1]

        # dias do mês que caem no domingo
        qtd_domingos = sum(
            1
            for dia in range(1, qtd_dias_mes + 1)
            if datetime.date(ano, mes, dia).weekday() == calendar.SUNDAY
        )

        # feriados que caem em dia útil (não domingo), para não descontar duas vezes
        col_feriado = next((c for c in feriados.columns if c.lower() == 'data_feriado'), None)
        qtd_feriados_uteis = 0
        if col_feriado is not None:
            for data_feriado in feriados[col_feriado]:
                if pd.notna(data_feriado) and pd.Timestamp(data_feriado).weekday() != calendar.SUNDAY:
                    qtd_feriados_uteis += 1

        qtd_dias_uteis = qtd_dias_mes - qtd_domingos - qtd_feriados_uteis
        print(qtd_dias_uteis)

        # dias úteis de hoje até o último dia do mês
        hoje = datetime.date.today()
        primeiro_dia = datetime.date(ano, mes, 1)
        ultimo_dia = datetime.date(ano, mes, qtd_dias_mes)

        datas_feriado = set()
        if col_feriado is not None:
            datas_feriado = {
                pd.Timestamp(data_feriado).date()
                for data_feriado in feriados[col_feriado]
                if pd.notna(data_feriado)
            }

        if hoje > ultimo_dia:
            qtd_dias_uteis_restantes = 0
        else:
            dia_inicio = max(primeiro_dia, hoje).day
            qtd_dias_uteis_restantes = sum(
                1
                for dia in range(dia_inicio, qtd_dias_mes + 1)
                if datetime.date(ano, mes, dia).weekday() != calendar.SUNDAY
                and datetime.date(ano, mes, dia) not in datas_feriado
            )

        print(qtd_dias_uteis_restantes)

        # meta proporcional aos dias úteis já decorridos e quanto falta para bater a meta do mês
        dias_uteis_decorridos = qtd_dias_uteis - qtd_dias_uteis_restantes

        if qtd_dias_uteis > 0:
            fechamento_empresa['Meta até agora'] = (
                fechamento_empresa['QTD_META'] * (dias_uteis_decorridos / qtd_dias_uteis)
            ).round(2)
        else:
            fechamento_empresa['Meta até agora'] = 0

        fechamento_empresa['Faltam p/ fim do mês'] = (
            fechamento_empresa['QTD_META'] - fechamento_empresa['Total']
        ).round(2)

        if qtd_dias_uteis_restantes > 0:
            fechamento_empresa['Meta por dia'] = (
                fechamento_empresa['Faltam p/ fim do mês'] / qtd_dias_uteis_restantes
            ).round(2)
        else:
            fechamento_empresa['Meta por dia'] = 0

        print(fechamento_empresa)

        # passagens e retornos por empresa (baseado em streamlit_app/views/fluxo_de_loja.py)
        # passagens do mês são contabilizadas até o dia anterior (não inclui hoje)
        # quando gerado na segunda-feira, considera o sábado (domingo não tem passagens)
        if hoje.weekday() == calendar.MONDAY:
            dia_anterior = min(hoje - datetime.timedelta(days=2), ultimo_dia)
        else:
            dia_anterior = min(hoje - datetime.timedelta(days=1), ultimo_dia)

        if dia_anterior < primeiro_dia:
            dia_anterior = None

        tipos_passagens = "785, 807"
        tipos_visitas = "819, 821, 815, 817, 810, 812, 829, 795, 793, 797, 799, 810, 812, 837, 785, 807, 835, 833"
        tipos_retornos = "819, 821, 815, 817, 810, 812, 829, 795, 793, 797, 799, 810, 812, 837, 785, 807, 835, 833"

        if dia_anterior is not None:
            primeiro_dia_sql = primeiro_dia.strftime('%Y-%m-%d')
            dia_fim_sql = dia_anterior.strftime('%Y-%m-%d')
            dia_anterior_sql = dia_anterior.strftime('%Y-%m-%d')

            query = f"""
                SELECT empresa,
                    COUNT(CASE WHEN data_passagem = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD') THEN 1 END) passagens_dia_anterior,
                    COUNT(*) passagens_mes,
                    SUM(tem_test_drive) test_drives,
                    SUM(CASE WHEN data_passagem = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD') THEN tem_test_drive ELSE 0 END) test_drives_dia_anterior
                FROM (
                    SELECT eu.cod_empresa empresa, TRUNC(ce.data_criacao) data_passagem,
                        CASE WHEN EXISTS (
                            SELECT 1 FROM caiuas_crm_test_drive cctd
                            WHERE cctd.cod_empresa = ce.cod_empresa
                              AND cctd.cod_evento = ce.cod_evento
                        ) THEN 1 ELSE 0 END tem_test_drive
                    FROM crm_eventos ce
                    LEFT JOIN empresas_usuarios eu ON 1=1
                        AND eu.nome = ce.responsavel_pelo_evento
                    WHERE ce.cod_tipo_evento IN ({tipos_passagens})
                      AND ce.status <> 'D'
                      AND eu.cod_empresa IN (11, 33)
                      AND TRUNC(ce.data_criacao) BETWEEN TO_DATE('{primeiro_dia_sql}', 'YYYY-MM-DD') AND TO_DATE('{dia_fim_sql}', 'YYYY-MM-DD')
                    UNION ALL
                    SELECT eu.cod_empresa empresa, TRUNC(ce.data_visita) data_passagem,
                        CASE WHEN EXISTS (
                            SELECT 1 FROM caiuas_crm_test_drive cctd
                            WHERE cctd.cod_empresa = ce.cod_empresa
                              AND cctd.cod_evento = ce.cod_evento
                        ) THEN 1 ELSE 0 END tem_test_drive
                    FROM crm_eventos ce
                    LEFT JOIN empresas_usuarios eu ON 1=1
                        AND eu.nome = ce.responsavel_pelo_evento
                    WHERE ce.cod_tipo_evento IN ({tipos_visitas})
                      AND ce.status <> 'D'
                      AND eu.cod_empresa IN (11, 33)
                      AND TRUNC(ce.data_visita) BETWEEN TO_DATE('{primeiro_dia_sql}', 'YYYY-MM-DD') AND TO_DATE('{dia_fim_sql}', 'YYYY-MM-DD')
                )
                GROUP BY empresa
            """
            cur.execute(query)
            result = cur.fetchall()
            passagens = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

            query = f"""
                SELECT ccr.cod_empresa empresa, COUNT(*) retornos_dia_anterior
                FROM caiuas_crm_retorno ccr
                LEFT JOIN crm_eventos ce ON 1=1
                    AND ce.cod_evento = ccr.cod_evento
                    AND ce.cod_empresa = ccr.cod_empresa
                WHERE ce.status <> 'D'
                  AND ce.cod_tipo_evento IN ({tipos_retornos})
                  AND ccr.cod_empresa IN (11, 33)
                  AND TRUNC(ccr.created_at) = TO_DATE('{dia_anterior_sql}', 'YYYY-MM-DD')
                GROUP BY ccr.cod_empresa
            """
            cur.execute(query)
            result = cur.fetchall()
            retornos = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

            passagens = pd.merge(passagens, retornos, on='EMPRESA', how='outer')

            dias_uteis_ate_atual = sum(
                1
                for dia in range(1, dia_anterior.day + 1)
                if datetime.date(ano, mes, dia).weekday() != calendar.SUNDAY
                and datetime.date(ano, mes, dia) not in datas_feriado
            )

            if dias_uteis_ate_atual > 0:
                passagens['Média passagens/dia'] = (
                    passagens['PASSAGENS_MES'] / dias_uteis_ate_atual
                ).round(2)
            else:
                passagens['Média passagens/dia'] = 0

            passagens = passagens.fillna(0)
            passagens['EMPRESA'] = passagens['EMPRESA'].replace({11: 'Sorocaba', 33: 'Indaiatuba'})
            passagens = passagens.rename(columns={
                'EMPRESA': 'Empresa',
                'PASSAGENS_DIA_ANTERIOR': 'Passagens dia anterior',
                'RETORNOS_DIA_ANTERIOR': 'Retornos dia anterior',
                'PASSAGENS_MES': 'Passagens no mês',
                'TEST_DRIVES': 'Test drives',
                'TEST_DRIVES_DIA_ANTERIOR': 'Test drives dia anterior',
            })
        else:
            passagens = pd.DataFrame(columns=[
                'Empresa', 'Passagens dia anterior', 'Retornos dia anterior', 'Passagens no mês', 'Test drives', 'Test drives dia anterior', 'Média passagens/dia'
            ])

        # print(passagens)

        # modelos de veículos (estoque x grade)
        query = """
            SELECT p.DESCRICAO_PRODUTO, pm.DESCRICAO_MODELO, pm.COD_PRODUTO, pm.COD_MODELO
            FROM PRODUTOS_MODELOS pm
            LEFT JOIN PRODUTOS p ON 1=1
                AND p.COD_PRODUTO = pm.COD_PRODUTO
            WHERE 1=1
                AND pm.ATIVO = 'S'
                AND p.DESCRICAO_PRODUTO LIKE ('AUTO-%')
                AND p.DESCRICAO_PRODUTO NOT IN (
                    --'AUTO-ACCORD ( I )',
                    'AUTO-ZR-V',
                    'AUTO-NEW FIT',
                    'AUTO-CIVIC'
                )
            ORDER BY p.DESCRICAO_PRODUTO, pm.DESCRICAO_MODELO
        """
        cur.execute(query)
        result = cur.fetchall()
        modelos_df = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # estoque por modelo
        query = """
            SELECT pm.DESCRICAO_MODELO modelo, pm.COD_PRODUTO, pm.COD_MODELO
            FROM veiculos v
            LEFT JOIN produtos pr ON pr.COD_PRODUTO = v.COD_PRODUTO
            LEFT JOIN CORES_EXTERNAS ce ON ce.COR_EXTERNA = v.COR_EXTERNA
            LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = v.COD_PRODUTO
                AND pm.COD_MODELO = v.COD_MODELO
            LEFT JOIN VEICULOS_PROPOSTAS vp ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
            LEFT JOIN patio p ON p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
            LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU
            LEFT JOIN empresas e ON e.cod_empresa = v.COD_EMPRESA
            LEFT JOIN caiuas_recebimento_veiculo crv ON crv.cod_modelo = v.COD_MODELO
                AND crv.cod_produto = v.COD_PRODUTO
                AND crv.chassi_resumido = v.CHASSI_RESUMIDO
                AND crv.cod_empresa = v.COD_EMPRESA
            WHERE v.status = 'E'
              AND e.cod_empresa IN ('11','33')
              AND NVL(v.novo_usado, 'N') <> 'U'
              AND v.COD_PROPOSTA_INTERNET IS NULL
              AND vp.COD_PROPOSTA is null
              AND NVL(vp.INTERNET, ' ') <> 'F'
              AND NVL(pm.DESCRICAO_MODELO, ' ') <> 'CR-V FH TOURING'
            ORDER BY pm.DESCRICAO_MODELO
        """
        cur.execute(query)
        result = cur.fetchall()
        estoque_modelos_df = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # grade por modelo
        query = """
            SELECT vp.COD_PRODUTO, vp.COD_MODELO
            FROM VEICULOS_PEDIDOS vp
            LEFT JOIN VEICULOS_PROPOSTAS vp2 ON 1=1
                AND vp.COD_PEDIDO = vp2.COD_PEDIDO
                AND vp2.STATUS_PROPOSTA <> 'C'
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp2.VENDEDOR
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = vp.COD_PRODUTO
                AND vp.COD_MODELO = pm.COD_MODELO
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = vp.COR_EXTERNA
            WHERE 1=1
                AND NVL(vp.STATUS_PEDIDO, ' ') <> 'E'
                AND vp.COD_EMPRESA IN (11,33)
                AND vp2.COD_PROPOSTA IS null
        """
        cur.execute(query)
        result = cur.fetchall()
        grade_modelos_df = pd.DataFrame(result, columns=[desc[0] for desc in cur.description])

        # cruza modelos com estoque e grade
        modelos_df['COD_PRODUTO'] = modelos_df['COD_PRODUTO'].astype(str)
        modelos_df['COD_MODELO'] = modelos_df['COD_MODELO'].astype(str)
        modelos_df['chave'] = modelos_df['COD_PRODUTO'] + '|' + modelos_df['COD_MODELO']

        estoque_modelos_df['chave'] = (
            estoque_modelos_df['COD_PRODUTO'].astype(str) + '|' + estoque_modelos_df['COD_MODELO'].astype(str)
        )
        grade_modelos_df['chave'] = (
            grade_modelos_df['COD_PRODUTO'].astype(str) + '|' + grade_modelos_df['COD_MODELO'].astype(str)
        )

        modelos_df['ESTOQUE'] = modelos_df['chave'].map(estoque_modelos_df.groupby('chave').size()).fillna(0).astype(int)
        modelos_df['GRADE'] = modelos_df['chave'].map(grade_modelos_df.groupby('chave').size()).fillna(0).astype(int)
        modelos_df['TOTAL'] = modelos_df['ESTOQUE'] + modelos_df['GRADE']

        # agrupa modelos repetidos (mesmo nome em anos diferentes) somando as quantidades
        modelos_df = (
            modelos_df.groupby(['DESCRICAO_PRODUTO', 'DESCRICAO_MODELO'], as_index=False)[['ESTOQUE', 'GRADE', 'TOTAL']]
            .sum()
            .sort_values(['DESCRICAO_PRODUTO', 'DESCRICAO_MODELO'])
        )

        cur.close()
        conn.close()
        # faça uma tabela com a meta x qtd vendida por empresa
        # meta_empresa = pd.pivot_table(todos, values='COD_PROPOSTA', index='EMPRESA_VENDEDOR', columns='NOVO_USADO', aggfunc='count')


        # with pd.ExcelWriter('rel_veiculos.xlsx', engine='xlsxwriter') as writer:
        #     meta.to_excel(writer, sheet_name='Meta')
        #     fechamento_vendedores.to_excel(writer, sheet_name='Fechamento Vendedores')
        #     fechamento_geral.to_excel(writer, sheet_name='Fechamento Geral')
        #     fechamento_sorocaba.to_excel(writer, sheet_name='Fechamento Sorocaba')
        #     fechamento_indaiatuba.to_excel(writer, sheet_name='Fechamento Indaiatuba')
        #     faturados.to_excel(writer, sheet_name='Faturados')
        #     venda_estoque.to_excel(writer, sheet_name='Venda_estoque')
        #     venda_grade.to_excel(writer, sheet_name='Venda_grade')
        #     varejo.to_excel(writer, sheet_name='Varejo')
        #     vd.to_excel(writer, sheet_name='VD')
        #     LX.to_excel(writer, sheet_name='LX')
        #     todos.to_excel(writer, sheet_name='Todos')
        #     clientes_repetidos.to_excel(writer, sheet_name='Clientes Repetidos')
        #     passagens.to_excel(writer, sheet_name='Passagens')


        # ============================================================
        # Dashboard de vendas em PDF (layout moderno, foco em celular)
        # ============================================================
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.patches import FancyBboxPatch, Rectangle

            COR_FUNDO = '#eef2f7'
            COR_CABECALHO = '#0f172a'
            COR_CARD = '#ffffff'
            COR_TEXTO = '#111827'
            COR_SUAVE = '#64748b'
            COR_LINHA = '#e2e8f0'
            COR_AZUL = '#2563eb'
            COR_VERDE = '#16a34a'
            COR_LARANJA = '#f59e0b'
            COR_VERMELHO = '#dc2626'

            def _num(valor):
                try:
                    return f"{int(round(float(valor))):,}".replace(',', '.')
                except (TypeError, ValueError):
                    return '0'

            def _limpar_familia(nome):
                if isinstance(nome, str) and len(nome.split('-')) > 1:
                    return nome.split('-')[1].strip()
                return nome

            def _montar_posicao(df):
                posicao = (
                    df.groupby(['FAMILIA_VEICULO', 'NOVO_USADO'])
                    .size()
                    .unstack(fill_value=0)
                )
                for coluna in ['Novo', 'Direta']:
                    if coluna not in posicao.columns:
                        posicao[coluna] = 0
                posicao = posicao[['Novo', 'Direta']]
                total = int(posicao['Novo'].sum() + posicao['Direta'].sum())
                posicao = posicao.sort_values(['Novo', 'Direta'], ascending=False)
                linhas = [
                    [modelo, _num(linha['Novo']), _num(linha['Direta'])]
                    for modelo, linha in posicao.iterrows()
                ]
                return linhas, total

            def _montar_posicao_vendedor(df, codigos=(11, 33)):
                lojas = {11: 'Sorocaba', 33: 'Indaiatuba'}
                base = df.copy()
                base['EMPRESA_VENDEDOR'] = pd.to_numeric(base['EMPRESA_VENDEDOR'], errors='coerce')
                base = base[base['EMPRESA_VENDEDOR'].isin(codigos)]
                posicao = (
                    base.groupby(['EMPRESA_VENDEDOR', 'COD_VENDEDOR', 'NOME_VENDEDOR', 'NOVO_USADO'])
                    .size()
                    .unstack(fill_value=0)
                )
                for coluna in ['Novo', 'Direta']:
                    if coluna not in posicao.columns:
                        posicao[coluna] = 0
                posicao = posicao[['Novo', 'Direta']].reset_index()

                linhas = []
                total_novo = 0
                total_direta = 0
                for codigo in codigos:
                    grupo = posicao[posicao['EMPRESA_VENDEDOR'] == codigo]
                    if grupo.empty:
                        continue
                    loja = lojas.get(codigo, str(codigo))
                    grupo = grupo.sort_values('NOME_VENDEDOR')
                    for zebra, (_, linha) in enumerate(grupo.iterrows()):
                        nome = linha['NOME_VENDEDOR']
                        if pd.isna(nome) or str(nome).strip() == '':
                            nome = linha['COD_VENDEDOR']
                        linhas.append(('item', loja, str(nome),
                                       int(linha['Novo']), int(linha['Direta']), zebra))
                    sub_novo = int(grupo['Novo'].sum())
                    sub_direta = int(grupo['Direta'].sum())
                    linhas.append(('subtotal', f'Subtotal {loja}', '',
                                   sub_novo, sub_direta, 0))
                    total_novo += sub_novo
                    total_direta += sub_direta
                linhas.append(('total', 'Total geral', '', total_novo, total_direta, 0))
                return linhas

            def _box(ax, x, y, w, h, cor=COR_CARD, raio=0.14):
                ax.add_patch(FancyBboxPatch(
                    (x, y), w, h,
                    boxstyle=f"round,pad=0,rounding_size={raio}",
                    linewidth=0, facecolor=cor, mutation_aspect=1,
                ))

            def _titulo(ax, x, y, texto, cor=COR_AZUL):
                ax.add_patch(Rectangle((x, y - 0.26), 0.07, 0.26, facecolor=cor, edgecolor='none'))
                ax.text(x + 0.18, y - 0.13, texto, ha='left', va='center',
                        fontsize=12.5, color=COR_TEXTO, fontweight='bold')
                return y - 0.42

            def _tabela(ax, x, y_topo, largura, cabecalhos, linhas, fracoes,
                        altura_linha=0.34, altura_cabecalho=0.42, fonte=9.5):
                xs = [x]
                for fracao in fracoes[:-1]:
                    xs.append(xs[-1] + largura * fracao)

                ax.add_patch(Rectangle((x, y_topo - altura_cabecalho), largura, altura_cabecalho,
                                       facecolor=COR_CABECALHO, edgecolor='none'))
                for i, cabecalho in enumerate(cabecalhos):
                    largura_col = largura * fracoes[i]
                    alinhamento = 'left' if i == 0 else 'right'
                    tx = xs[i] + 0.14 if i == 0 else xs[i] + largura_col - 0.14
                    ax.text(tx, y_topo - altura_cabecalho / 2, str(cabecalho), ha=alinhamento,
                            va='center', fontsize=fonte, color='#ffffff', fontweight='bold')

                y = y_topo - altura_cabecalho
                for indice, linha in enumerate(linhas):
                    fundo = '#f8fafc' if indice % 2 == 0 else '#ffffff'
                    ax.add_patch(Rectangle((x, y - altura_linha), largura, altura_linha,
                                           facecolor=fundo, edgecolor='none'))
                    for i, valor in enumerate(linha):
                        largura_col = largura * fracoes[i]
                        alinhamento = 'left' if i == 0 else 'right'
                        tx = xs[i] + 0.14 if i == 0 else xs[i] + largura_col - 0.14
                        ax.text(tx, y - altura_linha / 2, str(valor), ha=alinhamento, va='center',
                                fontsize=fonte, color=COR_TEXTO)
                    y -= altura_linha

                ax.add_patch(Rectangle((x, y), largura, y_topo - y, fill=False,
                                       edgecolor=COR_LINHA, linewidth=1))
                return y

            def _tabela_modelos(ax, x, y_topo, largura, linhas):
                cabecalhos = ['Modelo', 'Estoque', 'Grade', 'Total']
                fracoes = [0.52, 0.16, 0.16, 0.16]
                altura_cabecalho = 0.42
                altura_linha = 0.32
                fonte = 8.5

                xs = [x]
                for fracao in fracoes[:-1]:
                    xs.append(xs[-1] + largura * fracao)

                ax.add_patch(Rectangle((x, y_topo - altura_cabecalho), largura, altura_cabecalho,
                                       facecolor=COR_CABECALHO, edgecolor='none'))
                for i, cabecalho in enumerate(cabecalhos):
                    largura_col = largura * fracoes[i]
                    alinhamento = 'left' if i == 0 else 'right'
                    tx = xs[i] + 0.14 if i == 0 else xs[i] + largura_col - 0.14
                    ax.text(tx, y_topo - altura_cabecalho / 2, cabecalho, ha=alinhamento,
                            va='center', fontsize=9.5, color='#ffffff', fontweight='bold')

                y = y_topo - altura_cabecalho
                for tipo, modelo, estoque, grade, total, zebra in linhas:
                    if tipo == 'item':
                        fundo = '#f8fafc' if zebra % 2 == 0 else '#ffffff'
                        cor, peso, prefixo = COR_TEXTO, 'normal', '   '
                    elif tipo == 'subtotal':
                        fundo, cor, peso, prefixo = '#dbeafe', COR_TEXTO, 'bold', ''
                    else:
                        fundo, cor, peso, prefixo = COR_CABECALHO, '#ffffff', 'bold', ''

                    ax.add_patch(Rectangle((x, y - altura_linha), largura, altura_linha,
                                           facecolor=fundo, edgecolor='none'))
                    for i, valor in enumerate([prefixo + str(modelo), _num(estoque), _num(grade), _num(total)]):
                        largura_col = largura * fracoes[i]
                        alinhamento = 'left' if i == 0 else 'right'
                        tx = xs[i] + 0.14 if i == 0 else xs[i] + largura_col - 0.14
                        ax.text(tx, y - altura_linha / 2, valor, ha=alinhamento, va='center',
                                fontsize=fonte, color=cor, fontweight=peso)
                    y -= altura_linha

                ax.add_patch(Rectangle((x, y), largura, y_topo - y, fill=False,
                                       edgecolor=COR_LINHA, linewidth=1))
                return y

            def _tabela_vendedores(ax, x, y_topo, largura, linhas):
                cabecalhos = ['Loja', 'Vendedor', 'Novo', 'Direta']
                fracoes = [0.2, 0.4, 0.2, 0.2]
                alinhados_esquerda = (0, 1)
                altura_cabecalho = 0.42
                altura_linha = 0.32
                fonte = 8.5

                xs = [x]
                for fracao in fracoes[:-1]:
                    xs.append(xs[-1] + largura * fracao)

                ax.add_patch(Rectangle((x, y_topo - altura_cabecalho), largura, altura_cabecalho,
                                       facecolor=COR_CABECALHO, edgecolor='none'))
                for i, cabecalho in enumerate(cabecalhos):
                    largura_col = largura * fracoes[i]
                    alinhamento = 'left' if i in alinhados_esquerda else 'right'
                    tx = xs[i] + 0.14 if i in alinhados_esquerda else xs[i] + largura_col - 0.14
                    ax.text(tx, y_topo - altura_cabecalho / 2, cabecalho, ha=alinhamento,
                            va='center', fontsize=9.5, color='#ffffff', fontweight='bold')

                y = y_topo - altura_cabecalho
                for tipo, loja, nome, novo, direta, zebra in linhas:
                    if tipo == 'item':
                        fundo = '#f8fafc' if zebra % 2 == 0 else '#ffffff'
                        cor, peso = COR_TEXTO, 'normal'
                    elif tipo == 'subtotal':
                        fundo, cor, peso = '#dbeafe', COR_TEXTO, 'bold'
                    else:
                        fundo, cor, peso = COR_CABECALHO, '#ffffff', 'bold'

                    ax.add_patch(Rectangle((x, y - altura_linha), largura, altura_linha,
                                           facecolor=fundo, edgecolor='none'))
                    for i, valor in enumerate([loja, nome, _num(novo), _num(direta)]):
                        largura_col = largura * fracoes[i]
                        alinhamento = 'left' if i in alinhados_esquerda else 'right'
                        tx = xs[i] + 0.14 if i in alinhados_esquerda else xs[i] + largura_col - 0.14
                        ax.text(tx, y - altura_linha / 2, str(valor), ha=alinhamento, va='center',
                                fontsize=fonte, color=cor, fontweight=peso)
                    y -= altura_linha

                ax.add_patch(Rectangle((x, y), largura, y_topo - y, fill=False,
                                       edgecolor=COR_LINHA, linewidth=1))
                return y

            def gerar_dashboard_pdf(caminho='dashboard_vendas.pdf'):
                # vendidos = mesma base da planilha "Fechamento Geral" (df todos)
                vendas_dash = todos.copy()
                vendas_dash = vendas_dash[vendas_dash['NOVO_USADO'].isin(['Novo', 'Direta'])]

                vendido_loja = {
                    int(codigo): int(qtd)
                    for codigo, qtd in vendas_dash.groupby('EMPRESA_VENDEDOR').size().items()
                    if pd.notna(codigo)
                }

                posicao_linhas, _ = _montar_posicao(vendas_dash)
                total_vendido = int(vendas_dash.shape[0])

                codigo_loja = pd.to_numeric(vendas_dash['EMPRESA_VENDEDOR'], errors='coerce')
                posicao_sorocaba_linhas, _ = _montar_posicao(vendas_dash[codigo_loja == 11])
                posicao_indaiatuba_linhas, _ = _montar_posicao(vendas_dash[codigo_loja == 33])
                posicao_vendedor_linhas = _montar_posicao_vendedor(vendas_dash)

                # propostas de empresas diferentes de Sorocaba (11) e Indaiatuba (33)
                outras_empresas = todos.copy()
                outras_empresas['EMPRESA_VENDEDOR'] = pd.to_numeric(
                    outras_empresas['EMPRESA_VENDEDOR'], errors='coerce'
                )
                outras_empresas = outras_empresas[
                    outras_empresas['EMPRESA_VENDEDOR'].notna()
                    & ~outras_empresas['EMPRESA_VENDEDOR'].isin([11, 33])
                ]
                outras_empresas_linhas = []
                for _, linha in outras_empresas.sort_values('EMPRESA_VENDEDOR').iterrows():
                    nome = linha.get('NOME_VENDEDOR')
                    if pd.isna(nome) or str(nome).strip() == '':
                        nome = linha.get('COD_VENDEDOR')
                    data = linha.get('DATA_PROPOSTA')
                    try:
                        data_txt = pd.to_datetime(data).strftime('%d/%m/%Y') if pd.notna(data) else ''
                    except (TypeError, ValueError):
                        data_txt = str(data)
                    proposta = linha.get('COD_PROPOSTA')
                    proposta_txt = '' if pd.isna(proposta) else str(proposta)
                    outras_empresas_linhas.append([
                        str(int(linha['EMPRESA_VENDEDOR'])), str(nome), proposta_txt, data_txt,
                    ])

                meta_total = int(fechamento_empresa['QTD_META'].sum())
                percentual_meta = (total_vendido / meta_total * 100) if meta_total else 0

                # meta por loja (com o percentual atingido de cada uma) e quanto falta por loja
                meta_loja_linhas = []
                faltam_loja = {}
                for loja, meta in fechamento_empresa[['EMPRESA_VENDEDOR', 'QTD_META']].values.tolist():
                    codigo = 11 if loja == 'Sorocaba' else 33
                    vendido = vendido_loja.get(codigo, 0)
                    percentual = (vendido / meta * 100) if meta else 0
                    meta_loja_linhas.append([loja, _num(meta), _num(vendido), f"{percentual:.1f}%"])
                    faltam_loja[loja] = int(meta) - vendido

                # total que falta para bater a meta (meta - vendido)
                total_faltam = meta_total - total_vendido
                meta_por_dia = (
                    total_faltam / qtd_dias_uteis_restantes if qtd_dias_uteis_restantes else 0
                )
                meta_por_dia_loja = {
                    loja: (falta / qtd_dias_uteis_restantes if qtd_dias_uteis_restantes else 0)
                    for loja, falta in faltam_loja.items()
                }

                # fluxo de loja (passagens e test drives) - geral e por loja
                fluxo_base = passagens.copy()
                for coluna in ('Passagens dia anterior', 'Passagens no mês',
                               'Test drives dia anterior', 'Test drives', 'Média passagens/dia'):
                    if coluna not in fluxo_base.columns:
                        fluxo_base[coluna] = 0

                def _soma(coluna):
                    return float(fluxo_base[coluna].sum())

                fluxo_linhas = [[
                    'Geral',
                    _num(_soma('Passagens dia anterior')),
                    _num(_soma('Passagens no mês')),
                    f"{_soma('Média passagens/dia'):.1f}",
                    _num(_soma('Test drives dia anterior')),
                    _num(_soma('Test drives')),
                ]]
                for _, linha in fluxo_base.iterrows():
                    fluxo_linhas.append([
                        linha['Empresa'],
                        _num(linha['Passagens dia anterior']),
                        _num(linha['Passagens no mês']),
                        f"{float(linha['Média passagens/dia']):.1f}",
                        _num(linha['Test drives dia anterior']),
                        _num(linha['Test drives']),
                    ])

                # modelos (estoque x grade) com subtotal por descrição de produto
                modelos_linhas = []
                zebra = 0
                for produto, grupo in modelos_df.groupby('DESCRICAO_PRODUTO', sort=False):
                    for _, linha in grupo.iterrows():
                        modelos_linhas.append((
                            'item', linha['DESCRICAO_MODELO'],
                            int(linha['ESTOQUE']), int(linha['GRADE']), int(linha['TOTAL']), zebra,
                        ))
                        zebra += 1
                    modelos_linhas.append((
                        'subtotal', f"Subtotal {produto}",
                        int(grupo['ESTOQUE'].sum()), int(grupo['GRADE'].sum()), int(grupo['TOTAL'].sum()), 0,
                    ))
                modelos_linhas.append((
                    'total', 'Total geral',
                    int(modelos_df['ESTOQUE'].sum()), int(modelos_df['GRADE'].sum()), int(modelos_df['TOTAL'].sum()), 0,
                ))

                # layout
                LARGURA = 8.27
                MARGEM = 0.5
                UTIL = LARGURA - 2 * MARGEM
                ALTURA_LINHA = 0.34

                n_meta = max(len(meta_loja_linhas), 1)
                n_pos = max(len(posicao_linhas), 1)
                n_pos_sor = max(len(posicao_sorocaba_linhas), 1)
                n_pos_ind = max(len(posicao_indaiatuba_linhas), 1)
                n_vend = len(posicao_vendedor_linhas)
                n_fluxo = max(len(fluxo_linhas), 1)
                n_modelos = len(modelos_linhas)
                n_outras = len(outras_empresas_linhas)

                def secao(n):
                    return 0.42 + (0.42 + n * ALTURA_LINHA)

                altura = 0.45 + 1.15 + 0.55 + 1.2 + 0.35 + 1.2 + 0.35 + 1.2 + 0.6
                altura += secao(n_meta) + 0.62
                altura += secao(n_pos) + 0.62
                altura += secao(n_pos_sor) + 0.62
                altura += secao(n_pos_ind) + 0.62
                altura += 0.42 + (0.42 + n_vend * 0.32) + 0.62
                altura += secao(n_fluxo) + 0.62
                altura += 0.42 + (0.42 + n_modelos * 0.32) + 0.62
                if n_outras:
                    altura += secao(n_outras) + 0.62
                altura += 0.45

                fig = plt.figure(figsize=(LARGURA, altura), dpi=200)
                fig.patch.set_facecolor(COR_FUNDO)
                ax = fig.add_axes([0, 0, 1, 1])
                ax.set_xlim(0, LARGURA)
                ax.set_ylim(0, altura)
                ax.axis('off')

                y = altura - 0.45

                # cabeçalho
                _box(ax, MARGEM, y - 1.15, UTIL, 1.15, COR_CABECALHO)
                ax.text(MARGEM + 0.35, y - 0.42, 'Dashboard de Vendas', color='#ffffff',
                        fontsize=19, fontweight='bold', va='center')
                ax.text(MARGEM + 0.35, y - 0.82, 'Caiuás  •  Sorocaba & Indaiatuba', color='#94a3b8',
                        fontsize=10.5, va='center')
                ax.text(LARGURA - MARGEM - 0.35, y - 0.42, 'Relatório gerado em', color='#94a3b8',
                        fontsize=10, ha='right', va='center')
                ax.text(LARGURA - MARGEM - 0.35, y - 0.82,
                        datetime.datetime.now().strftime('%d/%m/%Y %H:%M'), color='#ffffff',
                        fontsize=15, fontweight='bold', ha='right', va='center')
                y -= 1.15 + 0.55

                # KPIs
                kpis_linha1 = [
                    ('Meta das lojas', _num(meta_total), COR_AZUL),
                    ('Vendidos', _num(total_vendido), COR_VERDE),
                    ('% da meta', f"{percentual_meta:.1f}%", COR_LARANJA),
                    ('Dias úteis restantes', _num(qtd_dias_uteis_restantes), COR_AZUL),
                ]
                kpis_linha2 = [
                    ('Faltam (geral)', _num(total_faltam), COR_VERMELHO),
                    ('Faltam Sorocaba', _num(faltam_loja.get('Sorocaba', 0)), COR_VERMELHO),
                    ('Faltam Indaiatuba', _num(faltam_loja.get('Indaiatuba', 0)), COR_VERMELHO),
                ]
                kpis_linha3 = [
                    ('Meta por dia', f"{meta_por_dia:.1f}", COR_LARANJA),
                    ('Meta/dia Sorocaba', f"{meta_por_dia_loja.get('Sorocaba', 0):.1f}", COR_LARANJA),
                    ('Meta/dia Indaiatuba', f"{meta_por_dia_loja.get('Indaiatuba', 0):.1f}", COR_LARANJA),
                ]
                gap = 0.18
                altura_kpi = 1.2

                def desenhar_linha_kpis(kpis, y):
                    largura_kpi = (UTIL - gap * (len(kpis) - 1)) / len(kpis)
                    for i, (rotulo, valor, cor) in enumerate(kpis):
                        x = MARGEM + i * (largura_kpi + gap)
                        _box(ax, x, y - altura_kpi, largura_kpi, altura_kpi)
                        ax.add_patch(Rectangle((x + 0.12, y - altura_kpi), largura_kpi - 0.24, 0.08,
                                               facecolor=cor, edgecolor='none'))
                        centro = x + largura_kpi / 2
                        ax.text(centro, y - 0.42, rotulo, fontsize=9, color=COR_SUAVE,
                                va='center', ha='center')
                        ax.text(centro, y - 0.82, valor, fontsize=17, color=COR_TEXTO,
                                fontweight='bold', va='center', ha='center')
                    return y - altura_kpi

                y = desenhar_linha_kpis(kpis_linha1, y)
                y -= 0.35
                y = desenhar_linha_kpis(kpis_linha2, y)
                y -= 0.35
                y = desenhar_linha_kpis(kpis_linha3, y)
                y -= 0.6

                y = _titulo(ax, MARGEM, y, 'META')
                y = _tabela(ax, MARGEM, y, UTIL, ['Loja', 'Meta', 'Vendas', '% da meta'],
                            meta_loja_linhas, [0.4, 0.2, 0.2, 0.2])
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Posição atual geral')
                y = _tabela(ax, MARGEM, y, UTIL, ['Modelo', 'Novo', 'Direta'],
                            posicao_linhas, [0.55, 0.225, 0.225])
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Posição atual - Sorocaba')
                y = _tabela(ax, MARGEM, y, UTIL, ['Modelo', 'Novo', 'Direta'],
                            posicao_sorocaba_linhas, [0.55, 0.225, 0.225])
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Posição atual - Indaiatuba')
                y = _tabela(ax, MARGEM, y, UTIL, ['Modelo', 'Novo', 'Direta'],
                            posicao_indaiatuba_linhas, [0.55, 0.225, 0.225])
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Posição atual por vendedor')
                y = _tabela_vendedores(ax, MARGEM, y, UTIL, posicao_vendedor_linhas)
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Fluxo de loja (passagens e test drives)')
                y = _tabela(ax, MARGEM, y, UTIL,
                            ['Loja', 'Pass. dia ant.', 'Pass. mês', 'Média/dia', 'TD dia ant.', 'TD mês'],
                            fluxo_linhas, [0.22, 0.16, 0.15, 0.15, 0.16, 0.16])
                y -= 0.62

                y = _titulo(ax, MARGEM, y, 'Veículos disponíveis por modelo (estoque x grade)')
                y = _tabela_modelos(ax, MARGEM, y, UTIL, modelos_linhas)
                y -= 0.62

                if n_outras:
                    y = _titulo(ax, MARGEM, y,
                                'Propostas de outras empresas (revisar cadastro)', COR_VERMELHO)
                    y = _tabela(ax, MARGEM, y, UTIL,
                                ['Empresa', 'Vendedor', 'Proposta', 'Emissão'],
                                outras_empresas_linhas, [0.12, 0.4, 0.24, 0.24])
                    y -= 0.62

                fig.savefig(caminho, format='pdf', facecolor=COR_FUNDO)
                plt.close(fig)
                print(f'Dashboard salvo em {caminho}')

            _buffer = io.BytesIO()
            gerar_dashboard_pdf(_buffer)
        except Exception as erro:
            print(f'Dashboard não gerado: {erro}')

        _buffer.seek(0)
        return _buffer, f'dashboard_showroom_{ano}_{mes:02d}.pdf'
    except Exception as e:
        raise
