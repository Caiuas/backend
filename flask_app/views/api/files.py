from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from auth import token_required
import uuid
import boto3
from botocore.config import Config
from database import postgres_site, oracle

load_dotenv()
files_bp = Blueprint('files_bp', __name__)

@files_bp.route('/api/files/generate_presigned_url', methods=['POST'])
# @token_required # Descomente se for usar autenticação
def generate_presigned_url():
    try:
        # 1. Captura os dados
        file_name = request.json.get('file_name')
        file_size = request.json.get('file_size')
        file_type = request.json.get('file_type') # Recebe ex: "image/png"

        # Validações básicas
        if not file_name:
            return jsonify({"error": "file_name is required"}), 400
        
        # 2. Tratamento do Content-Type (O PULO DO GATO)
        # Se não vier tipo, usamos binário genérico.
        # JAMAIS formate isso como string "'content-type': ...", use o valor puro.
        if not file_type:
            file_type = 'application/octet-stream'

        # 3. Prepara o caminho do arquivo
        uuid_str = str(uuid.uuid4())
        now = datetime.now()
        date_path = now.strftime("%Y/%m/%d")
        # Nome final no S3
        full_file_name = f"{date_path}/{uuid_str}"

        # 4. Configura o Cliente S3 com Assinatura v4
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='sa-east-1',
            config=Config(signature_version='s3v4') # Força padrão seguro
        )

        # 5. Gera a URL Assinada
        # O 'ContentType' aqui deve ser EXATAMENTE igual ao header do frontend
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': 'processos-caiuas', 
                'Key': full_file_name, 
                'ContentType': file_type 
            },
            ExpiresIn=3600
        )
        
        print(f"DEBUG - Gerado URL para: {full_file_name} | Tipo: {file_type}")

        return jsonify({
            "presigned_url": presigned_url,
            "key": full_file_name, # Útil retornar a chave para salvar no banco depois
            "bucket": 'processos-caiuas',
            "content_type": file_type,
            "region": 'sa-east-1'
        }), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"error": str(e)}), 500
    
@files_bp.route('/api/files/register_file', methods=['POST'])
# @token_required # Descomente se for usar autenticação
def register_file():
    try:
        # 1. Captura os dados
        file_key = request.json.get('file_key') # A chave gerada no S3 (ex: "2024/06/10/uuid")
        file_name = request.json.get('file_name') # O nome original do arquivo (ex: "foto.png")
        file_type = request.json.get('file_type') # O tipo do arquivo (ex: "image/png")
        file_size = request.json.get('file_size') # O tamanho do arquivo em bytes

        # Validações básicas
        if not file_key or not file_name or not file_type:
            return jsonify({"error": "file_key, file_name and file_type are required"}), 400

        # 2. Aqui você pode salvar as informações no banco de dados
        # Exemplo: Salvar na tabela 'files' com colunas (id, key, name, type, created_at)
        # db.execute("INSERT INTO files (key, name, type) VALUES (%s, %s, %s)", (file_key, file_name, file_type))
        
        query = f"""
            insert into files (filename, url, file_size, old_filename, created_at) values (
                '{file_key}', 
                'https://processos-caiuas.s3.sa-east-1.amazonaws.com/{file_key}', 
                {file_size}, 
                '{file_name}', 
                now()
            )
            RETURNING id_file
        """
        conn, cursor = postgres_site()
        cursor.execute(query)
        id_file = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        retorno = {}
        retorno['id_file'] = id_file
        retorno['filename'] = file_key
        retorno['url'] = f'https://processos-caiuas.s3.sa-east-1.amazonaws.com/{file_key}'
        retorno['file_size'] = file_size
        retorno['old_filename'] = file_name
        retorno['created_at'] = datetime.now().isoformat()
        retorno['message'] = "File registered successfully"

        print(f"DEBUG - Registrado arquivo: {file_key} | Nome: {file_name} | Tipo: {file_type}")

        return jsonify(retorno), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"error": str(e)}), 500
    
