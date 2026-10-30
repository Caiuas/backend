from flask import Blueprint, jsonify, request
from psycopg2.extras import Json
import calendar
from datetime import date, datetime, timedelta, timezone
import os
import re
import requests

from database import postgres_site

telegram_bp = Blueprint('telegram', __name__)

MENU_TEXT = 'Opções de relatórios'
SHOWROOM_BUTTON = {
    'text': '1 - Vendas Showroom',
    'callback_data': 'vendas_showroom',
}
ASK_INITIAL_DATE = 'Selecione a data inicial:'
ASK_FINAL_DATE = 'Selecione a data final:'
INVALID_DATE = 'Data inválida. Selecione nos botões abaixo ou digite no formato DD/MM/AAAA.'
ALLOWED_TELEGRAM_IDS = {548519349, 8105764200, 8703967479}
UNAUTHORIZED_MESSAGE = 'Pesquisas não autorizadas'

MONTH_NAMES = (
    '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
)

DATE_RE = re.compile(
    r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b|\b(\d{4})-(\d{1,2})-(\d{1,2})\b'
)
STATE_TABLE_READY = False

MESSAGE_KEYS = ('message', 'edited_message', 'channel_post', 'edited_channel_post')
SENDER_KEYS = ('my_chat_member', 'chat_member', 'chat_join_request', 'inline_query')
MESSAGE_TYPES = (
    'text', 'photo', 'document', 'audio', 'video', 'video_note', 'voice',
    'sticker', 'animation', 'location', 'venue', 'contact', 'poll', 'dice',
    'new_chat_members', 'left_chat_member', 'new_chat_title',
    'new_chat_photo', 'delete_chat_photo', 'pinned_message', 'game',
    'invoice', 'successful_payment', 'story'
)


def _today_br():
    tz_br = timezone(timedelta(hours=-3))
    return datetime.now(tz_br).date()


def _shift_month(year, month, delta):
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def _build_date_keyboard(step, year=None, month=None, min_date=None):
    today = _today_br()
    if not year or not month:
        base = min_date or today
        year, month = base.year, base.month

    last_day = calendar.monthrange(year, month)[1]
    first_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, 1)

    keyboard = []

    if step == 'ini':
        keyboard.append([{
            'text': f'Início do mês ({first_date.strftime("%d/%m/%Y")})',
            'callback_data': f'date_ini:{first_date.isoformat()}',
        }])
    else:
        shortcuts = []
        if not min_date or end_date >= min_date:
            shortcuts.append({
                'text': f'Fim do mês ({end_date.strftime("%d/%m/%Y")})',
                'callback_data': f'date_fim:{end_date.isoformat()}',
            })
        if (not min_date or today >= min_date) and today != end_date:
            shortcuts.append({
                'text': f'Hoje ({today.strftime("%d/%m/%Y")})',
                'callback_data': f'date_fim:{today.isoformat()}',
            })
        if shortcuts:
            keyboard.append(shortcuts)

    keyboard.append([
        {'text': '◀️', 'callback_data': f'cal_nav:{step}:{prev_y}:{prev_m:02d}'},
        {'text': f'{MONTH_NAMES[month]}/{year}', 'callback_data': 'noop'},
        {'text': '▶️', 'callback_data': f'cal_nav:{step}:{next_y}:{next_m:02d}'},
    ])

    prefix = 'date_ini' if step == 'ini' else 'date_fim'
    row = []
    for day in range(1, last_day + 1):
        current = date(year, month, day)
        if min_date and current < min_date:
            row.append({'text': '·', 'callback_data': 'noop'})
        else:
            row.append({
                'text': f'{day:02d}',
                'callback_data': f'{prefix}:{current.isoformat()}',
            })
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([{'text': '↩️ Voltar ao menu', 'callback_data': 'menu'}])
    return {'inline_keyboard': keyboard}


def _get_message(update):
    for key in MESSAGE_KEYS:
        if isinstance(update.get(key), dict):
            return update[key]
    callback_query = update.get('callback_query')
    if isinstance(callback_query, dict) and isinstance(callback_query.get('message'), dict):
        return callback_query['message']
    return {}


