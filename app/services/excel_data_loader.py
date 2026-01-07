"""
Excel Data Loader Service.
Loads product and price data from Excel files for barcode scanning.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict
import os


class ExcelDataLoader:
    """Loads and caches data from Excel files"""

    _instance = None
    _products_df: Optional[pd.DataFrame] = None
    _prices_df: Optional[pd.DataFrame] = None
    _base_path: str = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExcelDataLoader, cls).__new__(cls)
            cls._base_path = os.path.join(os.path.dirname(__file__), "..", "..")
        return cls._instance

    def load_products(self) -> pd.DataFrame:
        """
        Load products and article codes from Excel file.

        Returns:
            DataFrame with columns: product, article codes, promoter
        """
        if self._products_df is None:
            file_path = os.path.join(self._base_path, "Products+Article codes.xlsx")
            try:
                self._products_df = pd.read_excel(file_path)
                # Clean whitespace from string columns
                for col in self._products_df.columns:
                    if self._products_df[col].dtype == 'object':
                        self._products_df[col] = self._products_df[col].str.strip()
            except FileNotFoundError:
                raise FileNotFoundError(f"Products Excel file not found at: {file_path}")
            except Exception as e:
                raise Exception(f"Error loading products Excel: {str(e)}")

        return self._products_df

    def load_prices(self) -> pd.DataFrame:
        """
        Load price consolidated data from Excel file.

        Returns:
            DataFrame with columns: pricelist, product, price
        """
        if self._prices_df is None:
            file_path = os.path.join(self._base_path, "pricelist - consolidated.xlsx")
            try:
                self._prices_df = pd.read_excel(file_path)
                # Clean whitespace from string columns
                for col in self._prices_df.columns:
                    if self._prices_df[col].dtype == 'object':
                        self._prices_df[col] = self._prices_df[col].str.strip()
            except FileNotFoundError:
                raise FileNotFoundError(f"Pricelist Excel file not found at: {file_path}")
            except Exception as e:
                raise Exception(f"Error loading pricelist Excel: {str(e)}")

        return self._prices_df

    def get_product_by_article_code(self, article_code: int) -> Optional[Dict]:
        """
        Get product information by article code.

        Args:
            article_code: The article code to search for

        Returns:
            Dictionary with product, article_codes, and promoter, or None if not found
        """
        df = self.load_products()

        # Search for article code
        result = df[df['article codes'] == article_code]

        if result.empty:
            return None

        row = result.iloc[0]
        return {
            'product': row['product'],
            'article_codes': int(row['article codes']),
            'promoter': row['promoter']
        }

    def get_price(self, product_name: str, store_name: str) -> Optional[float]:
        """
        Get price for a product at a specific store.

        Args:
            product_name: The product name to search for
            store_name: The store name to match in pricelist

        Returns:
            Price as float, or None if not found
        """
        df = self.load_prices()

        # Try exact match first
        result = df[
            (df['product'] == product_name) &
            (df['pricelist'].str.contains(store_name, case=False, na=False))
        ]

        if result.empty:
            # Try partial match on product name
            result = df[
                (df['product'].str.contains(product_name, case=False, na=False)) &
                (df['pricelist'].str.contains(store_name, case=False, na=False))
            ]

        if result.empty:
            return None

        return float(result.iloc[0]['price'])

    def reload(self):
        """Force reload of all Excel data"""
        self._products_df = None
        self._prices_df = None


# Singleton instance
excel_loader = ExcelDataLoader()
