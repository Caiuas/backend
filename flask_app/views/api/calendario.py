from flask import Blueprint, jsonify, request
from database import oracle
from dotenv import load_dotenv
from datetime import datetime
import calendar
from auth import token_required
load_dotenv()

calendario_bp = Blueprint('calendario', __name__)

DIAS_SEMANA = ['Segunda-feira', 'Terca-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sabado', 'Domingo']


def valida_data(data):
    try:
        return datetime.strptime(data, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None


@calendario_bp.route('/api/calendario/mes', methods=['GET'])
@token_required
def get_calendario_mes():
    try:
        mes = request.args.get('mes', None)
        ano = request.args.get('ano', None)
        if not mes or not ano:
            return jsonify({'status': 'error', 'message': 'Os parâmetros mes e ano são obrigatórios'}), 400
        try:
            mes = int(mes)
            ano = int(ano)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'mes e ano devem ser numéricos'}), 400
        if mes < 1 or mes > 12:
            return jsonify({'status': 'error', 'message': 'mes deve estar entre 1 e 12'}), 400

        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT TO_CHAR(f.DATA, 'YYYY-MM-DD') AS DATA, f.MOTIVO
            FROM FERIADO f
            WHERE EXTRACT(YEAR FROM f.DATA) = {ano}
                AND EXTRACT(MONTH FROM f.DATA) = {mes}
            ORDER BY f.DATA
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()

        bloqueios = {}
        for row in rows:
            bloqueios[row[0]] = row[1]

        primeiro_dia_semana, total_dias = calendar.monthrange(ano, mes)

        retorno = {
            'status': 'success',
            'mes': mes,
            'ano': ano,
            'total_bloqueios': len(bloqueios),
            'dias': []
        }
        for dia in range(1, total_dias + 1):
            data_str = f"{ano:04d}-{mes:02d}-{dia:02d}"
            dia_semana = calendar.weekday(ano, mes, dia)
            retorno['dias'].append({
                'data': data_str,
                'dia': dia,
                'dia_semana': dia_semana,
                'dia_semana_nome': DIAS_SEMANA[dia_semana],
                'feriado': data_str in bloqueios,
                'bloqueio': data_str in bloqueios,
                'motivo': bloqueios.get(data_str)
            })

        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@calendario_bp.route('/api/calendario/bloqueio', methods=['POST'])
@token_required
def add_bloqueio():
    try:
        dados = request.get_json()
        data = dados.get('data', None)
        motivo = dados.get('motivo', None)
        if not data or not motivo:
            return jsonify({'status': 'error', 'message': 'data e motivo são obrigatórios'}), 400
        if not valida_data(data):
            return jsonify({'status': 'error', 'message': 'Data inválida. Use o formato YYYY-MM-DD'}), 400

        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(f"""
            SELECT COUNT(*) FROM FERIADO f
            WHERE TRUNC(f.DATA) = TO_DATE('{data}', 'YYYY-MM-DD')
        """)
        count = cur_oracle.fetchone()[0]
        if count > 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Já existe um bloqueio/feriado para essa data'}), 409

        motivo_sql = str(motivo).replace("'", "''")
        query = f"""
            INSERT INTO FERIADO (DATA, MOTIVO)
            VALUES (TO_DATE('{data}', 'YYYY-MM-DD'), '{motivo_sql}')
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Bloqueio cadastrado com sucesso'}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@calendario_bp.route('/api/calendario/bloqueio/<data>', methods=['DELETE'])
@token_required
def remove_bloqueio(data):
    try:
        if not valida_data(data):
            return jsonify({'status': 'error', 'message': 'Data inválida. Use o formato YYYY-MM-DD'}), 400

        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(f"""
            SELECT COUNT(*) FROM FERIADO f
            WHERE TRUNC(f.DATA) = TO_DATE('{data}', 'YYYY-MM-DD')
        """)
        count = cur_oracle.fetchone()[0]
        if count == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Nenhum bloqueio/feriado encontrado para essa data'}), 404

        query = f"""
            DELETE FROM FERIADO
            WHERE TRUNC(DATA) = TO_DATE('{data}', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Bloqueio removido com sucesso'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
