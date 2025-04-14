import json
import os
import requests

# Config
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
PHOTO_URL = "https://cloud.appwrite.io/v1/storage/buckets/67f694430030364ac183/files/67f694ed0029e4957b1c/view?project=67f037f300060437d16d&mode=admin"
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET")

# Stato utenti
user_payments = {}

# Ottieni access token PayPal
def get_paypal_token():
    url = "https://api.sandbox.paypal.com/v1/oauth2/token"
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}
    res = requests.post(url, headers=headers, data=data, auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET))
    if res.status_code == 200:
        return res.json()['access_token']
    else:
        raise Exception(f"PayPal token error: {res.text}")

# Crea ordine PayPal con IPN
def create_payment_link(chat_id, amount):
    token = get_paypal_token()
    url = "https://api.sandbox.paypal.com/v2/checkout/orders"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    data = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": "EUR", "value": str(amount)},
                "custom_id": str(chat_id),
                "notify_url": "https://67f6d3471e1e1546c937.appwrite.global/v1/functions/67f6d345003e6da67d40/executions"
            }
        ],
        "application_context": {
            "return_url": "https://calcaterra.github.io/paypal-return",
            "cancel_url": "https://t.me/FoulesolExclusive_bot"
        }
    }
    res = requests.post(url, headers=headers, json=data)
    if res.status_code == 201:
        return next(link['href'] for link in res.json()['links'] if link['rel'] == 'approve')
    else:
        raise Exception(f"PayPal create payment error: {res.text}")

# Manda link PayPal su Telegram
def send_payment_link(chat_id):
    payment_link = create_payment_link(chat_id, 0.99)
    user_payments[chat_id] = {'payment_pending': True}
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "Paga 0,99€ con PayPal", "url": payment_link}]
        ]
    }
    payload = {
        "chat_id": chat_id,
        "text": (
            "Ciao 😘 clicca sul pulsante per offrirmi un caffè su PayPal. "
            "Dopo il pagamento, torna qui e premi *Guarda foto* per riceverla 😏"
        ),
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(keyboard)
    }
    requests.post(url, data=payload)

# Mostra pulsante "Guarda foto"
def send_view_photo_button(chat_id):
    print(f"📸 Invio pulsante 'Guarda foto' a {chat_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "Guarda foto", "callback_data": "photo"}]
        ]
    }
    payload = {
        "chat_id": chat_id,
        "text": "Pagamento ricevuto! Premi qui sotto per vedere la foto 👇",
        "reply_markup": json.dumps(keyboard)
    }
    requests.post(url, data=payload)

# Invia foto all'utente
def send_photo(chat_id):
    if user_payments.get(chat_id, {}).get('payment_pending') is False:
        print(f"✅ Invio foto a {chat_id}")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": PHOTO_URL
        }
        requests.post(url, data=payload)
    else:
        print(f"⚠️ Tentativo di accesso alla foto non autorizzato da {chat_id}")

# Gestione PayPal IPN
def handle_paypal_ipn(request_data):
    print("🧾 IPN ricevuto:", request_data)

    verify_url = "https://ipnpb.sandbox.paypal.com/cgi-bin/webscr"
    verify_payload = 'cmd=_notify-validate&' + request_data
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(verify_url, headers=headers, data=verify_payload)

    print("🔁 Risposta PayPal IPN:", res.text)

    if res.text == "VERIFIED":
        ipn = dict(x.split('=') for x in request_data.split('&') if '=' in x)
        print("📦 Dati IPN parsati:", ipn)

        payment_status = ipn.get("payment_status")
        chat_id = ipn.get("custom")

        if payment_status == "Completed" and chat_id:
            print(f"💰 Pagamento confermato da PayPal per chat_id: {chat_id}")
            user_payments[chat_id] = {'payment_pending': False}
            send_view_photo_button(chat_id)
        else:
            print(f"❌ IPN ricevuto ma pagamento non completato o chat_id mancante.")

# Funzione principale Appwrite
async def main(context):
    req = context.req
    res = context.res

    try:
        content_type = req.headers.get("content-type", "")
        if content_type == "application/x-www-form-urlencoded":
            raw_body = req.body_raw.decode()
            handle_paypal_ipn(raw_body)
            return res.json({"status": "IPN received"}, 200)

        data = req.body
        message = data.get("message")
        callback = data.get("callback_query")

        if message:
            chat_id = str(message["chat"]["id"])
            if message.get("text") == "/start":
                send_payment_link(chat_id)

        elif callback:
            chat_id = str(callback["message"]["chat"]["id"])
            if callback.get("data") == "photo":
                send_photo(chat_id)

        return res.json({"status": "ok"}, 200)

    except Exception as e:
        print("❗ Errore:", str(e))
        return res.json({"status": "error", "message": str(e)}, 500)
