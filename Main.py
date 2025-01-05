import time
from itertools import count

import requests
import json
import os

from bs4.diagnose import profile
from tqdm import tqdm
import configparser
from pprint import pprint

config = configparser.ConfigParser()
config.read('settings.ini')
vk_token = config['Tokens']['vk_token']
yd_token = config['Tokens']['yd_token']


class VKAPIClient:

    def __init__(self, vk_token, yd_token, version='5.199'):
        self.params = {
            'access_token': vk_token,
            'v': version
        }
        self.yd_token = yd_token

    # Функция для получения фотографий из профиля ВК____________________
    def get_vk_photos(self, user_id, album_id='profile', count=5):
        url = 'https://api.vk.com/method/photos.get'
        params = {
            'owner_id': user_id,
            'count': count,
            'sizes': '1',
            'album_id': album_id,
            'extended': 1,
        }
        params.update(self.params)
        response = requests.get(url, params=params)
        data = response.json()

        # Проверяем, есть ли ошибки в ответе
        if 'error' in data:
            raise Exception(f"Ошибка получения фотографий: {data['error']['error_msg']}")

        photos = data['response']

        # Создаем список для хранения фотографий с максимальным размером
        max_size_photos = []

        for photo in photos['items']:
            # Получаем максимальный размер для каждой фотографии
            max_size = max(photo['sizes'], key=lambda x: x['height'] * x['width'])
            # Добавляем информацию о фотографии
            max_size_photos.append({
                'url': max_size['url'],  # URL фотографии
                'width': max_size['width'],  # Ширина
                'height': max_size['height'],  # Высота
                'id': photo['id'],  # ID фотографии
                'owner_id': photo['owner_id']  # ID владельца
            })

        return max_size_photos  # Возвращаем только фотографии с максимальным размером

    # Функция создания папки на яндекс диске____________________
    def create_folder_on_yandex_disk(self, folder_name):
        url = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {
            'path': folder_name,
            'overwrite': 'true'
        }
        headers = {
            'Authorization': f'OAuth {self.yd_token}'
        }
        response = requests.put(url, params=params, headers=headers)

        if response.status_code not in [201, 409]:
            raise Exception("Ошибка создания папки на Я.Диск: " + response.text)

    # Функция загрузки фотографий на яндекс диск____________________
    def upload_to_yandex_disk(self, file_name, image_url, folder_name):
        # Получаем ссылку для загрузки на Яндекс.Диск
        yandex_disk_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        headers = {
            'Authorization': f'OAuth {self.yd_token}'
        }

        # Запрос на получение URL для загрузки
        params = {
            'path': f"{folder_name}/{file_name}",
            'overwrite': 'true'
        }

        response = requests.get(yandex_disk_url, headers=headers, params=params)

        if response.status_code != 200:
            raise Exception("Ошибка получения URL для загрузки: " + response.text)

        upload_url = response.json().get('href')

        # Теперь загружаем изображение по полученному URL
        upload_response = requests.put(upload_url, data=requests.get(image_url).content)

        if upload_response.status_code != 201:
            raise Exception("Ошибка загрузки на Я.Диск: " + upload_response.text)

    # Функция резервного копирования фотографий на Яндекс Диск____________________
    def backup_photos(self, user_id, album_id='profile', photo_count=5):
        photos = self.get_vk_photos(user_id, album_id)
        if not photos:
            print(f"Нет фотографий для пользователя {user_id} в альбоме {album_id}.")
            return

        sorted_photos = sorted(
            photos,
            key=lambda x: (x.get('width', 0), x.get('height', 0)),
            reverse=True
        )[:photo_count]

        folder_name = f"vk_photos_{user_id}"

        # Создание папки на Yandex Disk
        try:
            self.create_folder_on_yandex_disk(folder_name)
            print("Папка успешно создана на Яндекс.Диске.")
        except Exception as e:
            print(e)

        uploaded_files_info = []

        # Загрузка каждой фотографии
        for photo in tqdm(sorted_photos, desc="Uploading photos"):
            file_name = f"{photo['id']}.jpg"
            try:
                self.upload_to_yandex_disk(file_name, photo['url'], folder_name)
                uploaded_files_info.append({
                    'file_name': file_name,
                    'size': photo['width'] * photo['height']  # Размер
                })
                print(f"Uploaded {file_name} successfully.")
            except Exception as e:
                print(f"Error uploading {file_name}: {e}")

        return uploaded_files_info


def main():
    user_id = input("Введите ID пользователя VK: ")
    album_id = input("Введите ID альбома для скачивания (по умолчанию 'profile'): ") or 'profile'
    photo_count = int(input("Введите количество фотографий для сохранения (по умолчанию 5): ") or 5)

    vk = VKAPIClient(vk_token, yd_token)
    pprint(vk.get_vk_photos(user_id, album_id, photo_count))
    vk.backup_photos(user_id, album_id, photo_count)


if __name__ == '__main__':
    main()