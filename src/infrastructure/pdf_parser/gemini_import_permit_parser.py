"""Gemini APIを使用したPDF輸入許可書パーサー"""
import json
import logging
import base64
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List

import google.generativeai as genai

from src.domain.entities.import_permit import ImportPermit
from src.domain.value_objects.import_permit_items import ImportPermitItem

logger = logging.getLogger(__name__)


class GeminiImportPermitParser:
    """Gemini APIを使用してPDF輸入許可書を解析してImportPermitエンティティに変換する"""

    def __init__(self, api_key: str):
        """Gemini APIパーサーを初期化する

        Args:
            api_key: Gemini APIキー
        """
        # APIキーをクリーニング（前後の空白や改行を削除）
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("Gemini APIキーが空です")
        
        # 無効な文字（制御文字など）が含まれていないか確認
        if any(ord(c) < 32 and c not in '\t\n\r' for c in api_key):
            raise ValueError("Gemini APIキーに無効な文字が含まれています")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    @staticmethod
    def _parse_decimal(value, field_name: str, default: str = "0") -> Decimal:
        """値をDecimalに変換する（空文字やカンマを許容）

        Args:
            value: 変換対象の値
            field_name: ログ出力用のフィールド名
            default: デフォルト値

        Returns:
            Decimal: 変換された数値

        Raises:
            ValueError: 数値に変換できない場合
        """
        if value is None:
            value = default

        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        if isinstance(value, str):
            cleaned = value.strip()
            # カンマや通貨記号を除去
            for token in [",", "¥", "円"]:
                cleaned = cleaned.replace(token, "")

            if cleaned in ("", "-", "--"):
                cleaned = default

            try:
                return Decimal(cleaned)
            except InvalidOperation as e:
                raise ValueError(f"{field_name} を数値に変換できません: {value}") from e

        raise ValueError(f"{field_name} の値が不正です: {value}")

    def parse(self, pdf_path: Path) -> ImportPermit:
        """PDF輸入許可書を解析する

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            ImportPermit: 解析された輸入許可書エンティティ

        Raises:
            ValueError: PDFの解析に失敗した場合
        """
        logger.info(f"輸入許可書PDFを解析中（Gemini API使用）: {pdf_path}")

        if not pdf_path.exists():
            raise ValueError(f"PDFファイルが存在しません: {pdf_path}")

        try:
            # PDFファイルを読み込む
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()

            # PDFをbase64エンコード
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

            # Gemini APIに送信するプロンプト
            prompt = """このPDFは輸入許可書です。以下の情報を抽出してJSON形式で返してください。

抽出する情報:
1. permit_number: 輸入許可書番号（例: YP5507887XX）
2. issue_date: 発行日（YYYY-MM-DD形式）
3. importer_name: 輸入者名
4. tracking_number: 追跡番号（例: YP5507887XX）
5. subtotal: 小計（数値のみ、カンマなし）
6. customs_duty: 関税額（数値のみ、カンマなし）
7. consumption_tax: 消費税額（数値のみ、カンマなし）
8. local_consumption_tax: 地方消費税額（数値のみ、カンマなし）
9. total_amount: 合計金額（数値のみ、カンマなし）
10. items: 輸入項目のリスト（各項目にitem_name, amount, quantity, unitを含む）

JSON形式で返してください。JSON以外のテキストは含めないでください。
例:
{
  "permit_number": "YP5507887XX",
  "issue_date": "2025-10-23",
  "importer_name": "新白岡輸入販売株式会社 和田篤様",
  "tracking_number": "YP5507887XX",
  "subtotal": 10000,
  "customs_duty": 5000,
  "consumption_tax": 1500,
  "local_consumption_tax": 150,
  "total_amount": 16650,
  "items": [
    {
      "item_name": "商品名1",
      "amount": 5000,
      "quantity": 1,
      "unit": "件"
    }
  ]
}
"""

            # Gemini APIにリクエストを送信
            logger.debug("Gemini APIにPDFを送信しています...")
            response = self.model.generate_content([
                {
                    "mime_type": "application/pdf",
                    "data": pdf_base64
                },
                prompt
            ])

            # レスポンスからテキストを取得
            response_text = response.text.strip()
            logger.debug(f"Gemini APIレスポンス: {response_text[:500]}")

            # JSONを抽出（```json で囲まれている場合がある）
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            # JSONをパース
            data = json.loads(json_text)

            # ImportPermitItemのリストを作成
            items = []
            for item_data in data.get("items", []):
                items.append(
                    ImportPermitItem(
                        item_name=str(item_data.get("item_name", "")),
                        amount=self._parse_decimal(item_data.get("amount"), "items.amount"),
                        quantity=self._parse_decimal(item_data.get("quantity"), "items.quantity", default="1"),
                        unit=str(item_data.get("unit", "件"))
                    )
                )

            # 発行日をパース
            issue_date_str = data.get("issue_date", "")
            if issue_date_str:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            else:
                raise ValueError("発行日が抽出できませんでした")

            # ImportPermitエンティティを作成
            import_permit = ImportPermit(
                permit_number=str(data.get("permit_number", "")),
                issue_date=issue_date,
                importer_name=str(data.get("importer_name", "")),
                tracking_number=str(data.get("tracking_number", "")),
                total_amount=self._parse_decimal(data.get("total_amount"), "total_amount"),
                customs_duty=self._parse_decimal(data.get("customs_duty"), "customs_duty"),
                consumption_tax=self._parse_decimal(data.get("consumption_tax"), "consumption_tax"),
                local_consumption_tax=self._parse_decimal(data.get("local_consumption_tax"), "local_consumption_tax"),
                subtotal=self._parse_decimal(data.get("subtotal"), "subtotal"),
                items=items,
                pdf_path=pdf_path,
            )

            logger.info(f"輸入許可書の解析が完了しました: {import_permit.permit_number}")
            return import_permit

        except json.JSONDecodeError as e:
            logger.error(f"JSONのパースに失敗しました: {e}")
            logger.error(f"レスポンステキスト: {response_text[:1000] if 'response_text' in locals() else 'N/A'}")
            raise ValueError(f"輸入許可書の解析に失敗しました: JSONのパースエラー - {e}") from e
        except Exception as e:
            logger.error(f"輸入許可書の解析中にエラーが発生しました: {e}")
            raise ValueError(f"輸入許可書の解析に失敗しました: {e}") from e

