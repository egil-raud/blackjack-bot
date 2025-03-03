import random
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TOKEN  # Импортируем токен из config.py

# Константы
START_BALANCE = 1000  # Начальный баланс для новых пользователей
DATABASE_NAME = "blackjack.db"  # Имя файла базы данных

# Глобальные переменные
games = {}  # Состояние игры для каждого чата

# Функция для создания и перемешивания колоды
def create_deck():
    return [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4

# Функция для подсчета очков
def calculate_score(hand):
    score = sum(hand)
    if score > 21 and 11 in hand:
        hand[hand.index(11)] = 1
        score = sum(hand)
    return score

# Функция для инициализации базы данных
def init_db():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL
            )
        """)
        conn.commit()

# Функция для получения баланса пользователя
def get_balance(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            # Если пользователя нет в базе, создаем запись с начальным балансом
            cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, START_BALANCE))
            conn.commit()
            return START_BALANCE

# Функция для обновления баланса пользователя
def update_balance(user_id, amount):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(
        f"Привет! Это игра в 21. Твой баланс: {balance} монет.\n"
        "Используй /play <ставка>, чтобы начать игру."
    )

# Команда /play
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем, есть ли ставка
    try:
        bet = int(context.args[0])  # Ставка из аргумента команды
    except (IndexError, ValueError):
        await update.message.reply_text("Укажи ставку. Например: /play 100")
        return

    # Проверяем, достаточно ли денег у пользователя
    balance = get_balance(user_id)
    if balance < bet:
        await update.message.reply_text("Недостаточно монет для ставки.")
        return

    # Если игра уже идет в этом чате
    if chat_id in games and games[chat_id]['game_active']:
        await update.message.reply_text("Игра уже идет. Используй /hit или /stand.")
        return

    # Инициализация игры
    deck = create_deck()
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    bot_hand = [deck.pop(), deck.pop()]

    # Сохраняем состояние игры для этого чата
    games[chat_id] = {
        'player_hand': player_hand,
        'bot_hand': bot_hand,
        'deck': deck,
        'game_active': True,
        'bet': bet,
        'user_id': user_id
    }

    # Вычитаем ставку из баланса
    update_balance(user_id, balance - bet)

    await update.message.reply_text(
        f"Ставка: {bet} монет.\n"
        f"Твои карты: {player_hand}, очки: {calculate_score(player_hand)}\n"
        f"Карта бота: [{bot_hand[0]}, ?]"
    )

# Команда /hit
async def hit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    # Проверяем, активна ли игра в этом чате
    if chat_id not in games or not games[chat_id]['game_active']:
        await update.message.reply_text("Игра не активна. Используй /play, чтобы начать.")
        return

    # Проверяем, что играет тот же пользователь
    if games[chat_id]['user_id'] != user_id:
        await update.message.reply_text("Это не твоя игра!")
        return

    # Игрок берет карту
    games[chat_id]['player_hand'].append(games[chat_id]['deck'].pop())
    player_score = calculate_score(games[chat_id]['player_hand'])

    if player_score > 21:
        await update.message.reply_text(
            f"Твои карты: {games[chat_id]['player_hand']}, очки: {player_score}\n"
            "Перебор! Ты проиграл."
        )
        games[chat_id]['game_active'] = False
    else:
        await update.message.reply_text(
            f"Твои карты: {games[chat_id]['player_hand']}, очки: {player_score}"
        )

# Команда /stand
async def stand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    # Проверяем, активна ли игра в этом чате
    if chat_id not in games or not games[chat_id]['game_active']:
        await update.message.reply_text("Игра не активна. Используй /play, чтобы начать.")
        return

    # Проверяем, что играет тот же пользователь
    if games[chat_id]['user_id'] != user_id:
        await update.message.reply_text("Это не твоя игра!")
        return

    # Бот берет карты, пока его счет меньше 17
    while calculate_score(games[chat_id]['bot_hand']) < 17:
        games[chat_id]['bot_hand'].append(games[chat_id]['deck'].pop())

    player_score = calculate_score(games[chat_id]['player_hand'])
    bot_score = calculate_score(games[chat_id]['bot_hand'])
    bet = games[chat_id]['bet']
    balance = get_balance(user_id)

    # Определение результата
    if bot_score > 21 or player_score > bot_score:
        result = "Ты выиграл!"
        update_balance(user_id, balance + bet * 2)  # Возвращаем ставку и добавляем выигрыш
    elif player_score == bot_score:
        result = "Ничья!"
        update_balance(user_id, balance + bet)  # Возвращаем ставку
    else:
        result = "Ты проиграл."

    await update.message.reply_text(
        f"Твои карты: {games[chat_id]['player_hand']}, очки: {player_score}\n"
        f"Карты бота: {games[chat_id]['bot_hand']}, очки: {bot_score}\n"
        f"{result}\n"
        f"Твой баланс: {get_balance(user_id)} монет."
    )
    games[chat_id]['game_active'] = False

# Команда /balance
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(f"Твой баланс: {balance} монет.")

# Основная функция для запуска бота
def main():
    # Инициализация базы данных
    init_db()

    # Создаем приложение и передаем токен
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("hit", hit))
    application.add_handler(CommandHandler("stand", stand))
    application.add_handler(CommandHandler("balance", balance))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
