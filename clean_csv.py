#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для очистки CSV файла от проблемных кавычек"""

import os

def clean_csv_file(output_file):
    """Очищает CSV файл от проблемных кавычек: ", ' и " """
    
    if not os.path.exists(output_file):
        print(f"Файл {output_file} не найден!")
        return
    
    try:
        # Читаем файл построчно
        with open(output_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        # Очищаем каждую строку от проблемных кавычек
        cleaned_lines = []
        for line in lines:
            # Удаляем только проблемные кавычки: ", ' и "
            cleaned_line = line.replace('"', '').replace("'", '').replace('"', '')
            cleaned_lines.append(cleaned_line)
        
        # Записываем обратно
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            f.writelines(cleaned_lines)
        
        print(f"✓ Файл {output_file} очищен от проблемных кавычек")
    except Exception as e:
        print(f"Ошибка при очистке файла: {e}")

if __name__ == '__main__':
    clean_csv_file('Papa_Dont_Preach_output.csv')


