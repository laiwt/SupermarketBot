from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from threading import Timer
import pandas as pd
import spacy
from nltk.stem.snowball import SnowballStemmer
import string
import random

nlp_spacy = spacy.load("ru_core_news_sm")
stemmer = SnowballStemmer("russian")

TOKEN = 'Здесь ваш TOKEN'
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

df = pd.read_csv('products.csv')
stem_products_key = [stemmer.stem(word) for word in df['name'].values]
stem_products_value = df['name'].values.tolist()
stem_products = dict(zip(stem_products_key, stem_products_value))
customers = {}
orders = []

class BotStates(StatesGroup):
    start_state = State()
    waiting_state = State()
    buying_state = State()
    adding_state = State()
    confirm_state = State()
    choosing_state = State()
    waiting_for_name_state = State()
    waiting_for_telephone_state = State()
    waiting_for_address_state = State()
    second_confirm_state = State()
    canceling_state = State()
    confirm_canceling_state = State()
    end_state = State()


class Customer:
    def __init__(self, id):
        self.id = id
        self.cur_product = None
        self.cur_quantity = None
        self.shopping_cart = []
        self.name = None
        self.telephone = None
        self.address = None
        self.order = None


def lemmatizing(corpus):
    doc = nlp_spacy(corpus.lower())
    return [token.lemma_ for token in doc if not token.text in string.punctuation]

@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    global customers
    customers[message.from_user.id] = Customer(message.from_user.id)
    answer = 'Здравствуйте! Добро пожаловать в наш онлайн-супермаркет🎉🎉🎉 Чем я могу вам помочь?'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ['Сделать заказ', 'Отменить заказ']
    keyboard.add(*buttons)
    await bot.send_message(message.from_user.id, answer, reply_markup=keyboard)
    await BotStates.waiting_state.set()

@dp.message_handler()
async def reply(message: types.Message):
    answer = 'Введите /start'
    await bot.send_message(message.from_user.id, answer)

@dp.message_handler(state=BotStates.end_state)
async def reply(message: types.Message):
    if message.text != '/start':
        answer = 'Введите /start'
        await bot.send_message(message.from_user.id, answer)
        return
    global customers
    customers[message.from_user.id] = Customer(message.from_user.id)
    answer = 'Здравствуйте! Добро пожаловать в наш онлайн-супермаркет🎉🎉🎉 Чем я могу вам помочь?'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ['Сделать заказ', 'Отменить заказ']
    keyboard.add(*buttons)
    await bot.send_message(message.from_user.id, answer, reply_markup=keyboard)
    await BotStates.waiting_state.set()
    

@dp.message_handler(state=BotStates.waiting_state)
async def choose_type(message: types.Message):
    if message.text == 'Сделать заказ':
        answer = 'OK. Что вы хотите купить?'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Мясо', 'Овощи', 'Фрукты', 'Морепродукты', 'Перейти к оформлению', 'Отменить']
        keyboard.add(*buttons)
        await bot.send_message(message.from_user.id, answer, reply_markup=keyboard)
        await BotStates.buying_state.set()
    elif message.text == 'Отменить заказ':
        answer = 'Мы приносим извинения за причиненные неудобства. Пожалуйста, введите номер заказа, который нужно отменить.'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Назад']
        keyboard.add(*buttons)
        await bot.send_message(message.from_user.id, answer, reply_markup=keyboard)
        await BotStates.canceling_state.set()

@dp.message_handler(state=BotStates.canceling_state)
async def check_order_number(message: types.Message):
    id = message.from_user.id
    if message.text == 'Назад':
        answer = 'Чем я могу вам помочь?'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Сделать заказ', 'Отменить заказ']
        keyboard.add(*buttons)
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.waiting_state.set()
    else:
        for order in orders:
            if message.text == order[0]:
                answer = 'Вы уверены, что хотите отменить этот заказ?\n'
                total = 0
                for product in order[4]:
                    answer += f'Название: {product[0]}  Цена за 1 кг: {product[1]}  Количество: {product[2]}  Сумма: {product[3]}\n'
                    total += product[3]
                answer += f'Всего к оплате: {total}\n'
                customers[id].order = order
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                buttons = ['Да', 'Нет']
                keyboard.add(*buttons)
                await bot.send_message(id, answer, reply_markup=keyboard)
                await BotStates.confirm_canceling_state.set()
                return
        answer = 'Номер заказа не существует. Пожалуйста, введите номер заказа заново.'
        await bot.send_message(id, answer)

