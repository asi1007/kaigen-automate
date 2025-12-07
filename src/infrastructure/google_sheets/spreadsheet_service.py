"""Googleスプレッドシートへの書き込みサービス"""
import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.domain.entities.import_permit import ImportPermit
from src.domain.entities.invoice import Invoice
from src.domain.repositories.spreadsheet_repository import ISpreadsheetRepository
from src.infrastructure.google_drive.oauth_helper import OAuthHelper

logger = logging.getLogger(__name__)


class GoogleSheetsService(ISpreadsheetRepository):
    """OAuth 2.0でGoogleスプレッドシートにデータを書き込むサービス"""

    # Google Sheets APIのスコープ
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets'
    ]

    def __init__(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        credentials_file: str,
        token_file: str
    ):
        """Googleスプレッドシートサービスを初期化する

        Args:
            spreadsheet_id: スプレッドシートID
            sheet_id: シートID（gid）
            credentials_file: OAuth認証情報JSONファイルのパス
            token_file: トークン保存先ファイルのパス
        """
        self.spreadsheet_id = spreadsheet_id
        self.sheet_id = sheet_id
        self.oauth_helper = OAuthHelper(credentials_file, token_file, scopes=self.SCOPES)
        self.service = None
        self.sheet_name: str | None = None
        self._authenticate()
        self._resolve_sheet_name()

    def _authenticate(self) -> None:
        """Google Sheets API をOAuth 2.0で認証する"""
        logger.info("Google Sheets API のOAuth認証を開始します...")

        try:
            creds = self.oauth_helper.get_credentials()
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("Google Sheets API の認証が完了しました")
        except Exception as e:
            logger.error(f"Google Sheets API の認証に失敗しました: {e}")
            raise

    def _resolve_sheet_name(self) -> None:
        """sheet_id からシート名を解決する"""
        if not self.service:
            raise RuntimeError("Google Sheetsサービスが初期化されていません")

        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets(properties(sheetId,title))"
            ).execute()

            sheets = spreadsheet.get("sheets", [])
            for sheet in sheets:
                properties = sheet.get("properties", {})
                if properties.get("sheetId") == self.sheet_id:
                    self.sheet_name = properties.get("title")
                    logger.info(
                        "シート名を解決しました: %s (sheet_id: %s)",
                        self.sheet_name,
                        self.sheet_id,
                    )
                    return

            raise ValueError(
                f"sheet_id {self.sheet_id} に対応するシート名を取得できませんでした"
            )
        except HttpError as error:
            logger.error(f"シート名の取得中にエラーが発生しました: {error}")
            raise

    async def write_import_permit(self, import_permit: ImportPermit) -> None:
        """輸入許可書のデータをスプレッドシートに書き込む（マネーフォワード仕訳インポート形式・27列）"""
        if not self.service:
            raise RuntimeError("Google Sheetsサービスが初期化されていません")

        logger.info(f"スプレッドシートに書き込み中: {import_permit.permit_number}")

        try:
            metadata = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A2:A",
                valueRenderOption="UNFORMATTED_VALUE"
            ).execute()
            values_in_sheet = metadata.get("values", [])
            last_transaction_no = 0
            for row in values_in_sheet:
                if row:
                    try:
                        number_value = int(row[0])
                        if number_value > last_transaction_no:
                            last_transaction_no = number_value
                    except (ValueError, TypeError):
                        continue
            transaction_no = last_transaction_no + 1

            CREDIT_ACCOUNT = "普通預金"
            CREDIT_SUB_ACCOUNT = "埼玉県信用金庫"

            date_str = import_permit.issue_date.strftime("%Y/%m/%d")
            summary_base = f"輸入許可書 {import_permit.permit_number}"
            memo_base = f"輸入許可書番号: {import_permit.permit_number}, 追跡番号: {import_permit.tracking_number}"
            importer = import_permit.importer_name

            values = []

            debit_entries: list[tuple[str, str, float, str, str]] = []

            if import_permit.customs_duty > 0:
                debit_entries.append(
                    (
                        "租税公課",
                        "",
                        float(import_permit.customs_duty),
                        f"{summary_base} 関税",
                        f"{memo_base} (関税)",
                    )
                )

            if import_permit.consumption_tax > 0:
                debit_entries.append(
                    (
                        "仮払消費税",
                        "共-輸仕-消税 7.8%",
                        float(import_permit.consumption_tax),
                        f"{summary_base} 消費税",
                        f"{memo_base} (消費税)",
                    )
                )

            if import_permit.local_consumption_tax > 0:
                debit_entries.append(
                    (
                        "仮払消費税",
                        "共-輸仕-地税 2.2%",
                        float(import_permit.local_consumption_tax),
                        f"{summary_base} 地方消費税",
                        f"{memo_base} (地方消費税)",
                    )
                )

            total_debit_amount = sum(entry[2] for entry in debit_entries)

            for idx, (account_name, tax_category, amount, summary, memo) in enumerate(debit_entries, start=1):
                current_transaction_no = transaction_no
                values.append([
                    current_transaction_no,  # 取引No
                    date_str,  # 取引日
                    account_name,  # 借方勘定科目
                    "",  # 借方補助科目
                    "",  # 借方部門
                    "",  # 借方取引先
                    tax_category,  # 借方税区分
                    "",  # 借方インボイス
                    amount,  # 借方金額(円)
                    0,  # 借方税額
                    "",  # 貸方勘定科目
                    "",  # 貸方補助科目
                    "",  # 貸方部門
                    "",  # 貸方取引先
                    "",  # 貸方税区分
                    "",  # 貸方インボイス
                    "",  # 貸方金額(円)
                    0,  # 貸方税額
                    summary,  # 摘要
                    memo,  # 仕訳メモ
                    "",  # タグ
                    "",  # MF仕訳タイプ
                    "",  # 決算整理仕訳
                    "",  # 作成日時
                    "",  # 作成者
                    "",  # 最終更新日時
                    "",  # 最終更新者
                ])

            if total_debit_amount > 0:
                values.append([
                    transaction_no,  # 取引No
                    date_str,  # 取引日
                    "",  # 借方勘定科目
                    "",  # 借方補助科目
                    "",  # 借方部門
                    "",  # 借方取引先
                    "",  # 借方税区分
                    "",  # 借方インボイス
                    "",  # 借方金額(円)
                    0,  # 借方税額
                    CREDIT_ACCOUNT,  # 貸方勘定科目
                    CREDIT_SUB_ACCOUNT,  # 貸方補助科目
                    "",  # 貸方部門
                    "",  # 貸方取引先
                    "",  # 貸方税区分
                    "",  # 貸方インボイス
                    total_debit_amount,  # 貸方金額(円)
                    0,  # 貸方税額
                    f"{summary_base} 支払",  # 摘要
                    f"{memo_base} (支払)",  # 仕訳メモ
                    "",  # タグ
                    "",  # MF仕訳タイプ
                    "",  # 決算整理仕訳
                    "",  # 作成日時
                    "",  # 作成者
                    "",  # 最終更新日時
                    "",  # 最終更新者
                ])

            if not values:
                logger.warning(f"書き込むデータがありません: {import_permit.permit_number}")
                return

            # スプレッドシートにデータを追加
            body = {
                'values': values
            }

            if not self.sheet_name:
                raise RuntimeError("シート名が解決されていません")

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A2:AA',  # 1行目はヘッダーのためA2から書き込む
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            logger.info(
                f"スプレッドシートへの書き込みが完了しました: "
                f"{import_permit.permit_number} "
                f"(更新セル数: {result.get('updates', {}).get('updatedCells', 0)}, "
                f"追加行数: {len(values)})"
            )

        except HttpError as error:
            logger.error(f"スプレッドシートへの書き込み中にエラーが発生しました: {error}")
            raise

    async def write_invoice(self, invoice: Invoice) -> None:
        """請求書のデータをスプレッドシートに書き込む（マネーフォワード仕訳インポート形式・27列）"""
        if not self.service:
            raise RuntimeError("Google Sheetsサービスが初期化されていません")

        logger.info(f"スプレッドシートに書き込み中: {invoice.invoice_number}")

        try:
            metadata = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A2:A",
                valueRenderOption="UNFORMATTED_VALUE"
            ).execute()
            values_in_sheet = metadata.get("values", [])
            last_transaction_no = 0
            for row in values_in_sheet:
                if row:
                    try:
                        number_value = int(row[0])
                        if number_value > last_transaction_no:
                            last_transaction_no = number_value
                    except (ValueError, TypeError):
                        continue
            transaction_no = last_transaction_no + 1

            CREDIT_ACCOUNT = "普通預金"
            CREDIT_SUB_ACCOUNT = "海源"

            date_str = invoice.issue_date.strftime("%Y/%m/%d")
            summary_base = f"請求書 {invoice.invoice_number}"
            memo_base = f"請求書番号: {invoice.invoice_number}, 追跡番号: {invoice.tracking_number}"

            values = []

            # 請求書の合計金額を支払手数料として借方に計上
            total_amount = float(invoice.total_amount)

            if total_amount > 0:
                # 借方行: 支払手数料
                values.append([
                    transaction_no,  # 取引No
                    date_str,  # 取引日
                    "支払手数料",  # 借方勘定科目
                    "",  # 借方補助科目
                    "",  # 借方部門
                    "",  # 借方取引先
                    "",  # 借方税区分（対象外）
                    "",  # 借方インボイス
                    total_amount,  # 借方金額(円)
                    0,  # 借方税額
                    "",  # 貸方勘定科目
                    "",  # 貸方補助科目
                    "",  # 貸方部門
                    "",  # 貸方取引先
                    "",  # 貸方税区分
                    "",  # 貸方インボイス
                    "",  # 貸方金額(円)
                    0,  # 貸方税額
                    summary_base,  # 摘要
                    memo_base,  # 仕訳メモ
                    "",  # タグ
                    "",  # MF仕訳タイプ
                    "",  # 決算整理仕訳
                    "",  # 作成日時
                    "",  # 作成者
                    "",  # 最終更新日時
                    "",  # 最終更新者
                ])

                # 貸方行: 普通預金（海源）
                values.append([
                    transaction_no,  # 取引No
                    date_str,  # 取引日
                    "",  # 借方勘定科目
                    "",  # 借方補助科目
                    "",  # 借方部門
                    "",  # 借方取引先
                    "",  # 借方税区分
                    "",  # 借方インボイス
                    "",  # 借方金額(円)
                    0,  # 借方税額
                    CREDIT_ACCOUNT,  # 貸方勘定科目
                    CREDIT_SUB_ACCOUNT,  # 貸方補助科目（海源）
                    "",  # 貸方部門
                    "",  # 貸方取引先
                    "",  # 貸方税区分
                    "",  # 貸方インボイス
                    total_amount,  # 貸方金額(円)
                    0,  # 貸方税額
                    f"{summary_base} 支払",  # 摘要
                    f"{memo_base} (支払)",  # 仕訳メモ
                    "",  # タグ
                    "",  # MF仕訳タイプ
                    "",  # 決算整理仕訳
                    "",  # 作成日時
                    "",  # 作成者
                    "",  # 最終更新日時
                    "",  # 最終更新者
                ])

            if not values:
                logger.warning(f"書き込むデータがありません: {invoice.invoice_number}")
                return

            # スプレッドシートにデータを追加
            body = {
                'values': values
            }

            if not self.sheet_name:
                raise RuntimeError("シート名が解決されていません")

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A2:AA',  # 1行目はヘッダーのためA2から書き込む
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            logger.info(
                f"スプレッドシートへの書き込みが完了しました: "
                f"{invoice.invoice_number} "
                f"(更新セル数: {result.get('updates', {}).get('updatedCells', 0)}, "
                f"追加行数: {len(values)})"
            )

        except HttpError as error:
            logger.error(f"スプレッドシートへの書き込み中にエラーが発生しました: {error}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True,
    )
    async def write_import_permit_with_retry(self, import_permit: ImportPermit) -> None:
        """リトライ機能付きで輸入許可書のデータを書き込む"""
        await self.write_import_permit(import_permit)

