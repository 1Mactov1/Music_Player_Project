import ttkbootstrap as ttb
from tkinter import StringVar, W, E, CENTER
from ttkbootstrap.dialogs import Messagebox
import threading

class LoginFrame(ttb.Frame):
    def __init__(self, master, controller):
        super().__init__(master, padding=0)
        self.controller = controller
        self.is_login_mode = True
        
        self.username_var = StringVar()
        self.password_var = StringVar()
        
        self._create_widgets()

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        form_frame = ttb.Frame(self, padding=30, bootstyle="primary")
        form_frame.grid(row=0, column=0, sticky="nsew")
        
        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=3)

        self.title_label = ttb.Label(
            form_frame, 
            text="Вход в Музыкальный Плеер",
            font=("Helvetica", 16, "bold"),
            anchor=CENTER,
            justify=CENTER
        )
        self.title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="ew")

        ttb.Label(form_frame, text="Логин").grid(row=1, column=0, padx=10, pady=5, sticky=W)
        self.username_entry = ttb.Entry(form_frame, textvariable=self.username_var, bootstyle="primary")
        self.username_entry.grid(row=1, column=1, padx=10, pady=5, sticky=E+W)
        
        ttb.Label(form_frame, text="Пароль").grid(row=2, column=0, padx=10, pady=5, sticky=W)
        self.password_entry = ttb.Entry(form_frame, textvariable=self.password_var, show="*", bootstyle="primary")
        self.password_entry.grid(row=2, column=1, padx=10, pady=5, sticky=E+W)
        
        self.info_label = ttb.Label(
            form_frame, 
            text="Пароль/Логин должен содержат 6 символов которые могут состоять из латинских букв и/или чисел, без спец. символов",
            font=("Helvetica", 9),
            bootstyle="inverse-primary",
            anchor=CENTER,
            justify=CENTER,
            padding=(10, 8),
            relief="flat",
            wraplength=280
        )

        self.info_label.grid(row=3, column=0, columnspan=2, pady=(15, 10), padx=10, sticky="ew")
        self.info_label.grid_remove()
        
        self.action_button = ttb.Button(
            form_frame, 
            text="Войти", 
            command=self._handle_auth, 
            bootstyle="success"
        )
        self.action_button.grid(row=4, column=0, columnspan=2, pady=15, padx=10, sticky="ew")

        self.switch_button = ttb.Button(
            form_frame, 
            text="Нет аккаунта? Зарегистрироваться", 
            command=self._toggle_mode, 
            bootstyle="link"
        )
        self.switch_button.grid(row=5, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

    def _validate_fields(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            Messagebox.show_error("Сначала заполните все поля (Имя пользователя и Пароль)", "Ошибка:")
            return None, None
        return username, password

    def _handle_auth(self):
        username, password = self._validate_fields()
        if not username:
            return

        self.action_button.config(state="disabled", text="Загрузка...")
        
        if self.is_login_mode:
            thread = threading.Thread(target=self._api_login, args=(username, password))
        else:
            thread = threading.Thread(target=self._api_register, args=(username, password))
            
        thread.start()

    def _api_login(self, username, password):
        success, message = self.controller.api_client.login(username, password)
        self.after(0, lambda: self._handle_api_response(success, message))

    def _api_register(self, username, password):
        success, message = self.controller.api_client.register(username, password)
        self.after(0, lambda: self._handle_api_response(success, message))

    def _handle_api_response(self, success, message):
        self.action_button.config(state="normal", text="Войти" if self.is_login_mode else "Зарегистрироваться")
        
        if success:
            if self.is_login_mode:
                Messagebox.show_info("Вы успешно авторизовались", f"Добро пожаловать, {self.controller.api_client.username}!")
                self.controller.show_main_player()
            else:
                Messagebox.show_info("Регистрация прошла успешно", "Внимание:")
                self._toggle_mode()
        else:

            if "Логин должен содержать" in message or "Пароль должен содержать" in message:

                Messagebox.show_error("Ошибка валидации (Внимательно посмотрите правила регистрации)", f"Ошибка: \n{message}")
            elif "Данный логин уже используется" in message:

                Messagebox.show_error("Ошибка регистрации", "Данный логин уже используется.\nПожалуйста, выберите другой логин.")
            else:

                Messagebox.show_error("Данный логин уже используется", "Ошибка:")

    def _toggle_mode(self):
        self.is_login_mode = not self.is_login_mode
        self.username_var.set("")
        self.password_var.set("")
        self._update_ui_mode()

    def _update_ui_mode(self):
        if self.is_login_mode:
            self.title_label.config(text="Вход в Музыкальный Плеер")
            self.action_button.config(text="Войти", bootstyle="success")
            self.switch_button.config(text="Нет аккаунта? Зарегистрироваться")

            self.info_label.grid_remove()
        else:
            self.title_label.config(text="Создание аккаунта")
            self.action_button.config(text="Зарегистрироваться", bootstyle="warning")
            self.switch_button.config(text="Есть аккаунт? Войти")

            self.info_label.grid(row=3, column=0, columnspan=2, pady=(15, 10), padx=10, sticky="ew")