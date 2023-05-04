from os import getenv

import pandas as pd
import shimoku_api_python as shimoku
from dotenv import load_dotenv

from sales_reporter import SalesReporter


def connect_shimoku():
    access_token = getenv('SHIMOKU_TOKEN')  # env var with your token
    universe_id: str = getenv('UNIVERSE_ID')  # your universe UUID
    business_id: str = getenv('BUSINESS_ID')

    try:
        return shimoku.Client(
            access_token=access_token,
            universe_id=universe_id,
            business_id=business_id,
        )
    except Exception:
        print('Error al conectar con Shimoku')
        raise Exception('Error al conectar con Shimoku')

def delete_app(shimoku, app_name:str):
    app_id = shimoku.app.get_app_by_name(business_id=shimoku.app.business_id, name=app_name)["id"]
    shimoku.app.delete_app(business_id=shimoku.app.business_id, app_id=app_id)

def run():
    df = pd.read_csv('ventas.csv')
    s = connect_shimoku()
    delete_app(s, 'dashboard')

    sales_reporter = SalesReporter(s, df)
    sales_reporter.report()


if __name__ == '__main__':
    load_dotenv()
    run()
