import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import sqlite3

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8808027878:AAEd9acm1zjk8MYLi8LRjhvqiB2tGcEfyEE'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def init_db():
    conn = sqlite3.connect('chat_topics.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_by INTEGER,
        created_by_username TEXT,
        is_default BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER NOT NULL,
        user2_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS waiting_users (
        user_id INTEGER NOT NULL,
        username TEXT,
        topic_id INTEGER NOT NULL,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, topic_id))''')
    
    topics = [
        ('🎮 Игры', 'Видеоигры, киберспорт'),
        ('🎬 Кино', 'Фильмы и сериалы'),
        ('📚 Книги', 'Литература'),
        ('🎵 Музыка', 'Исполнители'),
        ('💻 IT', 'Технологии'),
        ('🏃 Спорт', 'Соревнования'),
        ('🎨 Искусство', 'Творчество'),
        ('✈️ Путешествия', 'Страны'),
        ('🍳 Кулинария', 'Рецепты'),
        ('🧘 Саморазвитие', 'Психология')
    ]
    
    for name, desc in topics:
        cursor.execute('INSERT OR IGNORE INTO topics (name, description, is_default) VALUES (?, ?, 1)', (name, desc))
    
    conn.commit()
    conn.close()

class ChatStates(StatesGroup):
    waiting_name = State()
    waiting_desc = State()
    in_chat = State()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Найти собеседника", callback_data="find")],
        [InlineKeyboardButton(text="📋 Список тематик", callback_data="list")],
        [InlineKeyboardButton(text="➕ Добавить тему", callback_data="add")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])

def topics_menu(topics, page=0):
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_topics = topics[start:end]
    
    keyboard = []
    for t in page_topics:
        keyboard.append([InlineKeyboardButton(text=t[1], callback_data=f"topic_{t[0]}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pg_{page-1}"))
    if end < len(topics):
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"pg_{page+1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def chat_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Завершить чат", callback_data="end")],
        [InlineKeyboardButton(text="👤 Следующий", callback_data="next")]
    ])

def get_topics():
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('SELECT id, name, description, created_by_username, is_default FROM topics WHERE is_active=1 ORDER BY is_default DESC, name')
    result = cur.fetchall()
    conn.close()
    return result

def add_custom_topic(name, desc, uid, uname):
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO topics (name, description, created_by, created_by_username) VALUES (?,?,?,?)', (name, desc, uid, uname))
    conn.commit()
    conn.close()

async def find_match(uid, uname, tid):
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('SELECT user_id, username FROM waiting_users WHERE topic_id=? AND user_id!=? LIMIT 1', (tid, uid))
    partner = cur.fetchone()
    if partner:
        cur.execute('DELETE FROM waiting_users WHERE user_id=? AND topic_id=?', (partner[0], tid))
        cur.execute('INSERT INTO user_chats (user1_id, user2_id, topic_id) VALUES (?,?,?)', (uid, partner[0], tid))
        conn.commit()
        conn.close()
        return partner
    else:
        cur.execute('INSERT OR REPLACE INTO waiting_users (user_id, username, topic_id) VALUES (?,?,?)', (uid, uname, tid))
        conn.commit()
        conn.close()
        return None

def get_active_chat(uid):
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('SELECT id, user1_id, user2_id FROM user_chats WHERE (user1_id=? OR user2_id=?) AND is_active=1', (uid, uid))
    chat = cur.fetchone()
    conn.close()
    return chat

def end_chat(cid):
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('UPDATE user_chats SET is_active=0 WHERE id=?', (cid,))
    conn.commit()
    conn.close()

def leave_queue(uid):
    conn = sqlite3.connect('chat_topics.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM waiting_users WHERE user_id=?', (uid,))
    conn.commit()
    conn.close()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Привет! Я бот для общения по интересам!\nВыберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "menu")
async def menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_menu())

@dp.callback_query(F.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    text = "ℹ️ <b>Помощь:</b>\n\n• Нажмите «Найти собеседника»\n• Выберите тему\n• Общайтесь!"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Меню", callback_data="menu")]]))

@dp.callback_query(F.data == "list")
@dp.callback_query(F.data.startswith("pg_"))
async def list_topics(callback: types.CallbackQuery):
    page = 0 if callback.data == "list" else int(callback.data.split("_")[1])
    topics = get_topics()
    await callback.message.edit_text("📋 <b>Тематики:</b>", reply_markup=topics_menu(topics, page), parse_mode="HTML")

@dp.callback_query(F.data == "add")
async def add_topic_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("➕ Введите название темы:")
    await state.set_state(ChatStates.waiting_name)

@dp.message(ChatStates.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ Слишком коротко. Минимум 3 символа:")
        return
    await state.update_data(name=name)
    await message.answer("📝 Введите описание:")
    await state.set_state(ChatStates.waiting_desc)

@dp.message(ChatStates.waiting_desc)
async def get_desc(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    if len(desc) < 5:
        await message.answer("❌ Слишком коротко. Минимум 5 символов:")
        return
    data = await state.get_data()
    add_custom_topic(data['name'], desc, message.from_user.id, message.from_user.username)
    await state.clear()
    await message.answer(f"✅ Тема «{data['name']}» добавлена!", reply_markup=main_menu())

@dp.callback_query(F.data == "find")
async def find(callback: types.CallbackQuery):
    chat = get_active_chat(callback.from_user.id)
    if chat:
        await callback.answer("❌ Вы уже в чате!", show_alert=True)
        return
    topics = get_topics()
    await callback.message.edit_text("🎯 Выберите тему:", reply_markup=topics_menu(topics))

@dp.callback_query(F.data.startswith("topic_"))
async def select_topic(callback: types.CallbackQuery, state: FSMContext):
    tid = int(callback.data.split("_")[1])
    chat = get_active_chat(callback.from_user.id)
    if chat:
        await callback.answer("❌ Вы уже в чате!", show_alert=True)
        return
    
    await callback.message.edit_text("🔍 Поиск собеседника...")
    partner = await find_match(callback.from_user.id, callback.from_user.username, tid)
    
    if partner:
        conn = sqlite3.connect('chat_topics.db')
        cur = conn.cursor()
        cur.execute('SELECT name FROM topics WHERE id=?', (tid,))
        topic_name = cur.fetchone()[0]
        conn.close()
        
        await callback.message.edit_text(f"✅ Собеседник найден!\nТема: {topic_name}\nСобеседник: @{partner[1] or 'Аноним'}\nПишите сообщение:", reply_markup=chat_menu(), parse_mode="HTML")
        await bot.send_message(partner[0], f"✅ Собеседник найден!\nТема: {topic_name}\nСобеседник: @{callback.from_user.username or 'Аноним'}\nПишите сообщение:", reply_markup=chat_menu(), parse_mode="HTML")
        await state.set_state(ChatStates.in_chat)
        await state.update_data(partner=partner[0])
    else:
        await callback.message.edit_text("⏳ Ожидание собеседника...\nВы в очереди!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu")]
        ]))

@dp.message(ChatStates.in_chat)
async def chat_message(message: types.Message, state: FSMContext):
    chat = get_active_chat(message.from_user.id)
    if not chat:
        await message.answer("❌ Чат завершён.", reply_markup=main_menu())
        await state.clear()
        return
    
    data = await state.get_data()
    partner_id = data.get('partner')
    
    try:
        if message.text:
            await bot.send_message(partner_id, f"💬 Собеседник: {message.text}")
        else:
            await bot.send_message(partner_id, "📎 Собеседник отправил вложение")
    except:
        await message.answer("❌ Ошибка отправки.")

@dp.callback_query(F.data == "end")
async def end(callback: types.CallbackQuery, state: FSMContext):
    chat = get_active_chat(callback.from_user.id)
    if chat:
        data = await state.get_data()
        partner_id = data.get('partner')
        end_chat(chat[0])
        try:
            await bot.send_message(partner_id, "👋 Собеседник завершил чат.", reply_markup=main_menu())
        except:
            pass
        await callback.message.edit_text("👋 Чат завершён.", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "next")
async def next_partner(callback: types.CallbackQuery, state: FSMContext):
    chat = get_active_chat(callback.from_user.id)
    if chat:
        data = await state.get_data()
        partner_id = data.get('partner')
        end_chat(chat[0])
        try:
            await bot.send_message(partner_id, "👋 Собеседник хочет сменить партнёра.", reply_markup=main_menu())
        except:
            pass
    await state.clear()
    topics = get_topics()
    await callback.message.edit_text("🎯 Выберите новую тему:", reply_markup=topics_menu(topics))

async def main():
    init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    print("🚀 Старт...")
    asyncio.run(main())
