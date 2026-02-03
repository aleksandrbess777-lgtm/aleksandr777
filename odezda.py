import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite
from datetime import datetime
import os

BOT_TOKEN = "8285827216:AAG3Hy6OvLTLUIIbR-sZTZQymsRIU0wFdAw"
ADMIN_IDS = [6791145579]
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    category = State()
    photo = State()


async def init_db():
    async with aiosqlite.connect('products.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT,
                photo_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Каталог", callback_data='show_categories')
    builder.button(text="Новинки", url='https://www.avito.ru/user/4b366e322280aa59d073806b6eb7cfbf/profile?src=sharing')
    builder.button(text="Отзывы", url="https://t.me/ArhieveFashionOTZIVI")
    builder.button(text="Связаться с админом", url="https://t.me/archivefashion_adm")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_categories_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👕 Верхняя одежда", callback_data='cat_верхняя одежда')
    builder.button(text="👖 Штаны", callback_data='cat_штаны')
    builder.button(text="👟 Обувь", callback_data='cat_обувь')
    builder.button(text="🎒 Аксессуары", callback_data='cat_аксессуары')
    builder.button(text="📦 Все товары", callback_data='cat_все')
    builder.button(text="◀️ Главное меню", callback_data='back_to_start')
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


async def get_products_keyboard(category="все", page=0, limit=5):
    builder = InlineKeyboardBuilder()

    async with aiosqlite.connect('products.db') as db:
        if category == "все":
            cursor = await db.execute('SELECT id, name, price FROM products')
        else:
            cursor = await db.execute('SELECT id, name, price FROM products WHERE category=?', (category,))
        products = await cursor.fetchall()

    if not products:
        return None

    start_idx = page * limit
    end_idx = start_idx + limit
    page_products = products[start_idx:end_idx]

    for product_id, name, price in page_products:
        builder.button(text=f"{name} - {price}₽", callback_data=f"product_{product_id}")

    if page > 0:
        builder.button(text="◀️ Назад", callback_data=f"page_{category}_{page - 1}")
    if end_idx < len(products):
        builder.button(text="Вперёд ▶️", callback_data=f"page_{category}_{page + 1}")

    builder.button(text="◀️ К категориям", callback_data="back_to_categories")
    builder.button(text="🏠 Главное меню", callback_data="back_to_start")

    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = get_start_keyboard()
    await message.answer(
        f'''{message.from_user.full_name}, добро пожаловать в Archive fasion! 📦\n
Тут все просто:\n
Только оригинал: каждый айтем проходит проверку.\n
Дропы: каждую неделю.\n
Доставка: по всему миру.\n
Нажми кнопку "Каталог", чтобы посмотреть, что в наличии прямо сейчас''',
        reply_markup=keyboard
    )


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав доступа.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data='admin_add_product')
    builder.button(text="🏠 Главное меню", callback_data='back_to_start')
    builder.adjust(1, 1)

    await message.answer("👑 Админ панель", reply_markup=builder.as_markup())


