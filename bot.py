from config import *
import telebot
import requests
import random
import sqlite3
import time
from threading import Thread, Event

NAMES = ['Илон Маск', 'Герман Греф', 'Михаил Круг',
         'Олег Тиньков', 'Билл Гейтс', 'Марк Цукерберг',
         'Павел Дуров', 'Тим Кук', 'Стив Джобс',
         'Гейб Ньюелл', 'Анатолий Чубайс', 'Юрий Дудь', 'Тина Канделаки',
        'Леонид Якубович', 'Владимир Путин', 'Лунтик', 'Стив Возняк', 'Альберт Эйнштейн']

if TOKEN:
    bot = telebot.TeleBot(TOKEN)
else:
    print("Set your bot's token in config.py")
    exit()

killer = Event()

# start the game
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    user_id = message.chat.id

    cur.execute('SELECT COUNT(*) FROM users WHERE id = ?', [user_id])
    if cur.fetchone()[0] != 0:
        bot.send_message(user_id, "Вы уже играете!")
        return
    while True:
        name = random.choice(NAMES)
        cur.execute('SELECT COUNT(*) FROM users WHERE name = ?', [name])
        if cur.fetchone()[0] == 0:
            break

    cur.execute('INSERT INTO users (points, name, tasks_solved, id) VALUES (?,?,?,?)', [0, name, 0, user_id])
    print('registered new user - {}, {}'.format(user_id, name))

    bot.send_message(user_id, "Добро пожаловать в игру, {}! Присылай фото с QR кодом!".format(name))

    con.commit()
    con.close()


@bot.message_handler(commands=['tower_stats'])
def tower_stats_handler(message):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    user_id = message.chat.id

    text = "Статистика по башням:\n\n"

    cur.execute('SELECT * FROM towers')
    towers = cur.fetchall()

    for tower in towers:
        text += "'{}' - ".format(tower[0])
        if tower[1] is None:
            text += 'не захвачено'
        else:
            cur.execute('SELECT * FROM users WHERE id = ?', [tower[1]])
            owner = cur.fetchone()
            text += owner[1]
        text += '\n'

    bot.send_message(user_id, text)

    con.commit()
    con.close()


@bot.message_handler(commands=['player_stats'])
def player_stats_handler(message):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    user_id = message.chat.id

    text = "Статистика по игрокам:\n\n"

    cur.execute('SELECT * FROM users')
    users = cur.fetchall()

    for user in users:
        text += "{}: {}\n".format(user[1], user[0])

    bot.send_message(user_id, text)

    con.commit()
    con.close()

def select_task(cur, user_id):
    cur.execute('SELECT * FROM tasks')
    tasks_result = cur.fetchall()
    tasks = []
    for row in tasks_result:
        tasks.append(row[3])


    cur.execute('SELECT * FROM solutions WHERE "user" = ?', [user_id])
    tasks_result = cur.fetchall()
    solved_tasks = []
    for row in tasks_result:
        solved_tasks.append(row[1])

    try:
        return random.choice([item for item in tasks if item not in solved_tasks])
    except:
        return None

#process photo
@bot.message_handler(content_types=['photo'])
def task_handler(message):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    user_id = message.chat.id

    cur.execute('SELECT * FROM users WHERE id = ?', [user_id])
    results = cur.fetchall()

    if len(results) != 1:
        bot.send_message(user_id, "Напишите /start.")
        return

    file_id = message.photo[-1].file_id

    cur.execute('SELECT COUNT(*) FROM submissions WHERE file_id = ? ', [file_id])
    if cur.fetchone()[0] != 0:
        bot.send_message(user_id, "Похоже, ты уже присылал это фото. Сделай фотографию еще раз.")
        return
    cur.execute('INSERT INTO submissions (user, file_id) VALUES (?,?)', [user_id, file_id])
    con.commit()

    path = bot.get_file(file_id)
    p = 'https://api.telegram.org/file/bot{0}/'.format(TOKEN) + path.file_path
    url = 'http://api.qrserver.com/v1/read-qr-code/'
    res = requests.post(url, {'fileurl': p})
    try:
        x = res.json()[0]['symbol'][0]['data']
        x = int(x)

        cur.execute('SELECT * FROM towers WHERE id = ? ', [x])
        towers = cur.fetchall()

        if len(towers) != 1:
            bot.send_message(user_id, "Неправильный QR код.")
            return

        tower_id = towers[0][2]
        tower_name = towers[0][0]
        tower_owner = towers[0][1]

        if user_id == tower_owner:
            bot.send_message(user_id, "Вы уже захватили эту башню.")
            return

        print("user {} attacks {}".format(user_id, tower_name))

        cur.execute('SELECT COUNT(*) FROM blocks WHERE "user" = ? and tower = ?', [user_id, tower_id])
        if cur.fetchone()[0] != 0:
            print("user {} attacks {} - blocked".format(user_id, tower_name))
            bot.send_message(user_id, "Башня '{}' временно недоступна для вас. Повторите попытку позже.".format(tower_name))
            return

        task_id = select_task(cur, user_id)
        if task_id == None:
            bot.send_message(user_id, "Похоже, задания закончились")
            return

        cur.execute('SELECT * FROM tasks WHERE id = ?', [task_id])
        task = cur.fetchone()[4]
        task = '```python\n' + task + '\n```'
        cur.execute('UPDATE users SET current_task = ? WHERE id = ?', [task_id, user_id])
        cur.execute('UPDATE users SET current_tower = ? WHERE id = ?', [tower_id, user_id])

        bot.send_message(user_id, f"Вы атакуете башню '{tower_name}'. Ваше задание:\n{task}", parse_mode='markdown')
    except Exception as e:
        print(e)
        bot.send_message(user_id, "На картинке не видно QR кода. Попробуй еще раз.")

    con.commit()
    con.close()

