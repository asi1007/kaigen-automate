"""OAuth 2.0認証ヘルパー"""
import json
import logging
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)


class OAuthHelper:
    """OAuth 2.0認証を管理するヘルパークラス"""

    # Google Drive APIのスコープ
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, credentials_file: str, token_file: str, scopes: Optional[List[str]] = None):
        """OAuth認証ヘルパーを初期化する

        Args:
            credentials_file: OAuth認証情報JSONファイルのパス
            token_file: トークン保存先ファイルのパス
            scopes: 使用するスコープのリスト（デフォルトはSCOPES）
        """
        # 相対パスの場合、プロジェクトルートからのパスとして解決
        self.credentials_file = self._resolve_path(credentials_file)
        self.token_file = self._resolve_path(token_file)
        self.scopes = scopes or self.SCOPES

    def _resolve_path(self, file_path: str) -> Path:
        """ファイルパスを解決する（相対パスの場合はプロジェクトルートからのパスとして解決）

        Args:
            file_path: ファイルパス（絶対パスまたは相対パス）

        Returns:
            Path: 解決されたファイルパス
        """
        path = Path(file_path)
        
        # 絶対パスの場合はそのまま返す
        if path.is_absolute():
            return path
        
        # 相対パスの場合、プロジェクトルートからのパスとして解決
        # main.pyの場所からプロジェクトルートを取得
        project_root = Path(__file__).parent.parent.parent.parent
        resolved_path = project_root / path
        
        return resolved_path

    def get_credentials(self) -> Credentials:
        """OAuth認証情報を取得する
        
        初回認証時はブラウザで認証フローを実行し、
        トークンを保存します。次回以降は保存されたトークンを使用します。

        Returns:
            Credentials: OAuth認証情報

        Raises:
            FileNotFoundError: credentials_fileが見つからない場合
            ValueError: 認証に失敗した場合
        """
        if not self.credentials_file.exists():
            absolute_path = self.credentials_file.resolve()
            raise FileNotFoundError(
                f"OAuth認証情報ファイル（credentials.json）が見つかりません: {absolute_path}\n\n"
                f"【重要】credentials.jsonは事前に準備が必要です。\n"
                f"このファイルを準備すれば、初回実行時にブラウザが自動で開き、\n"
                f"Googleアカウントでログインするだけで認証が完了します。\n"
                f"認証後、token.jsonが自動生成され、次回以降は再認証不要です。\n\n"
                f"【OAuth認証情報の取得手順】\n"
                f"1. Google Cloud Console (https://console.cloud.google.com/) にアクセス\n"
                f"2. プロジェクトを作成または選択\n"
                f"3. Google Drive APIを有効化\n"
                f"4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuth クライアント ID」\n"
                f"5. アプリケーションの種類: 「デスクトップアプリ」を選択\n"
                f"6. 作成したOAuthクライアントIDの「ダウンロード」ボタンからJSONファイルをダウンロード\n"
                f"7. ダウンロードしたファイルを {absolute_path} に配置してください\n\n"
                f"ファイルを配置後、再度実行するとブラウザが開いて認証できます。"
            )

        creds = None

        # 保存されたトークンを読み込む
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.scopes)
                logger.debug("保存されたトークンを読み込みました")
            except Exception as e:
                logger.warning(f"トークンファイルの読み込みに失敗しました: {e}")

        # トークンが無効または存在しない場合、認証フローを実行
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # トークンをリフレッシュ
                logger.info("トークンをリフレッシュしています...")
                try:
                    creds.refresh(Request())
                    logger.info("トークンのリフレッシュが完了しました")
                except Exception as e:
                    logger.warning(f"トークンのリフレッシュに失敗しました: {e}")
                    creds = None

            if not creds:
                # 新しい認証フローを開始
                logger.info("OAuth認証フローを開始します...")
                logger.info("ブラウザが開きますので、Googleアカウントでログインしてください。")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file),
                    self.scopes
                )
                creds = flow.run_local_server(port=0)
                logger.info("認証が完了しました")

            # トークンを保存
            self._save_token(creds)
            logger.info(f"トークンを保存しました: {self.token_file}")

        return creds

    def _save_token(self, creds: Credentials) -> None:
        """トークンをファイルに保存する

        Args:
            creds: 保存する認証情報
        """
        # トークンファイルの親ディレクトリを作成
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

        # トークンをJSON形式で保存
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }

        with open(self.token_file, 'w') as token:
            json.dump(token_data, token)

