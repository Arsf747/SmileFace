import cv2
from datetime import datetime
from deepface import DeepFace
import requests
import numpy
import pickle
from sklearn.metrics.pairwise import cosine_similarity
from fer import FER
from io import BytesIO
import sqlite3
import telebot
from telebot import types

from settings import token

emo_sl = {
    'Злость (angry)': 'angry',
    'Радость (happy)': 'happy',
    'Удивление (surprise)': 'surprise',
    'Отвращение (disgust)': 'disgust',
    'Грусть (sad)': 'sad',
    'Страх (fear)': 'fear'
}

bot = telebot.TeleBot(token)
connection = sqlite3.connect('e:\Desktop\BotSmileFace\ebot\SmileFace.db', check_same_thread=False) 
# Замените путь, данный выше, на реальный путь к базе данных
cursor = connection.cursor()
emotion_detector = FER()

@bot.message_handler(commands=['start'])
def start(message):
    dcheck = []
    user_id = message.from_user.id
    user_name = message.from_user.username
    user_fname = message.from_user.first_name
    user_sname = message.from_user.last_name
    if not user_name:
        if not user_sname:
            params = (user_id, f'(нет никнейма) {user_fname}', 0)
        else:
            params = (user_id, f'(нет никнейма) {user_fname} {user_sname}', 0)
    else:
        if not user_sname:
            params = (user_id, f'{user_name} ({user_fname})', 0)
        else:
            params = (user_id, f'{user_name} ({user_fname} {user_sname})', 0)
    cursor.execute('INSERT OR IGNORE INTO Users(id, username_fullname, daily_photos_sent) VALUES(?, ?, ?)', params)
    connection.commit()
    cursor.execute('SELECT created_at FROM Photos WHERE user_id = ?', [user_id])
    last_call = cursor.fetchall()
    now = datetime.now()
    nowd = now.day
    for j in range(len(last_call)):
        datebd = datetime.strptime(last_call[j][0], "%Y-%m-%d %H:%M:%S.%f")
        dcheck.append(datebd.day)
    if nowd not in dcheck:
        dailnum = 0
        cursor.execute('UPDATE Users SET daily_photos_sent = ? WHERE id = ?', (dailnum, user_id,))
        connection.commit()
    cursor.execute('SELECT daily_photos_sent FROM Users WHERE id = ?', [user_id])
    daily_photo_sp = cursor.fetchone()
    if daily_photo_sp[0] >= 5:
        bot.send_message(message.chat.id, "Ты отправил 5 фото за сегодня, попробуй позже")
    else:    
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Злость (angry)")
        btn2 = types.KeyboardButton("Радость (happy)")
        btn3 = types.KeyboardButton("Удивление (surprise)")
        btn4 = types.KeyboardButton("Отвращение (disgust)")
        btn5 = types.KeyboardButton("Грусть (sad)")
        btn6 = types.KeyboardButton("Страх (fear)")
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
        bot.send_message(message.chat.id, "Давай найдем друга по настроению! Выбери эмоцию", reply_markup=markup)
        bot.register_next_step_handler(message, emotion_photo)