@files_bp.route('/api/files/register_file_processos', methods=['POST'])
@token_required # Descomente se for usar autenticação
def register_file_processos():
    try:
        # 1. Captura os dados
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        file_key = request.json.get('file_key') # A chave gerada no S3 (ex: "2024/06/10/uuid")
        bucket = request.json.get('bucket') # O nome original do arquivo (ex: "foto.png")
        file_size = request.json.get('file_size') # O tipo do arquivo (ex: "image/png")
        content_type = request.json.get('content_type') # O tamanho do arquivo em bytes
        id_processo = request.json.get('id_processo') # ID do processo
        region = request.json.get('region') # Região do bucket (ex: "sa-east-1")
        old_file_name = request.json.get('old_file_name') # O nome original do arquivo (ex: "foto.png")

        # Validações básicas
        # Se todas as keys não forem fornecidas, retorna erro
        if not all([file_key, bucket, file_size, content_type, region]):
            return jsonify({"error": "file_key, bucket, file_size, content_type, and region are required"}), 400
        
        query = f"""
            select count(*) from caiuas_veic_proc cvp
            where 1=1
                and cvp.id_processo = {id_processo}
                and cvp.ativo = 1
        """
        conn_oracle, cursor_oracle = oracle()
        cursor_oracle.execute(query)
        result = cursor_oracle.fetchone()
        if result[0] == 0:
            cursor_oracle.close()
            conn_oracle.close()
            return jsonify({"message": "Processo finalizado ou inativo"}), 400
        
        
        
        query = f"""
            SELECT eu.NOME  
            FROM empresas_usuarios eu
            WHERE 1=1
                AND lower(eu.EMAIL) = '{email.strip().lower()}'
        """
        cursor_oracle.execute(query)
        results = cursor_oracle.fetchall()
        if not results:
            cursor_oracle.close()
            conn_oracle.close()
            return jsonify({"message": "Usuário não encontrado no NBS"}), 400
        usuarios_list = []
        for row in results:
            usuarios_list.append(str(row[0]).lower())
        
        query = f"""
            SELECT caiuas_files_seq.NEXTVAL FROM dual
        """
        cursor_oracle.execute(query)
        id_file = cursor_oracle.fetchone()[0]
        query = f"""
            INSERT INTO caiuas_files (
                    id_file, 
                    file_key, 
                    bucket, 
                    file_size, 
                    content_type,
                    region,
                    created_at,
                    old_file_name
                ) VALUES (
                    {id_file}, 
                    '{file_key}', 
                    '{bucket}', 
                    {file_size}, 
                    '{content_type}',
                    '{region}',
                    CURRENT_TIMESTAMP,
                    '{old_file_name}'
                )
        """
        cursor_oracle.execute(query)
        conn_oracle.commit()
        query = f"""
            select nvl(max(id_file_proc),0)+1 from CAIUAS_VEIC_PROC_files
        """
        cursor_oracle.execute(query)
        id_file_proc = cursor_oracle.fetchone()[0]
        query = f"""
            INSERT INTO caiuas_veic_proc_files (
                    id_file_proc, 
                    id_processo, 
                    responsible,
                    id_file,
                    created_at
                ) VALUES (
                    {id_file_proc}, 
                    {id_processo}, 
                    '{usuarios_list[0]}',
                    {id_file},
                    current_timestamp
                )
        """
        cursor_oracle.execute(query)
        conn_oracle.commit()
        cursor_oracle.close()
        conn_oracle.close()
        
        retorno = {}
        retorno['id_file'] = id_file
        retorno['file_key'] = file_key
        retorno['file_size'] = file_size
        retorno['created_at'] = datetime.now().isoformat()
        retorno['message'] = "File registered successfully"

        return jsonify(retorno), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"message": str(e)}), 500
      