@dp.message_handler(state=BotStates.confirm_canceling_state)
async def confirm(message: types.Message):
    text = lemmatizing(message.text)
    id = message.from_user.id
    if 'нет' in text or 'не' in text:
        customers[id].order = None
        answer = 'Пожалуйста, введите номер заказа заново.'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Назад']
        keyboard.add(*buttons)
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.canceling_state.set()
    elif 'да' in text:
        global orders
        for item in customers[id].order[4][:]:
            df_product = df[df['name'] == item[0]]
            inventory = df_product['inventory'].tolist()[0]
            idx = df_product.index[0]
            df.loc[idx, 'inventory'] = inventory + item[2]
        orders.remove(customers[id].order)
        answer = 'Заказ был успешно отменен. Если вам ещё нужны другие службы, вы можете ввести \start . До свидания!'
        keyboard = types.ReplyKeyboardRemove()
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.end_state.set()
    else:
        answer = 'Я не понимаю вас.'
        await bot.send_message(id, answer)

def word2num(word):
    try:
        return float(word)
    except:
        return None

def get_shopping_cart(id):
    res = 'Ваша корзина:\n'
    total = 0
    for product in customers[id].shopping_cart:
        res += f'Название: {product[0]}  Цена за 1 кг: {product[1]}  Количество: {product[2]}  Сумма: {product[3]}\n'
        total += product[3]
    res += f'Всего к оплате: {total}\n'
    return res

@dp.message_handler(state=BotStates.buying_state)
async def buy(message: types.Message):
    msg = message.text
    id = message.from_user.id
    global df
    if msg == 'Мясо' or msg == 'Овощи' or msg == 'Фрукты' or msg == 'Морепродукты':
        products = df[df['category'] == msg].values
        answer = f'Хотите купить {msg.lower()}? У нас есть следующие продукты:\n'
        for product in products:
            answer += f'Название: {product[0]}  Цена: {product[1]}₽/кг  В наличии: {product[3]}кг\n'
        await bot.send_message(id, answer)
        return
    if msg == 'Перейти к оформлению':
        if len(customers[id].shopping_cart) == 0:
            answer = 'Вы ещё ничего не купили!'
            await bot.send_message(id, answer)
            return
        else:
            answer = get_shopping_cart(id)
            answer += 'Вы подтверждаете?'
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ['Подтверждаю', 'Хочу удалить товар', 'Назад']
            keyboard.add(*buttons)
            await bot.send_message(id, answer, reply_markup=keyboard)
            await BotStates.confirm_state.set()
            return
    if msg == 'Отменить':
        for item in customers[id].shopping_cart[:]:
            df_product = df[df['name'] == item[0]]
            inventory = df_product['inventory'].tolist()[0]
            idx = df_product.index[0]
            df.loc[idx, 'inventory'] = inventory + item[2]
            customers[id].shopping_cart.remove(item)
        answer = 'Чем я могу вам помочь?'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Сделать заказ', 'Отменить заказ']
        keyboard.add(*buttons)
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.waiting_state.set()
        return
    text = lemmatizing(msg)
    products = []
    for word in text:
        if word in df['name'].values:
            products.append(word)
        elif stemmer.stem(word) in stem_products:
            products.append(stem_products[stemmer.stem(word)])
    quantity = [float(word) for word in text if word2num(word) != None]
    while len(quantity) < len(products):
        quantity.append(None)
    weight = []
    for word in text:
        if word == 'кг' or word == 'кг.' or word == 'килограмм' or word == 'г' or word == 'г.' or word == 'грамм':
            weight.append(word)
    while len(weight) < len(quantity):
        weight.append('кг')
    if len(products) == 0:
        # lemmatizing('есть') => быть
        if 'быть' in text or 'что' in text or 'какой' in text:
            df_products = df.values
            answer = f'У нас есть следующие продукты:\n'
            for product in df_products:
                answer += f'Название: {product[0]}  Цена: {product[1]}₽/кг  В наличии: {product[3]}кг\n'
            await bot.send_message(id, answer)
            return
        else:
            answer = 'Извините, я не нашел такого продукта😥'
            await bot.send_message(id, answer)
            return
    customers[id].cur_product = products[0]
    df_product = df[df['name'] == products[0]]
    inventory = df_product['inventory'].tolist()[0]
    price = df_product['price'].tolist()[0]
    if inventory == 0:
        answer = 'Нам очень жаль, но этот товар полностью распродан😅 Пожалуйста, попробуйте купить завтра.'
        await bot.send_message(id, answer)
        return
    if quantity[0] != None:
        if weight[0] == 'г' or weight[0] == 'г.' or weight[0] == 'грамм':
            quantity[0] /= 1000
        customers[id].cur_quantity = quantity[0]
        answer = f'Вы хотите купить {products[0]}({price}₽/кг) весом {quantity[0]} кг, верно?'
    else:
        answer = f'Вы хотите купить {products[0]}({price}₽/кг)?'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ['Да', 'Нет']
    keyboard.add(*buttons)
    await bot.send_message(id, answer, reply_markup=keyboard)
    await BotStates.adding_state.set()

