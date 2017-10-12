import config
import telebot
import requests
import random
import sqlite3


names = ['name1', 'name2', 'name3', 'name4', 'name5', 'name6', 'name7', 'name8', 'name9']

bot = telebot.TeleBot(config.token)


# start the game
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    con = sqlite3.connect('database.sqlite')
    cur = con.cursor()

    user_id = message.chat.id

    cur.execute('SELECT COUNT(*) FROM users WHERE id = ?', [user_id])
    if cur.fetchone()[0] == 0:
        return
    while True:
        name = random.choice(names)
        cur.execute('SELECT COUNT(*) FROM users WHERE name = ?', [name])
        if cur.fetchone()[0] == 0:
            break

    cur.execute('INSERT INTO users (points, name, tasks_solved, id) VALUES (?,?,?,?)', [0,name,0,user_id])
    print('registered new user - {}, {}'.format(user_id, name))

    bot.send_message(user_id, "Добро пожаловать в игру, {}! Присылай фото с QR кодом!".format(name))

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
    con = sqlite3.connect('database.sqlite')
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
    p = 'https://api.telegram.org/file/bot{0}/'.format(config.token) + path.file_path
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
        task = cur.fetchone()

        cur.execute('UPDATE users SET current_task = ? WHERE id = ?', [task_id, user_id])
        cur.execute('UPDATE users SET current_tower = ? WHERE id = ?', [tower_id, user_id])

        bot.send_message(user_id, "Вы атакуете башню '{}'. Ваше задание: {}.".format(tower_name, task[1]))
    except Exception as e:
        print(e)
        bot.send_message(user_id, "На картинке не видно QR кода. Попробуй еще раз.")

    con.commit()
    con.close()

@bot.message_handler(content_types=['text'])
def answer_handler(message):
    con = sqlite3.connect('database.sqlite')
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

    con.commit()

    if str(message.text) != str(task[2]):
        bot.send_message(user_id, "Ответ неверен. Башня '{}' для вас временно заблокирована. "
                                  "Попробуйте захватить другую башню или подождите.".format(tower[0]))
        cur.execute('INSERT INTO blocks (user, tower) VALUES (?,?)', [user_id, tower_id])
        return

    bot.send_message(user_id, "Ответ принят! Вы захватили башню '{}'.".format(tower[0]))
    cur.execute('UPDATE towers SET owner = ? WHERE id = ?', [user_id, tower_id])

    con.commit()
    con.close()


bot.polling(none_stop=True)