@bot.message_handler(content_types=['text'])
def answer_handler(message):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    user_id = message.chat.id

    cur.execute('SELECT * FROM users WHERE id = ?', [user_id])
    results = cur.fetchall()

    if len(results) != 1:
        bot.send_message(user_id, "Напишите /start.")
        return

    user = results[0]

    task_id = user[2]
    tower_id = user[5]

    if task_id == None or tower_id == None:
        bot.send_message(user_id, "Сначала нужно прислать фотографию QR кода на башне.")
        return

    cur.execute('SELECT * FROM tasks WHERE id = ?', [task_id])
    task = cur.fetchone()

    cur.execute('SELECT * FROM towers WHERE id = ?', [tower_id])
    tower = cur.fetchone()

    cur.execute('UPDATE users SET current_task = ? WHERE id = ?', [None, user_id,])
    cur.execute('UPDATE users SET current_tower = ? WHERE id = ?', [None, user_id])
    cur.execute('UPDATE users SET tasks_solved = ? WHERE id = ?', [user[3]+1, user_id])

    con.commit()

    if str(message.text) != str(task[2]):
        bot.send_message(user_id, "Ответ неверен. Башня '{}' для вас временно заблокирована. "
                                  "Попробуйте захватить другую башню или подождите.".format(tower[0]))
        cur.execute('INSERT INTO blocks (user, tower) VALUES (?,?)', [user_id, tower_id])
        con.commit()
        return

    bot.send_message(user_id, "Ответ принят! Вы захватили башню '{}'.".format(tower[0]))
    cur.execute('UPDATE towers SET owner = ? WHERE id = ?', [user_id, tower_id])
    cur.execute('INSERT INTO solutions (user, task, result, tower) VALUES (?,?,?,?)', [user_id, task_id, 1, tower_id])

    cur.execute('SELECT * FROM users')
    try:
        users = cur.fetchall()
        for row in users:
            if row[4] != user_id:
                bot.send_message(row[4], "Игрок {} захватил башню '{}'!".format(user[1], tower[0]))
    except Exception as e:
        print(e)
    con.commit()
    con.close()



def blocks_observer(killer):
    while not killer.wait(BLOCKING_DELAY):
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute('DELETE FROM blocks')

        cur.execute('SELECT * FROM users')
        users = cur.fetchall()
        try:
            for row in users:
                bot.send_message(row[4], "Все блокировки сняты!")
        except:
            pass

        con.commit()
        con.close()

def points_observer(killer):
    while not killer.wait(POINTS_INC_DELAY):
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute('SELECT * FROM towers')
        towers = cur.fetchall()
        for row in towers:
            if row[1] != None:
                cur.execute('SELECT * FROM users WHERE id = ?', [row[1]])
                user = cur.fetchone()
                cur.execute('UPDATE users SET points = ? WHERE id = ?', [user[0]+5, user[4]])

        con.commit()
        con.close()

def send_stop_messages():

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    
    for row in users:
        try:
            bot.send_message(row[4], "Игра закончилась, вернитесь в кабинет")
            print("sent to {0}".format(row[4]))
        except:
            pass

def clear_db():
    with sqlite3.connect(DB) as con:
        con.execute('UPDATE towers SET owner=null')
        tables = [
            'solutions',
            'users',
            'submissions',
            'users',
            'blocks'
        ]
        for table in tables:
            con.execute(f'DELETE FROM {table}')
        con.commit()

def bot_poll():
    bot.polling(none_stop=True)

def stop_bot():
    killer.set()
    send_stop_messages()
    clear_db()
    bot.stop_polling()

def main():

    print(
        '''
        > Bot is ready.
        Enter "start" to start the game or "exit" to exit.
        During the game, enter "stop" to clean up database and pause bot without exit.
        Then you can restart the game with "start" command.'''
        )

    while True:
        cmd = input()

        if cmd == 'start':
            print("Starting bot's threads...")

            blocks_thread = Thread(target=blocks_observer, name='blocks', args=(killer,))
            points_thread = Thread(target=points_observer, name='points', args=(killer,))
            poll_thread = Thread(target=bot_poll, name='poll')

            points_thread.start()
            blocks_thread.start()
            poll_thread.start()

            print('Game started')

        elif cmd == 'stop':
            stop_bot()
            print('Bot is suspended. Print start to restart')
        
        elif cmd == 'exit':
            print('Exiting...')
            stop_bot()
            break

if __name__ == '__main__':
    main()
