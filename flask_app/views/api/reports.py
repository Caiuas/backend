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
                ce.RESPONSAVEL_PELO_EVENTO,
                eu.NOME_COMPLETO,
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
                oa.status_agenda
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
                and o.complemento <> 'S'
                AND o.ORCAMENTO <> 'S'
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.NOME = oa.CONSULTOR
            where 
                1=1
            --            pb.COD_EMPRESA_FILTRO = 11
                AND oa.PRISMA IS NOT null
                and   trunc(s.data_fim) >= trunc(TO_DATE('{initial_date_str}', 'YYYY-MM-DD'))
                and   trunc(s.data_comeca) <=  trunc(TO_DATE('{final_date_str}', 'YYYY-MM-DD'))
            order by s.data_comeca
            """
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
            'status_agenda'
        ])
        agenda_por_responsavel = pd.pivot_table(
            df,
            index=['agente_sac'],
            values=['numero_os'],
            aggfunc=lambda x: x.count(),
            fill_value=0
        )
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

        worksheet = workbook.add_worksheet('Agenda')
        worksheet.merge_range('A1:K1', 'Agenda', workbook.add_format({'bold': True, 'font_size': 26, 'align': 'center', 'valign': 'vcenter'})) 
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
        worksheet.add_table(f'A2:K{cont+2}', {'columns': [{'header': 'COD_EMPRESA'},
                                                        {'header': 'COD_OS_AGENDA'},
                                                        {'header': 'NOME_CLIENTE'},
                                                        {'header': 'CRM_COD_EVENTO'},
                                                        {'header': 'AGENTE_SAC'},
                                                        {'header': 'DESCRICAO_PRISMA_BOX'},
                                                        {'header': 'PLACA'},
                                                        {'header': 'DESCRICAO_MODELO'},
                                                        {'header': 'DATA'},
                                                        {'header': 'NUMERO_OS'},
                                                        {'header': 'CONSULTOR'}],
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
        workbook.close()
        # retorna o arquivo
        file_memory.seek(0)
        response = Response(file_memory.read(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers.set('Content-Disposition', 'attachment', filename='agenda_por_responsavel.xlsx')
        response.headers.set('Content-Length', str(file_memory.tell()))
        return response, 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 400