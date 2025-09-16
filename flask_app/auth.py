import os
import jwt
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta, timezone

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            token_parts = auth_header.split(' ')
            
            if len(token_parts) == 2 and token_parts[0] == 'Bearer':
                token = token_parts[1]

        if not token:
            return jsonify({'message': 'Usuário não autenticado!'}), 401

        try:
            # Nota: O fuso horário de Brasília (BRT) é UTC-3
            fuso_horario = timezone(timedelta(hours=-3))
            
            # Decodifica o token
            token_data = jwt.decode(token, os.getenv('SECRET_KEY_BASE'), algorithms=["HS256"])
            
            # Verifica a expiração
            if token_data['exp'] < datetime.now(fuso_horario).timestamp():
                return jsonify({'message': 'Token expirado!'}), 401
        
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expirado!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token inválido!'}), 401
        except Exception as e:
            return jsonify({"message": 'Erro interno na autenticação', "error": str(e)}), 500

        # Adiciona os dados decodificados ao objeto request para uso na rota
        setattr(request, 'token_data', token_data)  

        return f(*args, **kwargs)

    return decorated