def _get_sender(update, message):
    callback_query = update.get('callback_query')
    if isinstance(callback_query, dict) and isinstance(callback_query.get('from'), dict):
        return callback_query['from']
    if isinstance(message.get('from'), dict):
        return message['from']
    for key in SENDER_KEYS:
        value = update.get(key)
        if isinstance(value, dict) and isinstance(value.get('from'), dict):
            return value['from']
    return {}


def _get_message_type(update, message):
    if isinstance(update.get('callback_query'), dict):
        return 'callback_query'
    for field in MESSAGE_TYPES:
        if field in message:
            return field
    if 'edited_message' in update:
        return 'edited_message'
    return 'unknown'


def _get_text(update, message):
    callback_query = update.get('callback_query')
    if isinstance(callback_query, dict):
        return callback_query.get('data')
    text = message.get('text') or message.get('caption')
    if text:
        return text
    return None


def _get_name(person):
    if not isinstance(person, dict):
        return None
    name = ' '.join(
        part for part in (person.get('first_name'), person.get('last_name')) if part
    ).strip()
    return name or person.get('title')


def _get_token():
    return os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT')


def _call_telegram(method, payload):
    token = _get_token()
    if not token:
        print('TELEGRAM_BOT_TOKEN não configurado')
        return False
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{token}/{method}',
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f'Erro ao chamar Telegram {method}: {e}')
        return False


def _send_menu(chat_id):
    return _call_telegram('sendMessage', {
        'chat_id': chat_id,
        'text': MENU_TEXT,
        'reply_markup': {
            'inline_keyboard': [[SHOWROOM_BUTTON]]
        }
    })


def _send_document(chat_id, filename, content, caption=None):
    token = _get_token()
    if not token:
        print('TELEGRAM_BOT_TOKEN não configurado')
        return False
    data = {'chat_id': chat_id}
    if caption:
        data['caption'] = caption
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{token}/sendDocument',
            data=data,
            files={'document': (filename, content, 'application/pdf')},
            timeout=120
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f'Erro ao enviar documento no Telegram: {e}')
        return False


