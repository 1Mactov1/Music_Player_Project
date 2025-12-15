import ttkbootstrap as ttb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog, END, LEFT
from ttkbootstrap.dialogs import Messagebox
from tkinter.scrolledtext import ScrolledText
import shutil
import pygame
import threading
import json
import asyncio
import websockets
import os
import queue
import socket
from datetime import datetime

MEDIA_FOLDER = "media"
GLOBAL_FOLDER = os.path.join(MEDIA_FOLDER, "global")
PERSONAL_FOLDER = os.path.join(MEDIA_FOLDER, "personal")
CHAT_HISTORY_FILE = "chat_history.json"

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)
if not os.path.exists(GLOBAL_FOLDER):
    os.makedirs(GLOBAL_FOLDER)

class ChatClientThread(threading.Thread):
    def __init__(self, frame, url, username):
        super().__init__()
        self.frame = frame
        self.url = url
        self.username = username
        self.stop_event = threading.Event()
        self.send_queue = queue.Queue()
        self.ws = None
        self.is_async = False

    def run(self):
        try:
            import websocket
            self.is_async = False
            self._run_sync()
        except Exception:
            self.is_async = True
            asyncio.run(self._run_async())

    def _run_sync(self):
        import websocket
        import time
        
        ws = None

        try:
            ws = websocket.create_connection(self.url, timeout=5)
            self.ws = ws

            ws.settimeout(0.2)

            while not self.stop_event.is_set():
                try:
                    while True:
                        msg = self.send_queue.get_nowait()
                        ws.send(msg)
                except queue.Empty:
                    pass

                try:
                    data = ws.recv()
                    if data:
                        self.frame.after(
                            0, self.frame.receive_message_callback, data, False
                        )
                except socket.timeout:
                    continue
                except Exception as e:
                    if "timed out" in str(e):
                        time.sleep(0.1)
                        continue
                    else:
                        break

        except Exception as error:
            self.frame.after(
                0, self.frame.receive_message_callback, f"[Ошибка подключения] {error}", True
            )
        finally:
            if ws:
                try:
                    ws.close()
                except:
                    pass
            self.ws = None

    async def _run_async(self):
        try:
            async with websockets.connect(self.url) as ws:
                self.ws = ws

                while not self.stop_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.1)
                        if msg:
                            self.frame.after(
                                0, self.frame.receive_message_callback, msg, False
                            )
                    except asyncio.TimeoutError:
                        pass
                    except Exception:
                        break

                    try:
                        while True:
                            msg = self.send_queue.get_nowait()
                            await ws.send(msg)
                    except queue.Empty:
                        pass

        except Exception as error:
            self.frame.after(
                0, self.frame.receive_message_callback, f"[Ошибка чата] {error}", True
            )
        finally:
            self.ws = None

    def send_text(self, text):
        try:
            self.send_queue.put_nowait(text)
        except:
            pass

    def stop(self):
        self.stop_event.set()
        if not self.is_async and self.ws:
            try:
                self.ws.close()
            except:
                pass


