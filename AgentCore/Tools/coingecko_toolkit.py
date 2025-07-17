from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool
from typing import List

import requests

class CoinGeckoToolkit(BaseToolkit):
    def _format_dict_row_by_row(self, data: dict) -> str:
        """
        Formats a dictionary into a human-readable multi-line string.
        
        - Each top-level key-value pair is displayed on a separate line.
        - For the 'market_data' field, only the selected subfields 
        ('current_price', 'market_cap', 'total_volume') are shown.
        - Within each subfield, only values for specified currencies (e.g., 'usd', 'cny') are included.
        
        Args:
            data (dict): The input dictionary, typically containing general asset information 
                        and a nested 'market_data' field with financial metrics.
        
        Returns:
            str: A formatted string where each line represents a piece of information,
                suitable for display or logging.
        """
        lines = []
        for key, value in data.items():
            if key == 'market_data':
                lines.append("market_data:")
                # Only include selected subfields
                subfields = ['current_price', 'market_cap', 'total_volume']
                currencies = ['usd', 'cny']
                for subfield in subfields:
                    if subfield in value:
                        lines.append(f"  {subfield}:")
                        for currency in currencies:
                            currency_value = value[subfield].get(currency)
                            if currency_value is not None:
                                lines.append(f"    {currency.upper()}: {currency_value}")
                lines.append("")  # Separate market_data from other fields
            else:
                lines.append(f"{key}: {value}\n")
        
        return '\n\n'.join(lines).strip()

    def get_coin_history(self, coin_id: str, date: str, localization: str = 'false') -> str:
        """
        Fetches historical data for a specified coin on a given date using the CoinGecko API.

        Args:
            coin_id (str): The ID of the coin (e.g., 'bitcoin').
            date (str): The date for the historical data in 'dd-mm-yyyy' format.
            localization (str, optional): Whether to include localized languages in the response. Defaults to 'false'.

        Returns:
            str: Formatted string of the historical data.
        """
        url = f'https://api.coingecko.com/api/v3/coins/{coin_id}/history'
        params = {'date': date, 'localization': localization}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return self._format_dict_row_by_row(data)
        except requests.exceptions.RequestException as e:
            return f"An error occurred: {e}"
    
    def get_tools(self) -> List[FunctionTool]:
        r"""Returns a list of FunctionTool objects representing the
        functions in the toolkit.

        Returns:
            List[FunctionTool]: A list of FunctionTool objects
                representing the functions in the toolkit.
        """
        return [
            FunctionTool(self.get_coin_history),
        ]

