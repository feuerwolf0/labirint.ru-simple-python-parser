from urllib.parse import quote
import requests
import fake_headers
import bs4
import os
from concurrent.futures import ThreadPoolExecutor
import datetime
import json
import re
import csv
import shutil


# ---------------- Конфигурация ----------------
QUERY = 'java' # Поисковый запрос
THREAD_COUNT = 5 # Количество потоков для загрузки страниц
TEMP_PATH = 'temp' # Название папки для временного хранения html страниц
# ----------------------------------------------


URL = f'https://www.labirint.ru/search/{quote(QUERY)}/?display=table&id_genre=-1'

# Создаю заголовок
header = fake_headers.Headers(
    browser='chrome',
    os='win',
    headers=True
)
HEADER = header.generate()

def main():
    
    # Получаю начальное время работы скрипта
    start = datetime.datetime.now()

    # Создаю папку для временных файлов html страниц
    if not os.path.exists(TEMP_PATH):
        os.mkdir(TEMP_PATH)

    # Получаю страницу результатов поиска
    response = requests.get(url=URL, headers=HEADER)

    if response.status_code == 200:
        print(f'Страница по запросу {QUERY} успешно загружена')
    else:
        print(f'Что-то пошло не так, код ошибки: {response.status_code}')

    # Сохраняю первую страницу во временной папке
    with open(f'{TEMP_PATH}/1.html', 'w', encoding='utf-8') as file:
        file.write(response.text)
    print('Страница 1 успешно загружена и сохранена')

    # Создаю суп
    soup = bs4.BeautifulSoup(response.text, 'lxml')

    # Получаю количество страниц книг
    pages_count = int(soup.find('div', 'pagination-numbers__right').findAll('div', 'pagination-number')[-1].text.strip())
    print(f'Найдено страниц: {pages_count}')

    # Получаю количество найденных книг
    books_count = int(soup.find('div', class_='b-stab-e-wrapper-container').find('span', 'b-stab-e-slider-item-e-txt-m-small js-search-tab-count').text)
    print(f'Найдено книг: {books_count}')

    # Создаю пул для сохранения всех найденых страниц мультипоточно
    print('Начинаю сохранять страницы')
    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        pool.map(save_temp_pages, range(2,pages_count+1))
    print('Все страницы сохранены')

    # Получаю список всех книг
    all_books = get_all_data_from_page(pages_count)

    # Сохраняю полученный список в json формате
    current_time = datetime.datetime.now().strftime('%Y%m%d_%H_%M_%S')
    with open(f'result_{current_time}.json', 'w', encoding='utf-8') as file:
        json.dump(all_books, file, ensure_ascii=False, indent=4)
        print(f'Книг сохранено: {len(all_books)} \nРезультат сохранен в файл result_{current_time}.json')

    # Сохраняю полученный список в csv формате
    with open(f'result_{current_time}.csv', 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['Название', 'Ссылка', 'Автор', 'Издательство', 'Цена', 'Размер скидки', 'Старая цена', 'Наличие']
        writer = csv.DictWriter(file, delimiter=',', quotechar='"', fieldnames=fieldnames)
        writer.writeheader()
        for book in all_books:
            writer.writerow(book)
        print(f'Результат сохранен в файл result_{current_time}.csv')

    # Удаляю временную папку
    if os.path.exists(TEMP_PATH):
        shutil.rmtree(TEMP_PATH)

    end = datetime.datetime.now()
    print(f'Работа скрипта завершена. Время выполнения: {end-start}')


def save_temp_pages(num_page):
    """Функция загружает и сохраняет страницу num_page"""
    params = {
        'page': f'{num_page}'
    }
    response = requests.get(url=URL, headers=HEADER, params=params)
    if response.status_code == 200:
        with open(f'{TEMP_PATH}/{num_page}.html', 'w', encoding='utf-8') as file:
            file.write(response.text)
            print(f'Страница {num_page} успешно загружена и сохранена')
    else:
        print(f'Что-то пошло не так. Страница {num_page} не загружена. Код ошибки: {response.status_code}')


def get_all_data_from_page(pages_count):
    """Собирает все книги со страницы
       Получает: pages_count - количество страниц
       Возвращает: список всех книг со всех страниц"""
    all_books = []
    for page in range(1, pages_count+1):
        # Получаю исходный код html страницы
        with open(f'{TEMP_PATH}/{page}.html', 'r', encoding='utf-8') as file:
            html = file.read()
        
        # Создаю суп
        soup = bs4.BeautifulSoup(html, 'lxml')

        all_src_books = []
        # Получаю список всех книг на странице
        all_src_books = soup.find('tbody', 'products-table__body').find_all('tr')

        current_book = dict()
        for row in all_src_books:
            item = row.find_all('td')
            pattern = r'\s+'
            # Собираю словарь для 1 книги
            current_book = dict()
            current_book['Название'] = item[0].text.strip()
            current_book['Ссылка'] = 'https://www.labirint.ru' + item[0].find('a')['href']
            current_book['Автор'] = item[1].text.strip()
            # Удаляю лишние пробелы из издательства
            current_book['Издательство'] = re.sub(pattern, ' ', item[2].text.strip())
            current_book['Цена'] = item[3].find('span', 'price-val').text.strip()
            # Если скидка есть:
            if item[3].find('span', 'price-old'):
                current_book['Размер скидки'] = item[3].find('span', 'price-val').get('title')
                current_book['Старая цена'] = item[3].find('span', 'price-gray').text.strip()

            current_book['Наличие'] = item[-1].text.strip()

            # Добавляю словарь в список книг
            all_books.append(current_book)
    return all_books


if __name__ == '__main__':
    main()