def _ensure_state_table(cur):
    global STATE_TABLE_READY
    if STATE_TABLE_READY:
        return
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_conversation_state (
            chat_id BIGINT PRIMARY KEY,
            state TEXT NOT NULL,
            initial_date DATE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    STATE_TABLE_READY = True


def _get_state(cur, chat_id):
    cur.execute(
        'SELECT state, initial_date FROM telegram_conversation_state WHERE chat_id = %s',
        (chat_id,)
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return row['state'], row['initial_date']


def _set_state(cur, chat_id, state, initial_date=None):
    cur.execute(
        """
        INSERT INTO telegram_conversation_state (chat_id, state, initial_date, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (chat_id) DO UPDATE SET
            state = EXCLUDED.state,
            initial_date = EXCLUDED.initial_date,
            updated_at = NOW()
        """,
        (chat_id, state, initial_date)
    )


def _clear_state(cur, chat_id):
    cur.execute('DELETE FROM telegram_conversation_state WHERE chat_id = %s', (chat_id,))


def _parse_dates(text):
    dates = []
    for match in DATE_RE.finditer(text or ''):
        try:
            if match.group(1):
                day, month, year = (int(match.group(i)) for i in (1, 2, 3))
            else:
                year, month, day = (int(match.group(i)) for i in (4, 5, 6))
            parsed = date(year, month, day)
        except ValueError:
            continue
        if parsed not in dates:
            dates.append(parsed)
    return dates


def _ask_initial_action(year=None, month=None, prefix_text=None):
    text = f'{prefix_text}\n{ASK_INITIAL_DATE}' if prefix_text else ASK_INITIAL_DATE
    return {
        'type': 'text',
        'text': text,
        'reply_markup': _build_date_keyboard('ini', year, month),
    }


def _ask_final_action(initial_date, year=None, month=None, prefix_text=None):
    base_text = f'Data inicial: {initial_date.strftime("%d/%m/%Y")}\n{ASK_FINAL_DATE}'
    text = f'{prefix_text}\n{base_text}' if prefix_text else base_text
    return {
        'type': 'text',
        'text': text,
        'reply_markup': _build_date_keyboard(
            'fim',
            year or initial_date.year,
            month or initial_date.month,
            min_date=initial_date,
        ),
    }


def _plan_report(cur, chat_id, initial_date, final_date):
    if not initial_date:
        _set_state(cur, chat_id, 'awaiting_initial')
        return _ask_initial_action()
    if not final_date:
        _set_state(cur, chat_id, 'awaiting_final', initial_date)
        return _ask_final_action(initial_date)
    if final_date < initial_date:
        _set_state(cur, chat_id, 'awaiting_final', initial_date)
        return _ask_final_action(
            initial_date,
            prefix_text='A data final deve ser maior ou igual à data inicial.',
        )
    _clear_state(cur, chat_id)
    return {'type': 'report', 'initial': initial_date, 'final': final_date}


def _plan_response(cur, chat_id, text, sender_id, is_callback=False, message_id=None):
    raw = (text or '').strip()

    if raw == 'noop':
        return {'type': 'none'}

    if raw == 'menu':
        _clear_state(cur, chat_id)
        return {'type': 'menu'}

    if raw in ('1', 'vendas_showroom'):
        if sender_id not in ALLOWED_TELEGRAM_IDS:
            _clear_state(cur, chat_id)
            return {'type': 'text', 'text': UNAUTHORIZED_MESSAGE}
        _set_state(cur, chat_id, 'awaiting_initial')
        return _ask_initial_action()

    if raw.startswith('cal_nav:'):
        if sender_id not in ALLOWED_TELEGRAM_IDS:
            return {'type': 'text', 'text': UNAUTHORIZED_MESSAGE}
        parts = raw.split(':')
        if len(parts) == 4:
            step, year, month = parts[1], int(parts[2]), int(parts[3])
            _, initial_date = _get_state(cur, chat_id)
            min_date = initial_date if step == 'fim' else None
            return {
                'type': 'edit_markup',
                'message_id': message_id,
                'reply_markup': _build_date_keyboard(step, year, month, min_date=min_date),
            }

    if raw.startswith('date_ini:'):
        if sender_id not in ALLOWED_TELEGRAM_IDS:
            return {'type': 'text', 'text': UNAUTHORIZED_MESSAGE}
        dates = _parse_dates(raw.split(':', 1)[1])
        if dates:
            _set_state(cur, chat_id, 'awaiting_final', dates[0])
            return _ask_final_action(dates[0])

    if raw.startswith('date_fim:'):
        if sender_id not in ALLOWED_TELEGRAM_IDS:
            return {'type': 'text', 'text': UNAUTHORIZED_MESSAGE}
        _, initial_date = _get_state(cur, chat_id)
        dates = _parse_dates(raw.split(':', 1)[1])
        if dates:
            return _plan_report(cur, chat_id, initial_date, dates[0])

    state, initial_date = _get_state(cur, chat_id)
    dates = _parse_dates(raw)

    if state == 'awaiting_initial' and dates:
        if len(dates) >= 2:
            return _plan_report(cur, chat_id, dates[0], dates[1])
        _set_state(cur, chat_id, 'awaiting_final', dates[0])
        return _ask_final_action(dates[0])

    if state == 'awaiting_final' and dates:
        if len(dates) >= 2:
            return _plan_report(cur, chat_id, dates[0], dates[1])
        return _plan_report(cur, chat_id, initial_date, dates[0])

    # Qualquer outra mensagem recebida retorna o menu de relatórios
    _clear_state(cur, chat_id)
    return {'type': 'menu'}


def _perform_action(action, chat_id, sender_id):
    if not action or not chat_id:
        return False

    action_type = action.get('type')
    if action_type == 'none':
        return True
    if action_type == 'menu':
        return _send_menu(chat_id)
    if action_type == 'edit_markup':
        if not action.get('message_id'):
            return False
        return _call_telegram('editMessageReplyMarkup', {
            'chat_id': chat_id,
            'message_id': action['message_id'],
            'reply_markup': action['reply_markup'],
        })
    if action_type == 'text':
        payload = {
            'chat_id': chat_id,
            'text': action.get('text'),
        }
        if action.get('reply_markup'):
            payload['reply_markup'] = action['reply_markup']
        return _call_telegram('sendMessage', payload)
    if action_type == 'report':
        if sender_id not in ALLOWED_TELEGRAM_IDS:
            return _call_telegram('sendMessage', {
                'chat_id': chat_id,
                'text': UNAUTHORIZED_MESSAGE,
            })
        initial_date = action['initial']
        final_date = action['final']
        period = f'{initial_date.strftime("%d/%m/%Y")} a {final_date.strftime("%d/%m/%Y")}'
        _call_telegram('sendMessage', {
            'chat_id': chat_id,
            'text': f'Gerando relatório de Vendas Showroom ({period})...',
        })
        try:
            from views.api.reports import gerar_dashboard_showroom
            buffer, filename = gerar_dashboard_showroom(
                initial_date.year,
                initial_date.month,
                data_inicial=initial_date,
                data_final=final_date,
            )
            return _send_document(
                chat_id,
                filename,
                buffer.getvalue(),
                caption=f'Vendas Showroom ({period})',
            )
        except Exception as e:
            print(f'Erro ao gerar relatório de Vendas Showroom: {e}')
            return _call_telegram('sendMessage', {
                'chat_id': chat_id,
                'text': f'Não foi possível gerar o relatório: {e}',
            })
    return False


@telegram_bp.route('/api/telegram', methods=['POST'])
def telegram_webhook():
    secret = os.getenv('TELEGRAM_WEBHOOK_SECRET')
    if secret and request.headers.get('X-Telegram-Bot-Api-Secret-Token') != secret:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        return jsonify({'ok': False, 'error': 'invalid payload'}), 400

    message = _get_message(update)
    sender = _get_sender(update, message)
    chat = message.get('chat') if isinstance(message.get('chat'), dict) else {}
    contact = message.get('contact') if isinstance(message.get('contact'), dict) else {}

    message_type = _get_message_type(update, message)
    text = _get_text(update, message)

    conn = None
    try:
        conn, cur = postgres_site()

        sender_id = sender.get('id')
        if sender_id:
            cur.execute(
                """
                INSERT INTO telegram_contacts
                    (telegram_id, chat_id, username, first_name, last_name,
                     language_code, is_bot, phone_number, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    chat_id = COALESCE(EXCLUDED.chat_id, telegram_contacts.chat_id),
                    username = COALESCE(EXCLUDED.username, telegram_contacts.username),
                    first_name = COALESCE(EXCLUDED.first_name, telegram_contacts.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, telegram_contacts.last_name),
                    language_code = COALESCE(EXCLUDED.language_code, telegram_contacts.language_code),
                    is_bot = EXCLUDED.is_bot,
                    phone_number = COALESCE(EXCLUDED.phone_number, telegram_contacts.phone_number),
                    raw = EXCLUDED.raw,
                    updated_at = NOW()
                """,
                (
                    sender_id,
                    chat.get('id'),
                    sender.get('username'),
                    sender.get('first_name'),
                    sender.get('last_name'),
                    sender.get('language_code'),
                    bool(sender.get('is_bot', False)),
                    contact.get('phone_number'),
                    Json(sender),
                )
            )

        cur.execute(
            """
            INSERT INTO telegram_log
                (update_id, message_id, chat_id, from_id, from_username,
                 from_name, message_type, text, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                update.get('update_id'),
                message.get('message_id'),
                chat.get('id'),
                sender.get('id'),
                sender.get('username'),
                _get_name(sender),
                message_type,
                text,
                Json(update),
            )
        )

        callback_query = update.get('callback_query')
        is_callback = isinstance(callback_query, dict)

        action = None
        if chat.get('id') and not sender.get('is_bot'):
            _ensure_state_table(cur)
            action = _plan_response(
                cur,
                chat['id'],
                text,
                sender.get('id'),
                is_callback=is_callback,
                message_id=message.get('message_id'),
            )

        conn.commit()
        cur.close()
        conn.close()
        conn = None

        if is_callback:
            _call_telegram('answerCallbackQuery', {
                'callback_query_id': callback_query.get('id')
            })

        sent = _perform_action(action, chat.get('id'), sender.get('id'))
        return jsonify({'ok': True, 'sent': sent}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
