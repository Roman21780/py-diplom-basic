import requests
import json
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from tqdm import tqdm


class VKAPIClient:

    def __init__(self, vk_token, yandex_token, google_token):
        self.vk_token = vk_token
        self.yandex_token = yandex_token
        self.google_token = google_token
        self.creds = Credentials.from_authorized_user_file('credentials.json')

    # Функция для получения фотографий из профиля ВК
    def get_vk_photos(self, user_id, album_id='profile'):
        url = 'https://api.vk.com/method/photos.get'
        params = {
            'owner_id': user_id,
            'album_id': album_id,
            'photos_sizes': '1',
            'access_token': self.vk_token,
            'v': 8.110
        }
        response = requests.get(url, params=params)
        response_data = response.json()

        if 'response' in response_data:
            return response_data['response']['items']
        else:
            raise Exception("Ошибка получения фотографий: " +
                            response_data.get('error, {}').get('error_msg', 'Unknown Error'))


    # Функция создания папки на яндекс диске
    def create_folder_on_yandex_disk(self, folder_name):
        url = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {
            'path': folder_name,
            'overwrite': 'true'
        }
        headers = {
            'Authorization': f'OAuth {self.yandex_token}'
        }
        response = requests.put(url, params=params, headers=headers)

        if response.status_code not in [201, 409]:
            raise Exception("Ошибка создания папки на Я.Диск: " + response.text)

    # Функция загрузки фотографий на яндекс диск
    def  upload_to_yandex_disk(self, file_name, image_url, folder_name):
        yandex_disk_url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        params = {
            'path': f"{folder_name}/{file_name}",
            'url': image_url,
            'overwrite': 'true'
        }
        headers = {
            'Authorization': f'OAuth {self.yandex_token}'
        }
        upload_response = requests.post(yandex_disk_url, params=params, headers=headers)

        if upload_response.status_code != 201:
            raise Exception("Ошибка загрузки на Я.Диск: " + upload_response.text)

    # Функция создания папки на google drive
    def create_folder_on_google_drive(self, folder_name):
        url = "https://www.googleapis.com/drive/v3/files"

        headers = {
            'Authorization': f'Bearer {self.google_token}',
            'Content-Type': 'application/json'
        }

        metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        response = requests.post(url, headers=headers, json=metadata)

        if response.status_code not in [200, 201]:
            raise Exception("Ошибка создания папки на Google Drive: " + response.text)

        return response.json().get('id')

    # Функция загрузки фотографий на google drive
    def upload_to_google_drive(self, file_name, url):
        if not hasattr(self, 'creds'):
            raise ValueError("Учетные данные не инициализированы. Проверьте, что creds установлены.")

        # Загрузка изображения из URL
        response = requests.get(url)
        if response.status_code == 200:
            # Сохранение изображения в локальный файл
            local_file_path = f"temp_{file_name}"
            with open(local_file_path, 'wb') as file:
                file.write(response.content)

            # Теперь загрузка на Google Drive
            service = build('drive', 'v3', credentials=self.creds)

            # Подготовка метаданных файла
            file_metadata = {
                'name': file_name,
                'mimeType': 'image/jpeg'
            }
            media = MediaFileUpload(local_file_path, mimetype='image/jpeg')

            # Выполнение загрузки файла на Google Drive
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"Файл загружен с ID: {file.get('id')}")

            # Удаление временного локального файла после загрузки
            os.remove(local_file_path)
        else:
            print(f"Ошибка при загрузке изображения: {response.status_code}")

    # Функция резервного копирования фотографий
    def backup_photos(self, user_id, album_id='profile', photo_count=5):
        photos = self.get_vk_photos(user_id, album_id)

        valid_photos = [photo for photo in photos if 'sizes' in photo and photo['sizes']]

        sorted_photos = sorted(valid_photos, key=lambda x: (max(size['width'] for size in x['sizes']),
                                                            max(size['height'] for size in x['sizes'])),
                               reverse=True)[:photo_count]

        folder_name = f"vk_photos_{user_id}"
        self.create_folder_on_google_drive(folder_name)

        uploaded_files_info = []

        for photo in tqdm(sorted_photos, desc="Загрузка фотографий на Google Drive"):
            max_size_photo = max(photo['sizes'], key=lambda x: (x['width'], x['height']))

            # Проверка наличия ключа 'likes'
            likes_count = photo.get('likes', {}).get('count',
                                                     0)  # Установка значения по умолчанию в 0, если отсутствует

            file_name = f"{likes_count}.jpg"

            # Загрузка на Google Drive
            self.upload_to_google_drive(file_name, max_size_photo['url'])

            uploaded_files_info.append({
                "file_name": file_name,
                "size": max_size_photo['type']
            })

        with open('uploaded_photos_info.json', 'w') as json_file:
            json.dump(uploaded_files_info, json_file, indent=4)

        print("Фотографии успешно загружены и информация сохранена в uploaded_photos_info.json.")


def main():
    user_id = input("Введите ID пользователя VK: ")
    album_id = input("Введите ID альбома для скачивания (по умолчанию 'profile'): ") or 'profile'
    vk_token = input("Введите токен ВК: ")
    yandex_token = input("Введите токен Яндекс.Диска: ")
    google_token = input("Введите токен Google Drive: ")
    photo_count = int(input("Введите количество фотографий для сохранения (по умолчанию 5): ") or 5)

    client = VKAPIClient(vk_token, yandex_token, google_token)
    client.backup_photos(user_id, album_id, photo_count)



if __name__ == '__main__':
    main()



