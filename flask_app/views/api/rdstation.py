from flask import Blueprint, jsonify, request
from datetime import datetime
import json
import os

rdstation_bp = Blueprint('rdstation', __name__)

RD_TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'rd_temp'))


@rdstation_bp.route('/api/rdstation', methods=['POST'])
def rdstation():
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({'status': 'error', 'message': 'JSON inválido ou ausente'}), 400

        os.makedirs(RD_TEMP_DIR, exist_ok=True)

        filename = f"rdstation_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        filepath = os.path.join(RD_TEMP_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return jsonify({'status': 'success', 'file': filename}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
