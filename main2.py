import openai
import config
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ParseMode, ChatActions
import urllib.request
import io
from pydub import AudioSegment
import pathlib
import ffmpeg
import os
from gtts import gTTS
import ssl
import json
from time import sleep
#from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

#отключаем проверку ssl сертификата для создания картинок
ssl._create_default_https_context = ssl._create_unverified_context

openai.api_key = config.API_KEY
bot_token = config.BOT_TOKEN
bot = Bot(token=bot_token)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message):
    user_id = message.from_user.id
    await message.answer_sticker(r'CAACAgIAAxkBAAEIiL9kNGvZV9LhAgAB2h09dQf0xvuuy4IAAk4CAAJWnb0KMP5rbYEyA28vBA')
    await message.answer(f'Привет, {message.from_user.full_name}! Это ChatGPT 🤖 \nДля того, что бы начать общение - просто отправь ему сообщение')


 @dp.message_handler(content_types=types.ContentType.VOICE)
 async def voices(message: types.Message):
     await bot.send_chat_action(message.chat.id, ChatActions.UPLOAD_VOICE)
     try:
         voice_id = message.voice.file_id

         # получение файла голосового сообщения
         file = await bot.get_file(voice_id)
         await file.download() #скачиваем аудиосообщение

         input_file = pathlib.Path(file.file_path)
         output_file = str(file.file_unique_id)+".mp4"

         stream = ffmpeg.input(input_file)
         stream = ffmpeg.output(stream, output_file)
         ffmpeg.run(stream)

         #await message.answer(f"The ID of the audio is {voice_id} и после get_file получили: {file}")
         audio_file = open(output_file, "rb")

         #получаем транскрипцию аудио
         transcript = openai.Audio.transcribe("whisper-1", audio_file)
         user_input = transcript['text']
         chat_log.append({"role": "user", "content": user_input})
         response = openai.ChatCompletion.create(
             model="gpt-3.5-turbo",
             messages=chat_log
         )

         answer = response.choices[0].message
         await message.answer(f"Ваше сообщение: {user_input}")
         await message.answer(answer['content'])
         audio_file.close()
         os.remove(output_file)
         print('4')
         input_file.unlink()
         print('4')
      except Exception as e:
         await message.answer(f"Ошибка в войсе: {str(e)}")

@dp.message_handler(commands=['stop'])
async def stop_chat(message: types.Message):
    await message.answer('Тема была очищена. Для начала новой темы для обсуждения, введите свое сообщение')

@dp.message_handler(commands=['image'])
async def echo(message: types.Message):
    user_input = message.text
    try:
        response = openai.Image.create(
            prompt=user_input,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']

        with urllib.request.urlopen(image_url) as u:
            photo_data = u.read()
            photo_buffer = io.BytesIO(photo_data)
            await bot.send_photo(message.chat.id, photo_buffer)
    except Exception as e:
        await message.answer(f"Ошибка image: {str(e)}")

 @dp.message_handler(commands=['say'])
 async def synthesize_handler(message: types.Message):

     user_input = message.text
     chat_log.append({"role": "user", "content": user_input})
     response = openai.ChatCompletion.create(
         model="gpt-3.5-turbo",
         messages=chat_log
     )
     answer = response.choices[0].message
     chat_log.append({"role": "assistant", "content": answer["content"]})

     tts = gTTS(text=answer["content"], lang='ru')
     tts.save('temp.mp3')

     sound = AudioSegment.from_file('temp.mp3')
     new_sound = sound.speedup(playback_speed=1.2)
     new_sound.export('temp_fast.mp3', format='mp3')

     # Отправляем голосовое сообщение пользователю
     with open('temp_fast.mp3', 'rb') as f:
         voice = types.Voice(f)
         await bot.send_voice(message.chat.id, voice=f)

     # Удаляем временный файл
     os.remove('temp.mp3')

@dp.message_handler()
async def message_answer(message: types.Message):
    await bot.send_chat_action(message.chat.id, ChatActions.TYPING)
    user_id = message.from_user.id
    with open('chat_logs.json', 'r') as f:
        chat_logs = json.load(f)

    if str(user_id) in chat_logs:
        user_chat_log = chat_logs[str(user_id)]

    else:
        user_chat_log = {f"{user_id}":
                        [{"role": "system", "content": "Ты полезный бот-помощник."}]
                }
    #print(user_chat_log)
    #print(user_chat_log[f"{user_id}"])
    user_input = message.text

    user_chat_log[f"{user_id}"].append({"role": "user", "content": user_input})
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=user_chat_log[f"{user_id}"]
        )
        answer = response.choices[0].message
        user_chat_log[f"{user_id}"].append({"role": "assistant", "content": answer["content"]})

        await message.answer(answer['content'])  # parse_mode=markdown
        chat_logs[str(user_id)] = user_chat_log

        with open('chat_logs.json', 'w') as f:
            json.dump(chat_logs, f)

        if response['usage']['total_tokens'] > 4000:
            user_chat_log[f"{user_id}"] = {"Превышение": f"{response['usage']['total_tokens']}"}
            chat_logs[str(user_id)] = user_chat_log
            await message.answer('Тема была очищена из-за превышения количества отправленных токенов. Для начала новой темы для обсуждения, введите свое сообщение')
            with open('chat_logs.json', 'w') as f:
                json.dump(chat_logs, f)

    except openai.error.RateLimitError as e:
        #await message.answer(f"ошибка времени: {str(e)}")
        await message.answer("Превышение лимита запросов! Можно отправлять до 3 запросов в минуту")
        wait_time = 20
        await message.answer(f"Подождите, пожалуйста, {wait_time} секунд...")
        sleep(wait_time)
        pass
    except Exception as e:
        await message.answer(f"Error: {str(e)}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)