@dp.message_handler(state=BotStates.adding_state)
async def add_product(message: types.Message):
    text = lemmatizing(message.text)
    id = message.from_user.id
    global df
    df_product = df[df['name'] == customers[id].cur_product]
    inventory = df_product['inventory'].tolist()[0]
    idx = df_product.index[0]
    if 'весь' in text or 'вся' in text or 'всё' in text or 'все' in text:
        customers[id].cur_quantity = inventory
        answer = f'Вы хотите купить все {customers[id].cur_product} (весом {customers[id].cur_quantity} кг), верно?'
        await bot.send_message(id, answer)
        return
    quantity = [float(word) for word in text if word2num(word) != None]
    if len(quantity) != 0:
        customers[id].cur_quantity = quantity[0]
        answer = f'Вы хотите купить {customers[id].cur_product} весом {customers[id].cur_quantity} кг, верно?'
        await bot.send_message(id, answer)
    elif 'нет' in text or 'не' in text:
        if customers[id].cur_quantity == None:
            answer = 'Что вам нужно купить?'
            customers[id].cur_product = None
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ['Мясо', 'Овощи', 'Фрукты', 'Морепродукты', 'Перейти к оформлению', 'Отменить']
            keyboard.add(*buttons)
            await bot.send_message(id, answer, reply_markup=keyboard)
            await BotStates.buying_state.set()
        else:
            customers[id].cur_quantity = None
            answer = 'Это тот товар, который вы хотите купить?'
            await bot.send_message(id, answer)
    elif 'да' in text:
        if customers[id].cur_quantity == None:
            answer = 'Скажите, пожалуйста, сколько килограммов вы хотите купить?'
            await bot.send_message(id, answer)
        else:
            if customers[id].cur_quantity <= 0:
                customers[id].cur_quantity = None
                answer = 'Не удалось добавить в корзину. Количество покупок должно быть больше 0. Вы ещё хотите купить этот товар?'
                await bot.send_message(id, answer)
            elif inventory >= customers[id].cur_quantity:
                price = df_product['price'].tolist()[0]
                customers[id].shopping_cart.append([customers[id].cur_product, price, customers[id].cur_quantity, price * customers[id].cur_quantity])
                df.loc[idx, 'inventory'] = inventory - customers[id].cur_quantity
                answer = 'Хорошо. Товар добавлен в корзину. Вы хотите купить что-нибудь ещё?'
                customers[id].cur_product = None
                customers[id].cur_quantity = None
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                buttons = ['Мясо', 'Овощи', 'Фрукты', 'Морепродукты', 'Перейти к оформлению', 'Отменить']
                keyboard.add(*buttons)
                await bot.send_message(id, answer, reply_markup=keyboard)
                await BotStates.buying_state.set()
            else:
                customers[id].cur_quantity = None
                answer = f'Извините, в наличии не так много, всего {inventory} кг на данный момент. Вы ещё хотите купить этот товар?'
                await bot.send_message(id, answer)
    else:
        answer = 'Я не совсем понимаю, что вы имеете в виду.'
        await bot.send_message(id, answer)

@dp.message_handler(state=BotStates.confirm_state)
async def confirm(message: types.Message):
    text = lemmatizing(message.text)
    id = message.from_user.id
    global df
    product = None
    for word in text:
        if word in df['name'].values:
            product = word
            break
        elif stemmer.stem(word) in stem_products:
            product = stem_products[stemmer.stem(word)]
            break
    if product != None:
        deleted = False
        for item in customers[id].shopping_cart[:]:
            if item[0] == product:
                df_product = df[df['name'] == item[0]]
                inventory = df_product['inventory'].tolist()[0]
                idx = df_product.index[0]
                df.loc[idx, 'inventory'] = inventory + item[2]
                customers[id].shopping_cart.remove(item)
                deleted = True
        if len(customers[id].shopping_cart) == 0:
            answer = 'Корзина пуста. Добавьте товар.'
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ['Мясо', 'Овощи', 'Фрукты', 'Морепродукты', 'Перейти к оформлению', 'Отменить']
            keyboard.add(*buttons)
            await bot.send_message(id, answer, reply_markup=keyboard)
            await BotStates.buying_state.set()
            return
        if deleted:
            answer = f'Товар "{product}" удален из корзины.\n'
            answer += get_shopping_cart(id)
            answer += 'Вы подтверждаете?'
            await bot.send_message(id, answer)
            return
        else:
            answer = f'В вашей корзине нет товара "{product}". Попробуйте другой товар.'
            await bot.send_message(id, answer)
            return
    if 'нет' in text or 'удалить' in text or 'удалять' in text or 'не' in text:
        answer = 'Хорошо, какой товар вы хотите удалить?'
        await bot.send_message(id, answer)
    elif 'да' in text or 'подтверждать' in text:
        answer = 'Вам нужен самовывоз или доставка?'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Самовывоз', 'Доставка']
        keyboard.add(*buttons)
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.choosing_state.set()
    elif 'назад' in text:
        answer = 'Хорошо, продолжайте покупки.'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ['Мясо', 'Овощи', 'Фрукты', 'Морепродукты', 'Перейти к оформлению', 'Отменить']
        keyboard.add(*buttons)
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.buying_state.set()
    else:
        answer = 'Извините, я вас не понимаю.'
        await bot.send_message(id, answer)