@dp.message(Command("getids"))
async def cmd_getids(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав доступа.")
        return

    async with aiosqlite.connect('products.db') as db:
        cursor = await db.execute('SELECT id, name, price, category FROM products ORDER BY id DESC')
        products = await cursor.fetchall()

    if not products:
        await message.answer("📦 В базе данных нет товаров.")
        return

    text = "📋 Список всех товаров с ID:\n\n"

    for product_id, name, price, category in products:
        item_text = f"🆔 ID: <code>{product_id}</code>\n📦 {name}\n💰 {price}₽\n🏷️ {category}\n────────────\n"

        if len(text) + len(item_text) > 4000:
            await message.answer(text, parse_mode='HTML')
            text = item_text
        else:
            text += item_text

    if text:
        await message.answer(text, parse_mode='HTML')


@dp.message(Command("deleteforadmin"))
async def cmd_delete(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав доступа.")
        return

    if len(message.text.split()) < 2:
        await message.answer(
            "Использование: /deleteforadmin <ID_товара>\n\nЧтобы получить ID товаров, используйте команду /getids")
        return

    try:
        product_id = int(message.text.split()[1])
    except ValueError:
        await message.answer("❌ Ошибка: ID должен быть числом.\nПример: /deleteforadmin 5")
        return

    async with aiosqlite.connect('products.db') as db:
        cursor = await db.execute('SELECT name, photo_path FROM products WHERE id=?', (product_id,))
        product = await cursor.fetchone()

        if not product:
            await message.answer(f"❌ Товар с ID {product_id} не найден.")
            return

        await db.execute('DELETE FROM products WHERE id=?', (product_id,))
        await db.commit()

        photo_path = product[1]
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except:
                pass

        await message.answer(f"✅ Товар '{product[0]}' (ID: {product_id}) успешно удален!")


@dp.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start_callback(callback: CallbackQuery):
    keyboard = get_start_keyboard()

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer("Главное меню:", reply_markup=keyboard)
    else:
        await callback.message.edit_text("Главное меню:", reply_markup=keyboard)

    await callback.answer()


@dp.callback_query(lambda c: c.data == "show_categories")
async def show_categories_callback(callback: CallbackQuery):
    keyboard = get_categories_keyboard()
    await callback.message.edit_text("📂 Выберите категорию:", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories_callback(callback: CallbackQuery):
    keyboard = get_categories_keyboard()

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer("📂 Выберите категорию:", reply_markup=keyboard)
    else:
        await callback.message.edit_text("📂 Выберите категорию:", reply_markup=keyboard)

    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith('cat_'))
async def category_callback(callback: CallbackQuery):
    category = callback.data.replace('cat_', '')
    keyboard = await get_products_keyboard(category)

    if keyboard is None:
        await callback.message.edit_text("😔 В этой категории пока нет товаров.", reply_markup=get_categories_keyboard())
    else:
        category_names = {
            'верхняя одежда': 'Верхняя одежда',
            'штаны': 'Штаны',
            'обувь': 'Обувь',
            'аксессуары': 'Аксессуары',
            'все': 'Все товары'
        }
        display_name = category_names.get(category, 'Все товары')
        await callback.message.edit_text(f"📦 {display_name}:", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith('page_'))
async def page_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    category = parts[1] if parts[1] != "все" else "все"
    page = int(parts[2])
    keyboard = await get_products_keyboard(category, page)

    if keyboard:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith('product_'))
async def product_callback(callback: CallbackQuery):
    product_id = int(callback.data.split('_')[1])

    async with aiosqlite.connect('products.db') as db:
        cursor = await db.execute(
            'SELECT name, description, price, category, photo_path FROM products WHERE id=?',
            (product_id,)
        )
        product = await cursor.fetchone()

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    name, description, price, category, photo_path = product

    # УБРАЛ СТРОКУ С ID ТОВАРА
    text = f"""
<b>{name}</b>

{description}

💰 Цена: {price}₽
🏷️ Категория: {category}
    """

    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Запросить подробности", url="https://t.me/archivefashion_adm")
    builder.button(text="🏠 Главное меню", callback_data='back_to_start')
    builder.adjust(1, 1)
    keyboard = builder.as_markup()

    try:
        if photo_path and os.path.exists(photo_path):
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await callback.message.answer(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
    except Exception as e:
        await callback.message.answer(
            text + "\n\n⚠️ Ошибка при загрузке фото",
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    await callback.answer()


@dp.callback_query(lambda c: c.data == 'admin_add_product')
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AddProduct.name)
    await callback.message.edit_text(
        "Введите название товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
        ]])
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data='admin_add_product')
    builder.button(text="🏠 Главное меню", callback_data='back_to_start')
    builder.adjust(1, 1)

    await callback.message.edit_text(
        "❌ Добавление отменено",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.message(AddProduct.name)
async def process_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer("Введите описание товара:")


@dp.message(AddProduct.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Введите цену (только число):")


@dp.message(AddProduct.price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)

        builder = InlineKeyboardBuilder()
        builder.button(text="👕 Верхняя одежда", callback_data="setcat_верхняя одежда")
        builder.button(text="👖 Штаны", callback_data="setcat_штаны")
        builder.button(text="👟 Обувь", callback_data="setcat_обувь")
        builder.button(text="🎒 Аксессуары", callback_data="setcat_аксессуары")
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(2, 2, 1)

        await state.set_state(AddProduct.category)
        await message.answer("Выберите категорию:", reply_markup=builder.as_markup())
    except ValueError:
        await message.answer("❌ Введите число (например: 2999):")


@dp.callback_query(AddProduct.category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split('_')[1]
    await state.update_data(category=category)
    await state.set_state(AddProduct.photo)
    await callback.message.edit_text("📸 Отправьте фото товара:")
    await callback.answer()


@dp.message(AddProduct.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    if not os.path.exists('product_photos'):
        os.makedirs('product_photos')

    photo = message.photo[-1]
    file_id = photo.file_id
    file = await bot.get_file(file_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"product_photos/{timestamp}_{file_id}.jpg"

    await bot.download_file(file.file_path, filename)

    data = await state.get_data()

    async with aiosqlite.connect('products.db') as db:
        await db.execute(
            'INSERT INTO products (name, description, price, category, photo_path) VALUES (?, ?, ?, ?, ?)',
            (data['name'], data['description'], data['price'], data['category'], filename)
        )
        await db.commit()

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data='admin_add_product')
    builder.button(text="🏠 Главное меню", callback_data='back_to_start')
    builder.adjust(1, 1)

    await message.answer(
        f"✅ Товар '{data['name']}' добавлен!\n\n"
        f"Название: {data['name']}\n"
        f"Цена: {data['price']}₽\n"
        f"Категория: {data['category']}\n\n"
        f"Товар появится в каталоге у пользователей.",
        reply_markup=builder.as_markup()
    )
    await state.clear()


async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())