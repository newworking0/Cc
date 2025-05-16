import random
import requests
import telebot
import time
import re
import stripe

# === CONFIGURATION ===
BOT_TOKEN = "7928470785:AAHMz54GOWoI-NsbD2zyj0Av_VbnqX7fYzI"
STRIPE_SECRET_KEY = "sk_test_51RPHEyPKJT4UzOPvvRdP59qoEt4h3khaN3xlGusDd1jvT01Houk9VsaH4geyzzWSBICupYkn5kuwEjTA2C3woy8N00Iph2LvSG"
CHECKED_BY = "CheckerBot"

# === SETUP ===
bot = telebot.TeleBot(BOT_TOKEN)
stripe.api_key = STRIPE_SECRET_KEY

# === UTILITIES ===
def is_valid_bin(bin_number):
    return bin_number.isdigit() and len(bin_number) >= 6

def get_bin_info(bin_number):
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_number}")
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def generate_card(bin_prefix, length=16):
    card_number = bin_prefix
    while len(card_number) < length - 1:
        card_number += str(random.randint(0, 9))
    digits = [int(d) for d in card_number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    check_digit = (10 - (total % 10)) % 10
    return card_number + str(check_digit)

def generate_card_details():
    month = str(random.randint(1, 12)).zfill(2)
    year = str(random.randint(int(time.strftime("%y")) + 1, int(time.strftime("%y")) + 5))
    cvv = str(random.randint(100, 999))
    return month, year, cvv

def extract_card_info(text):
    match = re.search(r"(\d{16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})", text)
    return match.groups() if match else None

def extract_multiple_cards(text):
    lines = text.strip().splitlines()[1:]
    cards = []
    for line in lines:
        match = re.match(r"(\d{16})\|(\d{2})\|(\d{4})\|(\d{3,4})", line)
        if match:
            cards.append(match.groups())
    return cards

def check_card(number, exp_month, exp_year, cvc):
    bin_info = get_bin_info(number[:6])
    card_type = bin_info.get("scheme", "Unknown").title() if bin_info else "Unknown"
    brand = bin_info.get("brand", "") if bin_info else ""
    country = bin_info.get("country", {}).get("name", "Unknown") if bin_info else "Unknown"
    try:
        stripe.PaymentIntent.create(
            amount=100,
            currency="usd",
            payment_method_data={
                "type": "card",
                "card": {
                    "number": number,
                    "exp_month": int(exp_month),
                    "exp_year": int(exp_year),
                    "cvc": cvc,
                },
            },
            confirm=True,
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never"
            }
        )
        status = "Approved"
    except stripe.error.CardError:
        status = "Declined"
    except Exception as e:
        status = f"Error: {str(e)}"

    return (
        f"Status: {status}\n"
        f"Card: {number}|{exp_month}|{exp_year}|{cvc}\n"
        f"Type: {card_type} {brand}\n"
        f"Country: {country}\n"
        f"Checked by: {CHECKED_BY}\n"
        + "-"*30
    )

# === BOT HANDLERS ===

@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    text = (
        "Welcome to CC Tool Bot!\n\n"
        "Commands:\n"
        "/gen BIN - Generate 15 Cards\n"
        "/chk CC|MM|YY|CVV - Check Single Card\n"
        "/mass (10 cards) - Check Multiple Cards\n"
    )
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: m.text.startswith(('/gen', '.gen')))
def gen_handler(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a BIN. Example: /gen 446542")
        return
    bin_number = parts[1]
    if not is_valid_bin(bin_number):
        bot.reply_to(message, "Invalid BIN.")
        return
    bin_info = get_bin_info(bin_number)
    bin_text = (
        f"🏦 BIN Info:\n"
        f"• Brand: {bin_info.get('scheme', 'Unknown').title()}\n"
        f"• Type: {bin_info.get('type', 'Unknown').title()}\n"
        f"• Bank: {bin_info.get('bank', {}).get('name', 'Unknown')}\n"
        f"• Country: {bin_info.get('country', {}).get('name', 'Unknown')} {bin_info.get('country', {}).get('emoji', '')}\n"
    ) if bin_info else "⚠️ BIN Info not found.\n"

    cards = []
    for _ in range(15):
        card = generate_card(bin_number)
        m, y, c = generate_card_details()
        cards.append(f"{card}|{m}|{y}|{c}")
    bot.reply_to(message, f"• Format: {bin_number}|xx|xx|xxx\n\n{bin_text}\nGenerated:\n" + "\n".join(cards))

@bot.message_handler(func=lambda m: m.text.startswith('/chk'))
def chk_handler(message):
    data = extract_card_info(message.text)
    if not data:
        bot.reply_to(message, "Please provide CC|MM|YY|CVV after /chk.")
        return
    bot.reply_to(message, "Checking...")
    result = check_card(*data)
    bot.reply_to(message, result)

@bot.message_handler(func=lambda m: m.text.startswith('/mass'))
def mass_handler(message):
    cards = extract_multiple_cards(message.text)
    if not cards:
        bot.reply_to(message, "Please send up to 10 cards in CC|MM|YYYY|CVV format.")
        return
    if len(cards) > 10:
        bot.reply_to(message, "Only 10 cards allowed at once.")
        return
    for i, card in enumerate(cards, 1):
        bot.send_message(message.chat.id, f"Card {i}: Checking...")
        result = check_card(*card)
        bot.send_message(message.chat.id, f"Card {i}:\n{result}")
        time.sleep(1.5)

# === START BOT ===
bot.polling()