@files_bp.route('/api/files/classifica_processo', methods=['POST'])
@token_required
def classifica_processo():
    """Vincula (ou remove) uma etapa a um arquivo do processo, exigindo autorização completa da etapa."""
    try:
        id_file = request.json.get('id_file')
        id_etapa = request.json.get('id_etapa')

        if id_file is None:
            return jsonify({"error": "id_file is required"}), 400

        try:
            id_file = int(id_file)
            if id_etapa is not None:
                id_etapa = int(id_etapa)
        except (ValueError, TypeError):
            return jsonify({"error": "id_file and id_etapa must be integers"}), 400

        conn, cur = oracle()

        # id_etapa nulo -> remove a classificação atual do arquivo
        if id_etapa is None:
            query = f"""
                UPDATE caiuas_veic_proc_files
                SET id_etapa = NULL
                WHERE id_file = {id_file}
            """
            cur.execute(query)
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({
                "id_file": id_file,
                "id_etapa": None,
                "message": "Classificação removida com sucesso"
            }), 200

        # Só permite classificar se a etapa ainda NÃO estiver totalmente autorizada
        query = f"""
            SELECT autorizadores
            FROM CAIUAS_VEIC_PROC_ETAPAS
            WHERE id_etapa = {id_etapa}
        """
        cur.execute(query)
        result = cur.fetchone()

        if not result:
            cur.close()
            conn.close()
            return jsonify({"error": "Etapa não encontrada"}), 404

        autorizadores = result[0]
        if not autorizadores:
            cur.close()
            conn.close()
            return jsonify({"error": "Etapa não possui autorizadores configurados"}), 400

        autorizadores_list = [a.strip().upper() for a in autorizadores.split(',') if a.strip()]
        total_autorizadores = len(autorizadores_list)

        query = f"""
            SELECT COUNT(*)
            FROM CAIUAS_VEIC_PROC_ETAPAS_AUT
            WHERE id_etapa = {id_etapa}
        """
        cur.execute(query)
        total_autorizacoes = cur.fetchone()[0]

        if total_autorizacoes >= total_autorizadores:
            cur.close()
            conn.close()
            return jsonify({"message": "Etapa já está autorizada, não é possível classificar"}), 400

        query = f"""
            UPDATE caiuas_veic_proc_files
            SET id_etapa = {id_etapa}
            WHERE id_file = {id_file}
        """
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "id_file": id_file,
            "id_etapa": id_etapa,
            "message": "Arquivo classificado com sucesso"
        }), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"error": str(e)}), 500

@files_bp.route('/api/files/download/<int:id_file>', methods=['GET'])
@token_required
def get_presigned_download_url(id_file):
    """
    Gera uma URL pré-assinada para download de um arquivo registrado.
    """
    try:
        # 1. Busca os dados do arquivo no banco Oracle
        query = f"""
            SELECT cf.id_file, cf.file_key, cf.bucket, cf.content_type, cf.region, cf.file_size
            FROM caiuas_files cf
            WHERE cf.id_file = {id_file}
        """
        conn, cur = oracle()
        cur.execute(query)
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({"error": "Arquivo não encontrado"}), 404
        
        file_key = result[1]
        bucket = result[2] or 'processos-caiuas'
        content_type = result[3] or 'application/octet-stream'
        region = result[4] or 'sa-east-1'
        file_size = result[5]
        
        # 2. Configura o Cliente S3
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region,
            config=Config(signature_version='s3v4')
        )
        
        # 3. Gera a URL pré-assinada para download (get_object)
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': file_key
            },
            ExpiresIn=3600  # URL válida por 1 hora
        )
        
        return jsonify({
            "presigned_url": presigned_url,
            "id_file": id_file,
            "file_key": file_key,
            "bucket": bucket,
            "content_type": content_type,
            "file_size": file_size,
            "expires_in": 3600
        }), 200
        
    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"error": str(e)}), 500
    