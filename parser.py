#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер для страницы Papa Don't Preach
Извлекает данные о товарах и создает CSV файл в формате TSUM
"""

import re
import json
import csv
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import os
import requests
import time


def js_to_json(js_str):
    """Преобразует JavaScript объект в валидный JSON"""
    # Это упрощенная версия - для сложных случаев лучше использовать альтернативный метод
    
    # Сначала заменяем экранированные слеши
    js_str = js_str.replace('\\/', '/')
    
    # Заменяем ключи без кавычек на ключи с кавычками
    # Но только если они не внутри строк
    # Паттерн: начало строки или запятая/открывающая скобка, затем ключ, затем двоеточие
    def add_quotes_to_keys(match):
        prefix = match.group(1)  # пробелы/запятые/скобки перед ключом
        key = match.group(2)     # сам ключ
        return f'{prefix}"{key}":'
    
    # Заменяем ключи без кавычек (но не внутри строковых значений)
    js_str = re.sub(r'([{,]\s*)(\w+)\s*:', add_quotes_to_keys, js_str)
    
    # Заменяем true/false/null на их JSON эквиваленты (они уже правильные)
    # Ничего не делаем, они уже в правильном формате
    
    return js_str


def extract_product_data(html_content, product_url=None):
    """Извлекает данные о товаре из HTML"""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Извлекаем данные из JavaScript объекта KiwiSizing.data
    kiwi_data_match = re.search(r'KiwiSizing\.data\s*=\s*({.*?});', html_content, re.DOTALL)
    
    if not kiwi_data_match:
        print("Не найдены данные KiwiSizing.data")
        return None
    
    # Используем альтернативный метод через регулярные выражения
    # так как JavaScript объект сложно преобразовать в JSON
    # Если URL не передан, пытаемся извлечь из HTML
    if not product_url:
        url_match = re.search(r'saved from url=\([^)]+\)(https://[^\s]+)', html_content)
        product_url = url_match.group(1) if url_match else None
        
        if not product_url:
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical:
                product_url = canonical.get('href', '')
    
    return extract_product_data_regex(html_content, product_url)
    
    # Используем общую функцию обработки данных
    return process_kiwi_data(kiwi_data, html_content, soup)


def extract_product_data_regex(html_content, product_url=None):
    """Альтернативный метод извлечения данных через регулярные выражения"""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    kiwi_data = {}
    
    # Извлекаем product ID
    product_match = re.search(r'product:\s*"([^"]+)"', html_content)
    if product_match:
        kiwi_data['product'] = product_match.group(1)
    
    # Извлекаем title
    title_match = re.search(r'title:\s*"([^"]+)"', html_content)
    if title_match:
        kiwi_data['title'] = title_match.group(1)
    
    # Извлекаем vendor
    vendor_match = re.search(r'vendor:\s*"([^"]+)"', html_content)
    if vendor_match:
        kiwi_data['vendor'] = vendor_match.group(1)
    
    # Извлекаем type
    type_match = re.search(r'type:\s*"([^"]+)"', html_content)
    if type_match:
        kiwi_data['type'] = type_match.group(1)
    
    # Извлекаем images (массив)
    images_match = re.search(r'images:\s*\[(.*?)\]', html_content, re.DOTALL)
    if images_match:
        images_str = images_match.group(1)
        # Извлекаем все URL из массива
        image_urls = re.findall(r'"([^"]+)"', images_str)
        # Очищаем от экранированных слешей
        image_urls = [url.replace('\\/', '/') for url in image_urls]
        kiwi_data['images'] = image_urls
    
    # Извлекаем variants (размеры и SKU)
    variants_match = re.search(r'variants:\s*\[(.*?)\]', html_content, re.DOTALL)
    variants = []
    if variants_match:
        variants_str = variants_match.group(1)
        # Извлекаем все варианты как отдельные объекты
        # Каждый вариант начинается с {"id":...
        variant_blocks = re.findall(r'\{"id":\d+.*?"public_title":"([^"]+)".*?"sku":"([^"]+)"', variants_str)
        
        for public_title, sku in variant_blocks:
            variants.append({'public_title': public_title, 'sku': sku})
    
    kiwi_data['variants'] = variants
    
    # Теперь используем те же методы обработки
    return process_kiwi_data(kiwi_data, html_content, soup, product_url)


def process_kiwi_data(kiwi_data, html_content, soup, product_url=None):
    """Обрабатывает данные из kiwi_data и возвращает готовый словарь для CSV"""
    
    # Извлекаем URL страницы
    if not product_url:
        url_match = re.search(r'saved from url=\([^)]+\)(https://[^\s]+)', html_content)
        if url_match:
            product_url = url_match.group(1)
        else:
            # Пробуем найти в canonical link
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical:
                product_url = canonical.get('href', '')
            else:
                product_url = ''
    
    # Извлекаем название товара
    title = kiwi_data.get('title', '')
    
    # Извлекаем бренд
    brand = kiwi_data.get('vendor', '')
    
    # Извлекаем категорию
    category = kiwi_data.get('type', '')
    
    # Извлекаем ID товара
    product_id = kiwi_data.get('product', '')
    
    # Извлекаем изображения
    images = kiwi_data.get('images', [])
    
    # Обрабатываем изображения согласно требованиям
    # IMAGE2 = первое фото (индекс 0)
    # EXT IMAGES = второе и третье фото (индексы 1 и 2), если они есть
    image2 = ''
    ext_images = ''
    
    if len(images) > 0:
        # Преобразуем относительный URL в абсолютный
        first_image = images[0]
        if first_image.startswith('//'):
            image2 = 'https:' + first_image
        elif first_image.startswith('/'):
            image2 = 'https://www.papadontpreach.com' + first_image
        else:
            image2 = first_image
    
    # Обрабатываем EXT IMAGES
    if len(images) >= 3:
        # Если есть 3+ фото, берем 2-е и 3-е
        img2 = images[1]
        img3 = images[2]
        
        if img2.startswith('//'):
            img2 = 'https:' + img2
        elif img2.startswith('/'):
            img2 = 'https://www.papadontpreach.com' + img2
            
        if img3.startswith('//'):
            img3 = 'https:' + img3
        elif img3.startswith('/'):
            img3 = 'https://www.papadontpreach.com' + img3
        
        ext_images = f"{img2},{img3}"
    elif len(images) == 2:
        # Если только 2 фото, берем только 2-е
        img2 = images[1]
        if img2.startswith('//'):
            img2 = 'https:' + img2
        elif img2.startswith('/'):
            img2 = 'https://www.papadontpreach.com' + img2
        ext_images = img2
    # Если только 1 фото, ext_images остается пустым
    
    # Извлекаем описание
    description = ''
    # Пробуем найти описание в SwymProductInfo
    swym_match = re.search(r'window\.SwymProductInfo\.product\s*=\s*({.*?});', html_content, re.DOTALL)
    if swym_match:
        try:
            swym_data_str = swym_match.group(1)
            swym_data_str = swym_data_str.replace('\\/', '/')
            swym_data = json.loads(swym_data_str)
            description_html = swym_data.get('description', '')
            # Удаляем HTML теги из описания
            if description_html:
                desc_soup = BeautifulSoup(description_html, 'html.parser')
                description = desc_soup.get_text(separator=' ', strip=True)
        except:
            pass
    
    # Если описание не найдено, пробуем найти в meta description
    if not description:
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')
    
    # Если описание все еще пустое, пробуем найти в og:description
    if not description:
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            description = og_desc.get('content', '')
    
    # Извлекаем размеры из вариантов
    sizes = []
    variants = kiwi_data.get('variants', [])
    for variant in variants:
        size = variant.get('public_title', '')
        if size and size not in sizes:
            sizes.append(size)
    
    sizes_str = ','.join(sizes) if sizes else ''
    
    # Извлекаем артикул (SKU) - берем первый вариант
    article = ''
    if variants:
        article = variants[0].get('sku', '')
    
    # Генерируем ID2 (UUID-подобный формат)
    import uuid
    id2 = str(uuid.uuid4())
    
    # Цвет и пол - пока оставляем пустыми, так как в данных нет явной информации
    color = ''
    gender = ''
    
    return {
        'URL': product_url,
        'ID': product_id,
        'Name': title,
        'Brand': brand,
        'Article': article,
        'Gender': gender,
        'Image2': image2,
        'Ext Images': ext_images,
        'Description': description,
        'Sizes': sizes_str,
        'Color': color,
        'Category': category,
        'ID2': id2,
        'Combine': ''
    }


def parse_html_file(html_file_path):
    """Парсит HTML файл и возвращает данные о товаре"""
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return None
    
    return extract_product_data(html_content)


def download_html(url):
    """Скачивает HTML страницу по URL"""
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании {url}: {e}")
        return None


def parse_url(url):
    """Парсит товар по URL"""
    
    print(f"Обработка: {url}")
    
    # Скачиваем HTML
    html_content = download_html(url)
    if not html_content:
        return None
    
    # Парсим данные (передаем URL для использования в функции)
    product_data = extract_product_data(html_content, url)
    
    # Убеждаемся, что URL установлен
    if product_data and not product_data.get('URL'):
        product_data['URL'] = url
    
    return product_data


def remove_quotes(value):
    """Удаляет только проблемные кавычки из значения: ", ' и " """
    if value is None:
        return ''
    if isinstance(value, str):
        # Удаляем только те кавычки, которые ломают CSV: ", ' и "
        value = value.replace('"', '').replace("'", '').replace('"', '')
    return value


def clean_product_data(product_data):
    """Очищает данные товара от кавычек"""
    if not product_data:
        return product_data
    
    cleaned = {}
    for key, value in product_data.items():
        cleaned[key] = remove_quotes(value)
    return cleaned


def clean_csv_file(output_file):
    """Дополнительная очистка CSV файла от кавычек"""
    
    if not os.path.exists(output_file):
        return
    
    try:
        # Читаем файл построчно
        with open(output_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        # Очищаем каждую строку от кавычек
        cleaned_lines = []
        for line in lines:
            # Удаляем только проблемные кавычки: ", ' и "
            cleaned_line = line.replace('"', '').replace("'", '').replace('"', '')
            cleaned_lines.append(cleaned_line)
        
        # Записываем обратно
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            f.writelines(cleaned_lines)
        
        print(f"✓ Файл {output_file} очищен от кавычек")
    except Exception as e:
        print(f"Ошибка при очистке файла: {e}")


def save_to_csv(product_data_list, output_file='output.csv', append=False):
    """Сохраняет данные в CSV файл в формате TSUM"""
    
    if not product_data_list:
        print("Нет данных для сохранения")
        return
    
    # Заголовки CSV в формате TSUM
    fieldnames = [
        'URL', 'ID', 'Name', 'Brand', 'Article', 'Gender',
        'Image2', 'Ext Images', 'Description', 'Sizes', 'Color',
        'Category', 'ID2', 'Combine'
    ]
    
    # Проверяем, существует ли файл
    file_exists = os.path.exists(output_file) and append
    
    mode = 'a' if append and file_exists else 'w'
    
    with open(output_file, mode, newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';', quoting=csv.QUOTE_NONE, escapechar='\\')
        
        # Записываем заголовки только если файл новый
        if not (append and file_exists):
            writer.writeheader()
        
        # Записываем данные
        for product_data in product_data_list:
            if product_data:  # Пропускаем None значения
                # Очищаем данные от кавычек перед записью
                cleaned_data = clean_product_data(product_data)
                writer.writerow(cleaned_data)
    
    print(f"Сохранено {len([p for p in product_data_list if p])} записей в файл: {output_file}")
    
    # Дополнительная очистка файла от кавычек (на случай если они все же попали)
    clean_csv_file(output_file)


def read_links_from_file(links_file='links.txt'):
    """Читает ссылки из файла"""
    
    if not os.path.exists(links_file):
        print(f"Файл {links_file} не найден!")
        return []
    
    links = []
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                    links.append(line)
    except Exception as e:
        print(f"Ошибка чтения файла {links_file}: {e}")
        return []
    
    return links


def main():
    """Основная функция"""
    
    # Читаем ссылки из файла
    links_file = "links.txt"
    links = read_links_from_file(links_file)
    
    if not links:
        print("Не найдено ссылок для обработки!")
        return
    
    print(f"Найдено {len(links)} ссылок для обработки")
    
    output_file = "Papa_Dont_Preach_output.csv"
    all_products = []
    
    # Обрабатываем каждую ссылку
    for i, url in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Обработка: {url}")
        
        # Парсим URL
        product_data = parse_url(url)
        
        if product_data:
            # Убеждаемся, что URL установлен
            if not product_data.get('URL'):
                product_data['URL'] = url
            
            all_products.append(product_data)
            print(f"✓ Успешно обработан: {product_data.get('Name', 'N/A')}")
        else:
            print(f"✗ Не удалось обработать: {url}")
            all_products.append(None)  # Добавляем None для сохранения порядка
        
        # Небольшая задержка между запросами, чтобы не перегружать сервер
        if i < len(links):
            time.sleep(1)
    
    # Сохраняем все результаты в CSV
    if all_products:
        save_to_csv(all_products, output_file, append=False)
        print(f"\n✓ Обработка завершена! Результаты сохранены в {output_file}")
    else:
        print("\n✗ Не удалось обработать ни одной ссылки")


def clean_existing_csv(csv_file='Papa_Dont_Preach_output.csv'):
    """Очищает существующий CSV файл от кавычек"""
    if os.path.exists(csv_file):
        clean_csv_file(csv_file)
        print(f"✓ Существующий файл {csv_file} очищен от кавычек")
    else:
        print(f"Файл {csv_file} не найден")


if __name__ == '__main__':
    import sys
    
    # Если передан аргумент 'clean', очищаем существующий CSV
    if len(sys.argv) > 1 and sys.argv[1] == 'clean':
        clean_existing_csv()
    else:
        main()

