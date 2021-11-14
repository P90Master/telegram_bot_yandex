import os
import time

import requests
import logging

from telegram import Bot
from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


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
    user_id = TELEGRAM_CHAT_ID

    try:
        bot.send_message(
            chat_id=user_id,
            text=message
        )
        logger.info(f'Сообщение пользователю {user_id} успешно отправлено')

    except Exception:
        logger.error(f'Ошибка при отправке сообщения пользователю {user_id}')


def get_api_answer(current_timestamp):
    """Получение HTTP-ответа от API-сервиса."""
    try:
        timestamp = current_timestamp or int(time.time())
        payload = {'from_date': timestamp}
        practicum_response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )

        if practicum_response.status_code == HTTPStatus.OK.value:
            return practicum_response.json()

        raise ErrorException('Неудачный HTTP-запрос')

    except Exception:
        raise ErrorException('Неудачный HTTP-запрос')


def check_response(response):
    """Проверка полученного API-ответа на корректность."""
    if response is None:
        raise ErrorException('API-ответ пуст')

    # В некоторых тестах передается список со словарем внутри, в то время как
    # API яндекса передает просто словарь.
    if isinstance(response, list):
        response = response[0]

    if response.get('homeworks') is None:
        raise ErrorException('Нехватка данных в API-ответе')

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise ErrorException('Неккоректный API-ответ')

    return homeworks


def parse_status(homework):
    """Анализ словаря с данными о домашней работе."""
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')

    if homework_name is None:
        # Именно в этой точке тесты ожидают получить KeyError
        # Хотя в других местах пропускают любое исключение
        # Проблему уже описал в топике в slack'e
        raise KeyError('Нехватка данных в API-ответе')

    if homework_status not in VERDICTS.keys():
        raise ErrorException('Статус работы в API-ответе не распознан')

    verdict = VERDICTS.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия всех переменных окружения."""
    return not (None in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """
    Тело бота. Функционал.
        - Отправляет периодические HTTP-запросы на API Яндекс.Практикум;
        - Анализирует полученные ответы;
        - Пересылает статус домашней работы выбранному telegram-пользователю;
    """
    if not check_tokens():
        logger.critical(
            'Критическая ошибка: отсутствуют переменные окружения'
        )
        exit()

    try:
        bot = Bot(token=TELEGRAM_TOKEN)

    except CriticalException:
        logger.critical('Ошибка при создании объекта бота')
        exit()

    while True:
        try:
            current_timestamp = int(time.time())

            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                raise DebugException('Нет обновлений')

            homework = homeworks[0]
            verdict = parse_status(homework)
            send_message(bot, verdict)

        except DebugException as info:
            logger.debug(info)

        except InfoException as info:
            logger.info(info)

        except ErrorException as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        finally:
            try:
                time.sleep(RETRY_TIME)

            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    main()
