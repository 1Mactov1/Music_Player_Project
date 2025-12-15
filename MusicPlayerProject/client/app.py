import ttkbootstrap as ttb

from .api_client import ApiClient

from .ui.login_frame import LoginFrame
from .ui.main_player_frame import MainPlayerFrame
from .ui.tkinter_styles import THEME_DARK, THEME_LIGHT

class MusicPlayerApp(ttb.Window):
    def __init__(self):
        super().__init__(themename=THEME_DARK)
        self.title("Music Player - Загрузка")
        self.geometry("800x600")
        self.center_window()
        
        self.api_client = ApiClient()
        
        self.main_container = ttb.Frame(self, padding=0)
        self.main_container.pack(fill='both', expand=True)
        
        self.login_frame = LoginFrame(self.main_container, self)
        self.main_player_frame = None
        
        self.current_frame = None 
        
        self.show_login()
    
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def switch_frame(self, new_frame, geometry=None):
        if self.current_frame:
            self.current_frame.pack_forget()
            
        self.current_frame = new_frame
        new_frame.pack(fill='both', expand=True)

        if geometry:
            self.geometry(geometry)
            self.center_window()
    
    def show_login(self):
        self.api_client.token = None 
        self.api_client.username = None
        
        if self.main_player_frame:
            self.main_player_frame.destroy()
            self.main_player_frame = None
        
        self.title("Music Player - Вход")
        self.switch_frame(self.login_frame, geometry="400x350")

    def show_main_player(self):
        if self.main_player_frame:
            self.main_player_frame.destroy()
        
        self.main_player_frame = MainPlayerFrame(self.main_container, self)
        
        self.title(f"Music Player - {self.api_client.username}")
        self.switch_frame(self.main_player_frame, geometry="1200x900")
        self.main_player_frame.on_show()

    def toggle_theme(self):
        current_theme = self.style.theme.name
        
        if current_theme == THEME_DARK:
            new_theme = THEME_LIGHT
        else:
            new_theme = THEME_DARK
            
        self.style.theme_use(new_theme)
        
        if self.current_frame:
            self.current_frame.update_theme(new_theme)


if __name__ == "__main__":
    app = MusicPlayerApp()
    app.mainloop()