class MainPlayerFrame(ttb.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.api_client = controller.api_client
        
        pygame.mixer.init()
        
        self.playlist = []
        self.current_song_index = -1
        self.is_playing = False
        self.current_song = tk.StringVar(value="Нет активной песни")
        
        self.fav_path = "favorites.json"
        self._fav_store = {}
        self.user_favorites = set()
        
        self.chat_thread = None
        self.current_playlist_type = "global"
        
        self.personal_user_folder = None
        
        self.chat_history = []
        self._load_chat_history()
        
        self._load_favorites()
        self._build_ui()
        
    def _load_chat_history(self):

        try:
            if os.path.exists(CHAT_HISTORY_FILE):
                with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.chat_history = json.load(f)
        except:
            self.chat_history = []
    
    def _save_chat_history(self):

        try:
            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.chat_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения истории чата: {e}")
    
    def _add_to_chat_history(self, message):

        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")
        
        chat_entry = {
            "date": date_str,
            "time": time_str,
            "message": message,
            "username": self.api_client.username
        }
        self.chat_history.append(chat_entry)
        self._save_chat_history()
    
    def _load_favorites(self):
        try:
            if os.path.exists(self.fav_path):
                with open(self.fav_path, "r", encoding="utf-8") as f:
                    self._fav_store = json.load(f)
        except:
            self._fav_store = {}
        
        if hasattr(self.api_client, 'username') and self.api_client.username:
            user = self.api_client.username
            self.user_favorites = set(self._fav_store.get(user, []))
        else:
            self.user_favorites = set()

    def _save_favorites(self):
        if hasattr(self.api_client, 'username') and self.api_client.username:
            user = self.api_client.username
            self._fav_store[user] = list(self.user_favorites)
            
            try:
                with open(self.fav_path, "w", encoding="utf-8") as f:
                    json.dump(self._fav_store, f, indent=2, ensure_ascii=False)
            except:
                pass

    def _build_ui(self):
        paned = ttb.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)
        
        left = ttb.Frame(paned, padding=10)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)
        paned.add(left, weight=3)
        
        self._toolbar(left)
        self._player(left)
        self._playlist_controls(left)
        self._song_list(left)
        
        right = ttb.Frame(paned, padding=10)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        paned.add(right, weight=2)
        
        self._chat(right)
    
    def _toolbar(self, parent):
        bar = ttb.Frame(parent)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ttb.Button(bar, text="🎶 Добавить", bootstyle="info",
                   command=self.add_song).pack(side=LEFT, padx=4)
        
        ttb.Button(bar, text="📊 Аналитика", bootstyle="info",
                   command=self.show_analytics).pack(side=LEFT, padx=4)
        
        ttb.Button(bar, text="🌓 Тема",
                   command=self.controller.toggle_theme).pack(side=LEFT, padx=4)
        
        ttb.Button(bar, text="🚪 Выйти", bootstyle="danger",
                   command=self.logout).pack(side=LEFT, padx=4)
    
    def _player(self, parent):
        frame = ttb.Frame(parent)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        ttb.Label(frame, textvariable=self.current_song,
                  font=("Helvetica", 12, "bold")).pack(pady=5)
        
        self.btn_play = ttb.Button(
            frame, text="▶️ Play", bootstyle="success", command=self.play_pause
        )
        self.btn_play.pack()
    
    def _playlist_controls(self, parent):
        frame = ttb.Frame(parent)
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        self.playlist_var = tk.StringVar(value="Общий плейлист")
        playlist_menu = ttb.Menubutton(
            frame, 
            textvariable=self.playlist_var,
            bootstyle="outline",
            width=15
        )
        playlist_menu.pack(side=LEFT)
        
        menu = tk.Menu(playlist_menu, tearoff=0)
        menu.add_command(label="Общий плейлист", command=lambda: self._switch_playlist("global"))
        menu.add_command(label="Личный плейлист", command=lambda: self._switch_playlist("personal"))
        playlist_menu['menu'] = menu
    
    def _song_list(self, parent):
        cont = ttb.Labelframe(parent, text="Список песен", padding=5)
        cont.grid(row=3, column=0, sticky="nsew")
        cont.columnconfigure(0, weight=1)
        cont.rowconfigure(0, weight=1)
        
        self.tree = ttb.Treeview(
            cont, columns=("fav", "del", "id", "title"), show="headings"
        )
        
        self.tree.heading("fav", text="❤")
        self.tree.heading("del", text="🗑")
        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Название")
        
        self.tree.column("fav", width=40, anchor="center", stretch=False)
        self.tree.column("del", width=40, anchor="center", stretch=False)
        self.tree.column("id", width=50, anchor="center", stretch=False)
        self.tree.column("title", width=450, anchor="w", stretch=False)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        vs = ttb.Scrollbar(cont, orient="vertical", command=self.tree.yview)
        vs.grid(row=0, column=1, sticky="ns")
        
        hs = ttb.Scrollbar(cont, orient="horizontal", command=self.tree.xview)
        hs.grid(row=1, column=0, sticky="ew")
        
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        
        self.tree.bind("<ButtonRelease-1>", self._tree_click)
        self.tree.bind("<Double-1>", self._open_song)
    
    def _chat(self, parent):
        chat_frame = ttb.Frame(parent)
        chat_frame.grid(row=0, column=0, sticky="nsew")
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(1, weight=1)
        
        title_frame = ttb.Frame(chat_frame)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttb.Label(title_frame, text="ЧАТ", font=("Helvetica", 14)).pack()
        
        chat_container = ttb.Frame(chat_frame)
        chat_container.grid(row=1, column=0, sticky="nsew")
        chat_container.columnconfigure(0, weight=1)
        chat_container.rowconfigure(0, weight=1)
        
        self.chat_display = ScrolledText(chat_container, wrap="word", height=20)
        self.chat_display.grid(row=0, column=0, sticky="nsew")
        self.chat_display.config(state="disabled")
        
        self._display_chat_history()
        
        input_frame = ttb.Frame(chat_frame)
        input_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        input_frame.columnconfigure(0, weight=1)
        
        self.chat_var = tk.StringVar()
        entry = ttb.Entry(input_frame, textvariable=self.chat_var)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        entry.bind("<Return>", lambda e: self.send_chat())
        
        ttb.Button(input_frame, text="Отправить", command=self.send_chat).grid(row=0, column=1)
    
    def _display_chat_history(self):
        self.chat_display.config(state="normal")
        self.chat_display.delete(1.0, END)
        
        for entry in self.chat_history:
            time_str = entry.get("time", "")
            message = entry.get("message", "")
            if time_str and message:
                self.chat_display.insert(END, f"[{time_str}] {message}\n")
        
        self.chat_display.config(state="disabled")
        self.chat_display.see(END)
    
    def _switch_playlist(self, playlist_type):
        self.current_playlist_type = playlist_type
        if playlist_type == "global":
            self.playlist_var.set("Общий плейлист")
        else:
            self.playlist_var.set("Личный плейлист")
        self._load_songs()
    
    def _load_songs(self):
        self.tree.delete(*self.tree.get_children())
        self.playlist = []
        
        idx = 1
        
        if self.current_playlist_type == "global":
            if os.path.exists(GLOBAL_FOLDER):
                global_files = sorted([f for f in os.listdir(GLOBAL_FOLDER) if f.endswith(".mp3")])
                for name in global_files:
                    full = os.path.join(GLOBAL_FOLDER, name)
                    self.playlist.append((name, full, "global"))
                    
                    fav_key = f"global:{name}"
                    fav = "❤" if fav_key in self.user_favorites else "♡"
                    self.tree.insert("", END, values=(fav, "🗑", idx, name))
                    idx += 1
        
        elif self.current_playlist_type == "personal":
            if self.personal_user_folder and os.path.exists(self.personal_user_folder):
                personal_files = sorted([f for f in os.listdir(self.personal_user_folder) if f.endswith(".mp3")])
                for name in personal_files:
                    full = os.path.join(self.personal_user_folder, name)
                    self.playlist.append((name, full, "personal"))
                    
                    fav_key = f"personal:{name}"
                    fav = "❤" if fav_key in self.user_favorites else "♡"
                    self.tree.insert("", END, values=(fav, "🗑", idx, name))
                    idx += 1
    
    def _tree_click(self, event):
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            return
        
        fav, delete, idx, name = self.tree.item(row, "values")
        idx = int(idx) - 1 
        
        playlist_type = self.current_playlist_type
        
        if col == "#1":
            if playlist_type == "global":
                fav_key = f"global:{name}"
            else:
                fav_key = f"personal:{name}"
            
            if fav_key in self.user_favorites:
                self.user_favorites.remove(fav_key)
                self.tree.set(row, "fav", "♡")
            else:
                self.user_favorites.add(fav_key)
                self.tree.set(row, "fav", "❤")
            
            self._save_favorites()
            return
        
        if col == "#2":
            if self.current_song_index == idx and self.is_playing:
                Messagebox.show_warning("Сначала остановите воспроизведение!", "Внимание:")
                return
            
            if playlist_type == "global":
                path = os.path.join(GLOBAL_FOLDER, name)
                for user in self._fav_store:
                    fav_key = f"global:{name}"
                    if fav_key in self._fav_store[user]:
                        self._fav_store[user].remove(fav_key)
            else:

                if self.personal_user_folder:
                    path = os.path.join(self.personal_user_folder, name)
                    fav_key = f"personal:{name}"
                    if fav_key in self.user_favorites:
                        self.user_favorites.remove(fav_key)
                else:
                    path = None
            
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    
                    if self.current_song_index == idx:
                        self.current_song_index = -1
                        self.current_song.set("Нет активной песни")
                        self.btn_play.config(text="▶️ Play", bootstyle="success")
                        self.is_playing = False
                        pygame.mixer.music.stop()
                except Exception as e:
                    Messagebox.show_error("Не удалось удалить файл! (Скорее всего файл только что воспроизводился)", f"Ошибка:")
            
            self._save_favorites()
            self._load_songs()
    
    def _open_song(self, _):
        row = self.tree.focus()
        if not row:
            return
        
        fav, delete, idx, name = self.tree.item(row, "values")
        self.play_song(int(idx) - 1)
    
    def play_song(self, index):
        if not (0 <= index < len(self.playlist)):
            return
        
        if self.is_playing:
            pygame.mixer.music.stop()
        
        self.current_song_index = index
        name, path, song_type = self.playlist[index]
        
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            
            self.is_playing = True
            self.current_song.set(name)
            self.btn_play.config(text="⏸ Pause", bootstyle="warning")
            
            threading.Thread(target=self._record_play, args=(name, song_type)).start()
        except Exception as e:
            Messagebox.show_error("Не удалось воспроизвести песню!", f"Ошибка: {str(e)}")
            self.current_song_index = -1
            self.current_song.set("Нет активной песни")
            self.btn_play.config(text="▶️ Play", bootstyle="success")
            self.is_playing = False
    
    def _record_play(self, song_name, song_type):
        success, response = self.api_client.record_play(song_name, song_type)
        if not success:
            print(f"Не удалось записать прослушивание: {response}")
    
    def play_pause(self):
        if self.current_song_index == -1:
            Messagebox.show_info("Выберите песню!", "Внимание:")
            return
        
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.btn_play.config(text="▶️ Play", bootstyle="success")
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True
            self.btn_play.config(text="⏸ Pause", bootstyle="warning")
    
    def add_song(self):
        fp = filedialog.askopenfilename(
            filetypes=[("MP3 файлы", "*.mp3"), ("Все файлы", "*.*")]
        )
        if not fp:
            return
        
        if not fp.lower().endswith('.mp3'):
            Messagebox.show_error("Можно выбрать только MP3 файлы!", "Ошибка:")
            return
        
        choice_dialog = tk.Toplevel(self)
        choice_dialog.title("Добавить песню")
        choice_dialog.geometry("300x180")
        choice_dialog.resizable(False, False)
        
        choice_dialog.update_idletasks()
        x = (choice_dialog.winfo_screenwidth() // 2) - (300 // 2)
        y = (choice_dialog.winfo_screenheight() // 2) - (180 // 2)
        choice_dialog.geometry(f'300x180+{x}+{y}')
        
        choice_var = tk.StringVar(value="")
        
        ttb.Label(choice_dialog, text="Куда добавить песню?", 
                  font=("Helvetica", 12)).pack(pady=10)
        
        button_frame = ttb.Frame(choice_dialog)
        button_frame.pack(pady=10)
        
        def set_choice(value):
            choice_var.set(value)
            choice_dialog.destroy()
        
        ttb.Button(button_frame, text="В общий", bootstyle="info",
                   command=lambda: set_choice("В общий"), width=10).pack(side=LEFT, padx=5, pady=5)
        ttb.Button(button_frame, text="В личный", bootstyle="info",
                   command=lambda: set_choice("В личный"), width=10).pack(side=LEFT, padx=5, pady=5)
        
        ttb.Button(button_frame, text="В оба", bootstyle="info",
                   command=lambda: set_choice("В оба"), width=10).pack(side=LEFT, padx=5, pady=5)
        
        cancel_button = ttb.Button(choice_dialog, text="Отмена", bootstyle="danger",
                                   command=lambda: set_choice("Отмена"))
        cancel_button.pack(pady=10)
        
        choice_dialog.transient(self)
        choice_dialog.grab_set()
        self.wait_window(choice_dialog)
        
        choice = choice_var.get()
        
        if not choice or choice == "Отмена":
            return
        
        name = os.path.basename(fp)
        songs_to_add = []
        
        if choice in ["В общий", "В оба"]:
            dest = os.path.join(GLOBAL_FOLDER, name)
            base, ext = os.path.splitext(name)
            n = 1
            while os.path.exists(dest):
                new_name = f"{base}_{n}{ext}"
                dest = os.path.join(GLOBAL_FOLDER, new_name)
                n += 1
            shutil.copy(fp, dest)
            actual_name = name if n == 1 else f"{base}_{n-1}{ext}"
            songs_to_add.append(("global", dest, actual_name))
        
        if choice in ["В личный", "В оба"]:
            if not self.personal_user_folder:
                self.personal_user_folder = os.path.join(PERSONAL_FOLDER, self.api_client.username)
            
            if not os.path.exists(self.personal_user_folder):
                os.makedirs(self.personal_user_folder)
            
            dest = os.path.join(self.personal_user_folder, name)
            base, ext = os.path.splitext(name)
            n = 1
            while os.path.exists(dest):
                new_name = f"{base}_{n}{ext}"
                dest = os.path.join(self.personal_user_folder, new_name)
                n += 1
            shutil.copy(fp, dest)
            actual_name = name if n == 1 else f"{base}_{n-1}{ext}"
            songs_to_add.append(("personal", dest, actual_name))
        
        for song_type, file_path, actual_name in songs_to_add:
            threading.Thread(
                target=self._add_song_to_db,
                args=(actual_name, actual_name, file_path, song_type)
            ).start()
        
        self._load_songs()
        
        Messagebox.show_info("Успех", f"Песня добавлена в {choice.lower()}")
    
    def _add_song_to_db(self, name, filename, file_path, song_type):
        success, response = self.api_client.add_song_to_db(name, filename, file_path, song_type)
        if not success:
            print(f"Не удалось добавить песню в БД: {response}")
    
    def start_chat(self):
        self.stop_chat()
        
        url = f"ws://127.0.0.1:8000/chat/{self.api_client.username}"
        
        self.chat_thread = ChatClientThread(
            self, url, self.api_client.username
        )
        self.chat_thread.daemon = True
        self.chat_thread.start()
    
    def stop_chat(self):
        if self.chat_thread:
            self.chat_thread.stop()
            try:
                self.chat_thread.join(timeout=0.5)
            except:
                pass
            self.chat_thread = None
    
    def send_chat(self):
        msg = self.chat_var.get().strip()
        if not msg:
            return
        
        if not self.chat_thread:
            return
        
        self.chat_thread.send_text(msg)
        
        self.chat_var.set("")
    
    def receive_message_callback(self, msg, is_error=False):

        if not msg or msg.isspace():
            return
        
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        
        if is_error:
            display_msg = f"[ОШИБКА] {msg}"
        else:
            if msg.startswith("Server:"):
                display_msg = msg
            else:
                display_msg = msg
        
        final_display_msg = f"[{time_str}] {display_msg}"
        
        self._add_to_chat_history(display_msg)
        
        self.chat_display.config(state="normal")
        self.chat_display.insert(END, f"{final_display_msg}\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see(END)
    
    def show_analytics(self):
        win = ttb.Toplevel(self)
        win.title("Аналитика пользователя")
        win.geometry("500x450")
        
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')
        
        ttb.Label(
            win, 
            text=f"Аналитика: {self.api_client.username}",
            font=("Helvetica", 14, "bold")
        ).pack(pady=10)
        
        def load_analytics():
            success, analytics_data = self.api_client.get_user_analytics()
            
            if success:
                success_chat, chat_data = self.api_client.get_user_chat_count()
                
                if success_chat:
                    analytics_data['chat_messages_count'] = chat_data.get('chat_message_count', 0)
                
                analytics_data['favorite_songs_count'] = len(self.user_favorites)
                
                global_count = 0
                personal_count = 0
                
                if os.path.exists(GLOBAL_FOLDER):
                    global_count = len([f for f in os.listdir(GLOBAL_FOLDER) if f.endswith(".mp3")])
                
                if self.personal_user_folder and os.path.exists(self.personal_user_folder):
                    personal_count = len([f for f in os.listdir(self.personal_user_folder) if f.endswith(".mp3")])
                
                analytics_data['global_songs_count'] = global_count
                analytics_data['personal_songs_count'] = personal_count
                
                win.after(0, lambda: display_analytics(analytics_data))
            else:
                win.after(0, lambda: Messagebox.show_error(f"Не удалось загрузить аналитику: {analytics_data}", "Ошибка"))
        
        def display_analytics(data):
            analytics_text = f"""
1. Количество прослушиваний: {data.get('total_plays', 0)}
2. Песен в избранном: {data.get('favorite_songs_count', 0)}
3. Песен в общем плейлисте: {data.get('global_songs_count', 0)}
4. Песен в личном плейлисте: {data.get('personal_songs_count', 0)}
5. Отправлено сообщений в чате: {data.get('chat_messages_count', 0)}
"""
            
            most_played = data.get('most_played_song')
            most_played_count = data.get('most_played_count', 0)
            
            if most_played:
                analytics_text += f"\n\nСамая прослушиваемая песня: {most_played} ({most_played_count} раз)"
            else:
                analytics_text += "\n\nСамая прослушиваемая песня: Нет данных"
            
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S")
            analytics_text += f"\n\nПоследнее обновление: {time_str}"
            
            text_widget = ScrolledText(win, wrap="word", height=18, width=50)
            text_widget.pack(padx=20, pady=10, fill="both", expand=True)
            text_widget.insert("1.0", analytics_text)
            text_widget.config(state="disabled")
            
            ttb.Button(win, text="🔄 Обновить", command=self.show_analytics, bootstyle="info").pack(pady=10)

        threading.Thread(target=load_analytics).start()
    
    def logout(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        system_msg = f"System: {self.api_client.username} вышел из чата"
        final_display_msg = f"[{time_str}] {system_msg}"
        
        self._add_to_chat_history(system_msg)
        
        self.chat_display.config(state="normal")
        self.chat_display.insert(END, f"{final_display_msg}\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see(END)
        
        self.stop_chat()
        pygame.mixer.music.stop()
        self.controller.show_login()
        
    def update_theme(self, theme_name):
        for themes in self.winfo_children():
            try:
                themes.configure(style=themes.winfo_class())
            except:
                pass
            
            for sub in themes.winfo_children():
                try:
                    sub.configure(style=sub.winfo_class())
                except:
                    pass
    
    def on_show(self):
        self.personal_user_folder = os.path.join(PERSONAL_FOLDER, self.api_client.username)
        if not os.path.exists(self.personal_user_folder):
            os.makedirs(self.personal_user_folder)
        
        
        self._load_favorites()
        self._load_songs()
        self.start_chat()