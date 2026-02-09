from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
# from auth import token_required
import uuid
import boto3

load_dotenv()
files_bp = Blueprint('files_bp', __name__)

@files_bp.route('/api/files/generate_presigned_url', methods=['POST'])
# @token_required
def generate_presigned_url():
    try:
        file_name = request.json.get('file_name')
        file_size = request.json.get('file_size')
        uuid_str = str(uuid.uuid4())
        now = datetime.now()
        # pasta no formato YYYY/MM/DD
        date_path = now.strftime("%Y/%m/%d")
        file_name = f"{date_path}/{uuid_str}_{file_name}"
        
        
        if not file_name:
            return jsonify({"error": "file_name is required"}), 400
        if not file_size:
            return jsonify({"error": "file_size is required"}), 400
        if type(file_size) is not int:
            return jsonify({"error": "file_size must be an integer"}), 400
        
        # conn, cur = postgres_site()
        # query = f"""
        #     insert into files (filename, url, file_size, old_filename, created_at)
        #     values
        #     ( '{uuid_str}', '{file_name}', {file_size}, '{file_name}', now() )
        # """
        # cur.execute(query)
        # conn.commit()
        # cur.close()
        # conn.close()

        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='sa-east-1'
        )

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': 'intranet-caiuas2', 'Key': file_name},
            ExpiresIn=3600
        )

        return jsonify({"presigned_url": presigned_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500