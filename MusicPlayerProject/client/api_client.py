import requests
import re

BASE_URL = "http://127.0.0.1:8000"

class ApiClient:
    def __init__(self):
        self.token = None 
        self.username = None

    def _get_headers(self, requires_auth=True):
        headers = {}
        if requires_auth and self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        return headers

    def validate_credentials(self, username, password):
        errors = []
        
        if len(username) < 6:
            errors.append("Логин должен содержать не менее 6 символов")
        
        if not re.match("^[a-zA-Z0-9_]+$", username):
            errors.append("Логин может содержать только буквы, цифры и символ подчеркивания")
        
        if len(password) < 6:
            errors.append("Пароль должен содержать не менее 6 символов")
        
        if not re.match("^[a-zA-Z0-9_]+$", password):
            errors.append("Пароль может содержать только буквы, цифры и символ подчеркивания")
        
        return errors

    def register(self, username, password):
        validation_errors = self.validate_credentials(username, password)
        if validation_errors:
            return False, "\n".join(validation_errors)

        url = f"{BASE_URL}/auth/register"
        data = {"username": username, "password": password}
        try:
            response = requests.post(url, json=data)
            if response.status_code == 200:
                return True, "Регистрация прошла успешно."
            elif response.status_code == 400:
                error_detail = response.json().get("detail", "Ошибка регистрации.")
                return False, error_detail
            else:
                return False, response.json().get("detail", "Ошибка регистрации.")
        except Exception as e:
            return False, f"Ошибка соединения: {e}"

    def login(self, username, password):
        validation_errors = self.validate_credentials(username, password)
        if validation_errors:
            return False, "\n".join(validation_errors)

        url = f"{BASE_URL}/auth/login"
        data = {"username": username, "password": password}
        try:
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data.get("access_token")
                self.username = username
                return True, "Успешный вход."
            else:
                self.token = None
                return False, "Неверный логин или пароль."
        except Exception as e:
            return False, f"Ошибка соединения: {e}"

    def logout(self):
        if self.token:
            self.log_action(action="logout", details="User logged out")
        self.token = None
        self.username = None
        return True

    def is_authenticated(self):
        return self.token is not None

    def log_action(self, action: str, details: str = None):
        if not self.is_authenticated():
            return False, "Необходимо авторизоваться для логирования."
            
        url = f"{BASE_URL}/analytics/log"
        data = {"action": action, "details": details}
        headers = self._get_headers()
        
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401:
                self.token = None 
                return False, "Сессия истекла. Пожалуйста, войдите снова."
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."

    def record_play(self, song_name: str, song_type: str):
        if not self.is_authenticated():
            return False, "Необходимо авторизоваться."
            
        url = f"{BASE_URL}/analytics/record-play"
        data = {"song_name": song_name, "song_type": song_type}
        headers = self._get_headers()
        
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401:
                self.token = None 
                return False, "Сессия истекла. Пожалуйста, войдите снова."
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."

    def add_song_to_db(self, name: str, filename: str, file_path: str, song_type: str):
        if not self.is_authenticated():
            return False, "Необходимо авторизоваться."
            
        url = f"{BASE_URL}/songs/add"
        data = {
            "name": name,
            "filename": filename,
            "file_path": file_path,
            "song_type": song_type
        }
        headers = self._get_headers()
        
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401:
                self.token = None 
                return False, "Сессия истекла. Пожалуйста, войдите снова."
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."

    def get_user_analytics(self):
        if not self.is_authenticated():
            return False, "Необходимо авторизоваться."
            
        url = f"{BASE_URL}/analytics/user"
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401:
                self.token = None 
                return False, "Сессия истекла. Пожалуйста, войдите снова."
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."

    def get_user_chat_count(self):
        if not self.is_authenticated():
            return False, "Необходимо авторизоваться."
            
        url = f"{BASE_URL}/chat/user-count"
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401:
                self.token = None 
                return False, "Сессия истекла. Пожалуйста, войдите снова."
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."

    def get_analytics(self):
        url = f"{BASE_URL}/analytics/stats"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"Ошибка сервера: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Ошибка подключения к серверу."