def emotion_photo(message):
    sel_emo = message.text
    if sel_emo == "Злость (angry)" or sel_emo == "Радость (happy)" or sel_emo == "Удивление (surprise)" or sel_emo == "Отвращение (disgust)" or sel_emo == "Грусть (sad)" or sel_emo == "Страх (fear)":
        bot.send_message(message.chat.id, f"Отлично, выбрана эмоция {sel_emo}. Сфотографируйся с этой эмоцией", reply_markup = types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
    else:
        bot.send_message(message.chat.id, "Это что-то не то... Выбери из списка")
        bot.register_next_step_handler(message,emotion_photo)

def valid_photo(message, sel_emo):
    try:
        photo = message.photo[-1]
    except:
        if message.text == '/start':
            start(message)
        else:
            bot.send_message(message.chat.id, "Это не фото")
            bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
    else:
        photo_id = photo.file_id
        file_path = bot.get_file_url(photo_id)
        imgbytes = requests.get(file_path).content
        img_str = BytesIO(imgbytes)
        face_cascade = cv2.CascadeClassifier('e:\Desktop\BotSmileFace\ebot\haarcascade_frontalface_default.xml')
        # Замените путь, данный выше, на реальный путь к каскейду
        image = cv2.imdecode(numpy.frombuffer(img_str.read(), numpy.uint8), 1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor= 1.1,
        minNeighbors= 5,
        minSize=(10, 10)
        )
        if len(faces) == 0:
            bot.send_message(message.chat.id, "Я не вижу лица. Давай еще дубль")
            bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
        elif len(faces) > 1:
            bot.send_message(message.chat.id, "Слушай, твои бро мешают. Сфотайся один")
            bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
        else:
            for (x, y, w, h) in faces:
                cv2.rectangle(image, (x, y), (x+w, y+h), (255, 255, 0), 2)
            proc = (w*h)/(gray.shape[0]*gray.shape[1])
            if round(proc*100) < 50:
                bot.send_message(message.chat.id, "Лицо должно занимать хотя бы 50% фото, попробуй обрезать края фото. Давай еще дубль")
                bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
            else:
                cap_emo = emotion_detector.detect_emotions(image)
                dom_emo = emotion_detector.top_emotion(image)
                if not cap_emo:
                    bot.send_message(message.chat.id, "Я не понял, что это за эмоция. Давай еще дубль")
                    bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
                else:
                    if emo_sl[sel_emo] == dom_emo[0]:
                        cursor.execute('SELECT id FROM Photos WHERE id = ?', (photo_id,))
                        matchedphoto = cursor.fetchone()
                        if matchedphoto:
                            bot.send_message(message.chat.id, "Это фото у меня уже есть. Прям по-новому сфотографируйся, еще дубль")
                            bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))
                        else:
                            bot.send_message(message.chat.id, "Отличное фото, сейчас поищу твоего друга по настроению...")
                            search_face(message, sel_emo, file_path, photo_id, imgbytes)
                    else:
                        bot.send_message(message.chat.id, f"Это не та эмоция. It's {dom_emo[0]}. Надо {sel_emo}. Давай еще дубль")
                        bot.register_next_step_handler(message, lambda msg: valid_photo(msg, sel_emo))

def search_face(message, sel_emo, file_path, photo_id, imgbytes):
    embeddingr1 = DeepFace.represent(
            img_path=file_path,
            model_name="VGG-Face",
            enforce_detection=True
        )
    embedding1 = embeddingr1[0]['embedding']
    cursor.execute('SELECT * FROM Photos')
    photos_sp = cursor.fetchall()
    simm = 0
    user_id = message.from_user.id
    for i in range(len(photos_sp)):
        if user_id != photos_sp[i][1]:
            if emo_sl[sel_emo] == photos_sp[i][4]:
                embedding2 = pickle.loads(photos_sp[i][3])
                sim = cosine_similarity([embedding1], [embedding2])[0][0]
                if sim > simm:
                    simm = sim
                    match_img = photos_sp[i][2]
    if simm == 0:
        bot.send_message(message.chat.id, "У меня нет никого с твоей эмоцией... Что-ж, будешь первый, я сохранил твою фотографию")
        timestamp = datetime.now()
        params = (photo_id, user_id, imgbytes, pickle.dumps(embedding1), emo_sl[sel_emo], timestamp)
        cursor.execute('INSERT INTO Photos(id, user_id, image, embedding, emotion, created_at) VALUES(?, ?, ?, ?, ?, ?)', params)
        connection.commit()
        add_daily(message)
    else:
        cursor.execute('SELECT user_id FROM Photos WHERE image = ?', (match_img,))
        match_user_id = cursor.fetchone()
        cursor.execute('SELECT username_fullname FROM Users WHERE id = ?', match_user_id)
        musername = cursor.fetchone()
        bot.send_photo(message.chat.id, match_img)
        bot.send_message(message.chat.id, f"Нашел похожее лицо. Вы с ним похожи на {round(simm*100)}%. Его отправил @{musername[0]}. Сохранил твое фото")
        timestamp2 = datetime.now()
        params = (photo_id, user_id, imgbytes, pickle.dumps(embedding1), emo_sl[sel_emo], timestamp2)
        cursor.execute('INSERT INTO Photos(id, user_id, image, embedding, emotion, created_at) VALUES(?, ?, ?, ?, ?, ?)', params)
        params2 = (match_user_id[0], user_id, photo_id, timestamp2)
        cursor.execute('INSERT INTO sent_matches(sender_id, receiver_id, photo_id, created_at) VALUES(?, ?, ?, ?)', params2)
        cursor.execute('DELETE FROM Photos WHERE image = ?', (match_img,))
        connection.commit()
        add_daily(message)

def add_daily(message):
    user_id = message.from_user.id
    cursor.execute('SELECT daily_photos_sent FROM Users WHERE id = ?', [user_id])
    daily = cursor.fetchone()
    dailnum = daily[0]
    dailnum += 1
    cursor.execute('UPDATE Users SET daily_photos_sent = ? WHERE id = ?', (dailnum, user_id,))
    connection.commit()

bot.polling()