def get_order_number():
    res = ''
    for i in range(8):
        res += str(random.randint(0, 9))
    if not res in [order[0] for order in orders]:
        return res
    else:
        return get_order_number()

@dp.message_handler(state=BotStates.choosing_state)
async def choose(message: types.Message):
    text = lemmatizing(message.text)
    id = message.from_user.id
    global orders
    if 'самовывоз' in text:
        order_number = get_order_number()
        orders.append([order_number, None, None, None, customers[id].shopping_cart])
        customers[id].shopping_cart = []
        answer = f'Спасибо за вашу покупку😊😊😊 Ваш номер заказа: {order_number}. Пожалуйста, заберите ваш заказ из нашего супермаркета через 30 минут. Приглашаем вас вернуться снова! До скорой встречи.'
        keyboard = types.ReplyKeyboardRemove()
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.end_state.set()
    elif 'доставка' in text:
        answer = 'Хорошо. Как вас зовут?'
        keyboard = types.ReplyKeyboardRemove()
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.waiting_for_name_state.set()
    else:
        answer = 'Я не знаю, о чем вы говорите.'
        await bot.send_message(id, answer)

@dp.message_handler(state=BotStates.waiting_for_name_state)
async def get_name(message: types.Message):
    id = message.from_user.id
    customers[id].name = message.text
    answer = 'Какой у вас номер телефона?'
    await bot.send_message(id, answer)
    await BotStates.waiting_for_telephone_state.set()

@dp.message_handler(state=BotStates.waiting_for_telephone_state)
async def get_telephone(message: types.Message):
    id = message.from_user.id
    customers[id].telephone = message.text
    answer = 'Какой у вас адрес доставки?'
    await bot.send_message(id, answer)
    await BotStates.waiting_for_address_state.set()

@dp.message_handler(state=BotStates.waiting_for_address_state)
async def get_address(message: types.Message):
    id = message.from_user.id
    customers[id].address = message.text
    answer = 'Информация о вашем заказе:\n'
    answer += f'ФИО: {customers[id].name}\n'
    answer += f'Телефон: {customers[id].telephone}\n'
    answer += f'Адрес: {customers[id].address}\n'
    answer += get_shopping_cart(id)
    answer += 'Вы подтверждаете?'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ['Да', 'Нет']
    keyboard.add(*buttons)
    await bot.send_message(id, answer, reply_markup=keyboard)
    await BotStates.second_confirm_state.set()

@dp.message_handler(state=BotStates.second_confirm_state)
async def confirm(message: types.Message):
    text = lemmatizing(message.text)
    id = message.from_user.id
    global orders
    if 'нет' in text or 'не' in text:
        customers[id].name = None
        customers[id].telephone = None
        customers[id].address = None
        answer = 'Пожалуйста, введите информацию заново. Как вас зовут?'
        keyboard = types.ReplyKeyboardRemove()
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.waiting_for_name_state.set()
    elif 'да' in text or 'подтверждать' in text:
        order_number = get_order_number()
        orders.append([order_number, customers[id].name, customers[id].telephone, customers[id].address, customers[id].shopping_cart])
        customers[id].name = None
        customers[id].telephone = None
        customers[id].address = None
        customers[id].shopping_cart = []
        answer = f'Спасибо за вашу покупку😊😊😊 Ваш номер заказа: {order_number}. Товары будут доставлены в течение одного часа, пожалуйста, подождите. Приглашаем вас вернуться снова! До скорой встречи.'
        keyboard = types.ReplyKeyboardRemove()
        await bot.send_message(id, answer, reply_markup=keyboard)
        await BotStates.end_state.set()
    else:
        answer = 'Я не понял вас.'
        await bot.send_message(id, answer)

timer = None

def refresh_product():
    global df
    inventory = [30] * 13 + [20] * 12
    df['inventory'] = inventory
    loop_refresh()

def loop_refresh():
    global timer
    timer = Timer(86400, refresh_product)
    timer.start()


if __name__ == "__main__":
    loop_refresh()
    executor.start_polling(dp)
    timer.cancel()
