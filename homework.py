import os
import time

import requests
import logging

from telegram import Bot
from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()

ENV_VAR = {
    'PRACTICUM_TOKEN': os.getenv('PRACTICUM_TOKEN'),
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN'),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
}

RETRY_TIME = 300
HEADERS = {'Authorization': f'OAuth {ENV_VAR.get("PRACTICUM_TOKEN")}'}
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class DebugException(Exception):
    """Обработка исключений, требующих debug-сообщений."""

    pass


class InfoException(Exception):
    """Обработка исключений, требующих info-сообщений."""

    pass


class ErrorException(Exception):
    """Обработка исключений, требующих error-сообщений."""

    pass


class CriticalException(Exception):
    """Обработка исключений, требующих critical-сообщений."""

    pass


def send_message(bot, message):
    """Отправка сообщения выбранным ботом фиксированному пользователю."""
    user_id = ENV_VAR.get('TELEGRAM_CHAT_ID')

    try:
        bot.send_message(
            chat_id=user_id,
            text=message
        )
        logging.info(f'Сообщение пользователю {user_id} успешно отправлено')

    except Exception:
        logging.error(f'Ошибка при отправке сообщения пользователю {user_id}')


def get_api_answer(url, current_timestamp):
    """Получение HTTP-ответа от API-сервиса."""
    try:
        payload = {'from_date': current_timestamp}
        practicum_response = requests.get(
            url, headers=HEADERS, params=payload
        )

        if practicum_response.status_code == HTTPStatus.OK.value:
            return practicum_response.json()

        raise ErrorException('Неудачный HTTP-запрос')

    except Exception:
        raise ErrorException('Неудачный HTTP-запрос')


def parse_status(homework):
    """Анализ словаря с данными о домашней работе."""
    verdict = homework.get('status')
    homework_name = homework.get('homework_name')

    if (verdict or homework_name) is None:
        raise ErrorException('Нехватка данных в API-ответе')

    verdict = VERDICTS.get(verdict)

    # Неизвестные статусы отсеиваются в check_response
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверка полученного API-ответа на корректность."""
    homework = response.get('homeworks')

    if homework is None:
        raise ErrorException('API-ответ пуст')

    if len(homework) == 0:
        raise DebugException('Нет обновлений')

    homework = homework[0]

    if homework.get('status') not in VERDICTS.keys():
        raise ErrorException('Статус работы в API-ответе не распознан')

    return homework


def env_check():
    """Проверка наличия всех переменных окружения."""
    for var in ENV_VAR.keys():
        if ENV_VAR.get(var) is None:
            message = (
                f'Критическая ошибка: отсутствует переменная окружения {var}'
            )

            logging.critical(message)
            exit()


def main():
    """
    Тело бота. Функционал.
        - Отправляет периодические HTTP-запросы на API Яндекс.Практикум;
        - Анализирует полученные ответы;
        - Пересылает статус домашней работы выбранному telegram-пользователю;
    """
    env_check()

    try:
        bot = Bot(token=ENV_VAR.get("TELEGRAM_TOKEN"))

    except Exception:
        logging.critical('Ошибка при создании объекта бота')
        exit()

    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(response)
            verdict = parse_status(homework)
            send_message(bot, verdict)

            current_timestamp = int(time.time())

        except InfoException as info:
            logging.info(info)

        except ErrorException as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)

        except CriticalException as error:
            message = f'Критическая ошибка: {error}'
            logging.critical(message)

        finally:
            try:
                time.sleep(RETRY_TIME)

            except KeyboardInterrupt:
                break

    logging.info('Бот отключен')


if __name__ == '__main__':
    main()
