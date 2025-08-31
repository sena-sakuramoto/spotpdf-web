import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
import sys
import subprocess
import json
from pathlib import Path
from PIL import Image, ImageTk
from pixel_diff_detector import PixelDiffDetector

# --- 追加されたインポート --- #
from datetime import datetime, date
import webbrowser

import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
import webbrowser
import socket
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import threading
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- 追加された定数 --- #
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
# CONFIG_FILE はこのスクリプトからの相対パスで指定
CONFIG_FILE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / "GoogleLoginLauncher" / "SpotPDFLauncher.config.json"
TOKEN_FILE = Path(os.getenv("APPDATA")) / "SpotPDF" / "Auth" / "token.json"
CREDENTIALS_FILE = Path(os.getenv("APPDATA")) / "SpotPDF" / "Auth" / "client_secret.json"

# --- 追加された関数 --- #
def load_config():
    """Loads configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_keys = ["GoogleClientId", "GoogleClientSecret", "ServiceAccountKeyPath", "SpreadsheetUrl"]
        for key in required_keys:
            if not config.get(key):
                messagebox.showerror("設定エラー", f"設定ファイルに '{key}' が見つかりません。")
                return None

        # ServiceAccountKeyPath はこのスクリプトからの相対パスで解決
        config["ServiceAccountKeyPath"] = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / config["ServiceAccountKeyPath"]
        if not config["ServiceAccountKeyPath"].exists():
            messagebox.showerror("設定エラー", f"サービスアカウントキーファイルが見つかりません: {config["ServiceAccountKeyPath"]}")
            return None

        return config
    except FileNotFoundError:
        messagebox.showerror("設定エラー", f"設定ファイルが見つかりません: {CONFIG_FILE}")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("設定エラー", f"設定ファイル '{CONFIG_FILE}' のJSON形式が不正です。")
        return None

def get_authorized_users(config):
    """Fetches the list of authorized users from the Google Sheet."""
    try:
        sa_creds = ServiceAccountCredentials.from_service_account_file(
            config["ServiceAccountKeyPath"],
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        client = gspread.authorize(sa_creds)
        spreadsheet = client.open_by_url(config["SpreadsheetUrl"])
        # シート名を優先（env SHEET_NAME または config["SheetName"]、既定は 'auth'）
        sheet_name = os.getenv("SHEET_NAME") or config.get("SheetName") or "auth"
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            worksheet = spreadsheet.sheet1
        records = worksheet.get_all_records()
        
        authorized_users = {}
        for record in records:
            email = record.get('email')
            exp_date_str = record.get('expiration_date')
            if email and exp_date_str:
                try:
                    exp_date = datetime.strptime(str(exp_date_str), "%Y-%m-%d").date()
                    authorized_users[email.lower()] = exp_date
                except ValueError:
                    print(f"Warning: Skipping user '{email}' due to invalid date format '{exp_date_str}'. Please use YYYY-MM-DD.", file=sys.stderr)
        return authorized_users
    except gspread.exceptions.SpreadsheetNotFound:
        messagebox.showerror("アクセスエラー", "スプレッドシートが見つかりません。URLまたは共有設定を確認してください。")
        return None
    except Exception as e:
        messagebox.showerror("アクセスエラー", f"スプレッドシートへのアクセス中にエラーが発生しました: {e}")
        return None

def get_user_credentials(config):
    """Gets user credentials, refreshing or starting a new flow as needed."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    creds = None
    if TOKEN_FILE.exists():
        creds = UserCredentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}", file=sys.stderr)
                TOKEN_FILE.unlink()
                creds = None 
        
        if not creds:
            client_secrets = {
                "installed": {
                    "client_id": config["GoogleClientId"],
                    "client_secret": config["GoogleClientSecret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            }
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(client_secrets, f)

            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            
            # シンプルな日本語メッセージ
            success_message = """✅ 認証が完了しました！

SpotPDFの認証が正常に完了しました。
アプリケーションに戻って作業を続けてください。

このタブを閉じてください。"""
            
            creds = flow.run_local_server(port=0, open_browser=True, success_message=success_message)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()

    return creds


class PDFDiffApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.app_name = "SpotPDF"
        self.config_dir = Path(os.getenv('APPDATA', os.path.expanduser("~"))) / self.app_name
        self.config_file = self.config_dir / "config.json"

        self.title(self.app_name)
        # ログエリアを広げるため、全体の高さを増やす
        self.geometry("700x680")

        # アイコンを設定（PyInstaller実行時とソースコード実行時で対応）
        try:
            # PyInstaller実行時は_MEIPASSからアイコンを読み込み
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, "SpotPDF_icon.ico")
            else:
                # ソースコード実行時
                icon_path = os.path.join(os.path.dirname(__file__), "SpotPDF_icon.ico")
            
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                print(f"アイコンファイルが見つかりません: {icon_path}")
        except (tk.TclError, Exception) as e:
            print(f"アイコン設定エラー: {e}")

        style = ttk.Style(self)
        style.configure('TButton', font=('Yu Gothic UI', 10))
        style.configure('TLabel', font=('Yu Gothic UI', 10))
        style.configure('TEntry', font=('Yu Gothic UI', 10))
        style.configure('TLabelframe.Label', font=('Yu Gothic UI', 10, 'bold'))
        style.configure('Desc.TLabel', font=('Yu Gothic UI', 8))

        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        try:
            # ロゴ画像のパスを設定（PyInstaller対応）
            if hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "SpotPDF logo.png")
            else:
                logo_path = os.path.join(os.path.dirname(__file__), "SpotPDF logo.png")
            
            if os.path.exists(logo_path):
                original_logo = Image.open(logo_path)
                width, height = original_logo.size
                new_height = 64
                new_width = int(new_height * (width / height))
                resized_logo = original_logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(resized_logo)
                logo_label = ttk.Label(main_frame, image=self.logo_image)
                logo_label.pack(pady=(0, 10))
            else:
                print(f"ロゴファイルが見つかりません: {logo_path}")
        except Exception as e: 
            print(f"ロゴの読み込みエラー: {e}")

        description_label = ttk.Label(main_frame, text="2つのPDFファイルを選択して、ピクセルレベルの差分を検出します。")
        description_label.pack(pady=(5, 15))

        selection_frame = ttk.LabelFrame(main_frame, text="PDFファイル選択", padding="15")
        selection_frame.pack(fill=tk.X, pady=5)
        selection_frame.columnconfigure(1, weight=1)

        self.old_pdf_path = tk.StringVar()
        self.new_pdf_path = tk.StringVar()
        ttk.Label(selection_frame, text="旧版PDF:").grid(row=0, column=0, padx=(0, 10), pady=5, sticky=tk.W)
        ttk.Entry(selection_frame, textvariable=self.old_pdf_path).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(selection_frame, text="参照...", command=lambda: self.select_file(self.old_pdf_path, self.new_pdf_path)).grid(row=0, column=2, padx=(5, 0))
        ttk.Label(selection_frame, text="新版PDF:").grid(row=1, column=0, padx=(0, 10), pady=5, sticky=tk.W)
        ttk.Entry(selection_frame, textvariable=self.new_pdf_path).grid(row=1, column=1, sticky=tk.EW)
        ttk.Button(selection_frame, text="参照...", command=lambda: self.select_file(self.new_pdf_path, self.old_pdf_path)).grid(row=1, column=2, padx=(5, 0))

        settings_frame = ttk.LabelFrame(main_frame, text="詳細設定", padding="15")
        settings_frame.pack(fill=tk.X, pady=10)
        settings_frame.columnconfigure(1, weight=1)

        self.show_added = tk.BooleanVar(value=True)
        self.show_removed = tk.BooleanVar(value=True)
        ttk.Label(settings_frame, text="表示する差分:").grid(row=0, column=0, sticky=tk.W, padx=(0,10))
        filter_frame = ttk.Frame(settings_frame)
        filter_frame.grid(row=0, column=1, sticky=tk.W)
        ttk.Checkbutton(filter_frame, text="追加 (緑)", variable=self.show_added).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(filter_frame, text="削除 (赤)", variable=self.show_removed).pack(side=tk.LEFT, padx=5)

        self.sensitivity = tk.IntVar(value=10)
        ttk.Label(settings_frame, text="検出感度:").grid(row=1, column=0, sticky=tk.W, padx=(0,10), pady=5)
        sensitivity_frame = ttk.Frame(settings_frame)
        sensitivity_frame.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)
        ttk.Scale(sensitivity_frame, from_=1, to=50, orient=tk.HORIZONTAL, variable=self.sensitivity, command=lambda s: self.sensitivity_val_label.config(text=f"{int(float(s))}")).pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.sensitivity_val_label = ttk.Label(sensitivity_frame, text="10", width=3)
        self.sensitivity_val_label.pack(side=tk.LEFT, padx=(10,0))
        ttk.Label(settings_frame, text="(数値が小さいほど高精度で、細かい差を検出します)", style="Desc.TLabel").grid(row=2, column=1, sticky=tk.W, padx=5, pady=(0, 5))

        self.export_all_patterns = tk.BooleanVar(value=False)
        ttk.Label(settings_frame, text="出力オプション:").grid(row=3, column=0, sticky=tk.W, padx=(0,10), pady=5)
        ttk.Checkbutton(settings_frame, text="全パターンを個別に出力する (both, added, removed)", variable=self.export_all_patterns).grid(row=3, column=1, sticky=tk.W, padx=5)

        self.run_button = ttk.Button(main_frame, text="差分検出実行", command=self.run_diff_check, style='Accent.TButton')
        self.run_button.pack(pady=15, ipady=5)
        style.configure('Accent.TButton', font=('Yu Gothic UI', 12, 'bold'))

        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=5)
        output_frame.columnconfigure(1, weight=1)
        self.output_dir = tk.StringVar(value=os.path.join(os.getcwd(), "SpotPDF_Output"))
        ttk.Label(output_frame, text="出力先:").grid(row=0, column=0, padx=(0, 10))
        ttk.Entry(output_frame, textvariable=self.output_dir, state="readonly").grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(output_frame, text="フォルダ変更", command=self.change_output_dir).grid(row=0, column=2, padx=(5, 0))

        status_frame = ttk.LabelFrame(main_frame, text="処理ログ", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        # ログエリアの高さを修正
        self.log_text = tk.Text(status_frame, height=10, state="disabled", wrap=tk.WORD, font=("Yu Gothic UI", 9), relief=tk.FLAT, bg=self.cget('bg'))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.old_pdf_path.set(config.get("old_pdf_path", ""))
                    self.new_pdf_path.set(config.get("new_pdf_path", ""))
                    self.output_dir.set(config.get("output_dir", os.path.join(os.getcwd(), "SpotPDF_Output")))
                    self.show_added.set(config.get("show_added", True))
                    self.show_removed.set(config.get("show_removed", True))
                    self.sensitivity.set(config.get("sensitivity", 10))
                    self.export_all_patterns.set(config.get("export_all_patterns", False))
                    self.sensitivity_val_label.config(text=str(self.sensitivity.get()))
        except Exception as e: print(f"設定ファイルの読み込みに失敗: {e}")

    def save_settings(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "old_pdf_path": self.old_pdf_path.get(), "new_pdf_path": self.new_pdf_path.get(),
                "output_dir": self.output_dir.get(), "show_added": self.show_added.get(),
                "show_removed": self.show_removed.get(), "sensitivity": self.sensitivity.get(),
                "export_all_patterns": self.export_all_patterns.get()
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e: print(f"設定ファイルの保存に失敗: {e}")

    def on_closing(self):
        self.save_settings(); self.destroy()

    def select_file(self, path_var_to_set, other_path_var):
        initial_dir = os.getcwd()
        if other_path_var.get() and Path(other_path_var.get()).exists(): initial_dir = Path(other_path_var.get()).parent
        elif path_var_to_set.get() and Path(path_var_to_set.get()).exists(): initial_dir = Path(path_var_to_set.get()).parent
        file_path = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDFファイル", "*.pdf")], initialdir=initial_dir)
        if file_path: path_var_to_set.set(file_path)

    def change_output_dir(self):
        dir_path = filedialog.askdirectory(title="出力先フォルダを選択", initialdir=self.output_dir.get())
        if dir_path: self.output_dir.set(dir_path)

    def open_output_folder(self, path):
        if sys.platform == "win32": os.startfile(os.path.realpath(path))
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def log(self, message): self.after(0, self._log_update, message)

    def _log_update(self, message):
        self.log_text.config(state="normal"); self.log_text.insert(tk.END, str(message) + "\n"); self.log_text.see(tk.END); self.log_text.config(state="disabled")

    def run_diff_check(self):
        old_pdf, new_pdf, output_dir = self.old_pdf_path.get(), self.new_pdf_path.get(), self.output_dir.get()
        if not all([old_pdf, new_pdf]):
            messagebox.showerror("エラー", "旧版と新版の両方のPDFファイルを選択してください。"); return

        settings = {
            "sensitivity": self.sensitivity.get(),
            "display_filter": {"added": self.show_added.get(), "removed": self.show_removed.get()},
            "export_all_patterns": self.export_all_patterns.get()
        }

        self.run_button.config(state="disabled"); self.log_text.config(state="normal"); self.log_text.delete('1.0', tk.END); self.log_text.config(state="disabled")
        threading.Thread(target=self.run_backend_process, args=(old_pdf, new_pdf, output_dir, settings), daemon=True).start()

    def run_backend_process(self, old_pdf, new_pdf, output_dir, settings):
        try:
            detector = PixelDiffDetector()
            results = detector.create_pixel_diff_output(old_pdf_path=old_pdf, new_pdf_path=new_pdf, output_dir=output_dir, progress_callback=self.log, settings=settings)
            final_output_path = results.get("output_path", output_dir)
            self.log("✓✓✓ 処理が正常に完了しました。✓✓✓")
            message = f"処理が完了しました。\n出力先: {final_output_path}"
            self.after(0, lambda: messagebox.showinfo("完了", message))
            self.after(0, self.open_output_folder, final_output_path)
        except Exception as e:
            self.log(f"エラーが発生しました: {e}")
            message = f"処理中にエラーが発生しました。\n詳細はログを確認してください。\n\n{e}"
            self.after(0, lambda: messagebox.showerror("エラー", message))
        finally:
            self.after(0, lambda: self.run_button.config(state="normal"))

if __name__ == "__main__":
    # --- 認証ロジックの追加 --- #
    config = load_config()
    if not config:
        sys.exit(1)

    authorized_users = get_authorized_users(config)
    if authorized_users is None: # Error message already printed
        sys.exit(1)

    try:
        creds = get_user_credentials(config)
        if not creds:
            messagebox.showerror("認証エラー", "Google認証情報を取得できませんでした。")
            sys.exit(2)

        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()

        email = user_info.get('email')
        name = user_info.get('name', email)

        if not email or not user_info.get('verified_email'):
            messagebox.showerror("認証エラー", "メールアドレスが利用できないか、確認されていません。")
            sys.exit(3)

        user_email_lower = email.lower()
        if user_email_lower not in authorized_users:
            messagebox.showerror("アクセス拒否", f"ユーザー '{email}' は許可リストにありません。")
            sys.exit(4)
        
        expiration_date = authorized_users[user_email_lower]
        if expiration_date < date.today():
            messagebox.showerror("アクセス拒否", f"ユーザー '{email}' のデモ期間は {expiration_date} に終了しました。")
            sys.exit(4)

        # --- 認証成功後、アプリケーションを起動 --- #
        app = PDFDiffApp()
        
        # ウィンドウを前面に表示してフォーカスを当てる
        app.lift()
        app.attributes('-topmost', True)
        app.after(100, lambda: app.attributes('-topmost', False))
        app.focus_force()
        
        # システム通知音を鳴らす（オプション）
        try:
            import winsound
            winsound.MessageBeep(0)  # 0 = デフォルトシステム音
        except (ImportError, AttributeError):
            pass
        
        app.mainloop()

    except HttpError as error:
        messagebox.showerror("APIエラー", f"Google APIエラーが発生しました: {error}")
        sys.exit(5)
    except Exception as e:
        messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {e}")
        sys.exit(1)
