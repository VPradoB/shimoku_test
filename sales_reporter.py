import random
import unicodedata
from os import getenv

import pandas as pd
from pandas import DataFrame


class SalesReporter:
    def __init__(self, shimoku_client, df: DataFrame):
        self.shimoku_client = shimoku_client
        self.df = df
        self.sanitize_dataframe()

    def sanitize_dataframe(self):
        """Sanitize product names to avoid duplicates."""
        self.df['producto'] = self.df['producto'].apply(
            lambda x: unicodedata.normalize('NFKD', x).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
        )
        self.df['fecha_factura'] = pd.to_datetime(self.df['fecha_factura'])

        # hay valores negativos para precio_venta y unidades_vendidas en el excel, asumo que son errores
        # se podrían filtrar usando query en vez de usar el valor absoluto
        self.df['precio_venta'] = self.df['precio_venta'].abs()
        self.df['unidades_vendidas'] = self.df['unidades_vendidas'].abs()
        self.df['precio_total'] = self.df['precio_venta'] * self.df['unidades_vendidas']

    def top_sold_products(self):
        """Una clasificación de los productos que venden mejor y peor"""
        resume = self.df.groupby('producto').agg({'unidades_vendidas': 'sum'}).reset_index()
        ordered_resume = resume.sort_values('unidades_vendidas', ascending=False)

        return ordered_resume

    def stock_resume(self):
        """Un resumen de los productos que tenemos en venta."""
        return self.df['producto'].drop_duplicates()

    def revenue_percentage_by_product(self):
        """Un análisis del porcentaje de ganancia que tenemos respecto
         al costo de cada producto."""
        products_qt = self.df['producto'].value_counts()

        df_productos = self.df.groupby('producto').agg(
            {'precio_coste': 'sum', 'precio_venta': 'sum'})
        df_productos = df_productos.merge(products_qt.rename('conteo'), left_index=True, right_index=True).reset_index()

        df_productos['precio_coste_promedio'] = df_productos['precio_coste'] / df_productos['conteo']
        df_productos['precio_venta_promedio'] = df_productos['precio_venta'] / df_productos['conteo']

        df_productos['ganancia_promedio'] = df_productos['precio_venta_promedio'] - df_productos[
            'precio_coste_promedio']
        df_productos['margen_beneficio'] = (df_productos['ganancia_promedio'] / df_productos[
            'precio_venta_promedio']) * 100

        df_productos['margen_beneficio'] = df_productos['margen_beneficio'].astype(int)

        return df_productos[['index', 'margen_beneficio']]

    def weekly_sales_comparative(self):
        """ Una comparación semanal de las ventas y cómo han evolucionado
        desde la primera factura que hicimos."""
        self.df['semana'] = self.df['fecha_factura'].dt.isocalendar().week

        weekly_sales = self.df.groupby('semana')['precio_total'].sum().reset_index()

        weekly_sales['tasa_crecimiento'] = 100 * (
                weekly_sales['precio_total'] - weekly_sales['precio_total'].shift(1)
        ) / weekly_sales['precio_total'].shift(1)

        weekly_sales['tasa_crecimiento'] = weekly_sales['tasa_crecimiento'].round(2).fillna(0)

        return weekly_sales

    def average_sale_price(self):
        """¿Cuál es el valor promedio de las compras que realizan nuestros clientes?"""
        sales_qt = self.df.shape[0]
        return self.df['precio_total'].sum() / sales_qt

    def sales_amount_by_weekday(self):
        """ ¿Qué días de la semana se realizan más ventas?"""
        return self.df['fecha_factura'].dt.day_name().value_counts(normalize=False)

    def revenue_by_product(self):
        """ ¿Cuáles son los productos que generan mayores ganancias en términos absolutos? """
        self.df['ganancia_por_unidad'] = self.df['precio_venta'] - self.df['precio_coste']
        self.df['ganancia_total'] = self.df['ganancia_por_unidad'] * self.df['unidades_vendidas']
        ganancias_por_producto = self.df.groupby('producto')['ganancia_total'].sum()
        return ganancias_por_producto.sort_values(ascending=False)

    def net_sale_by_product(self):
        """ ¿Cuál es la venta neta de cada producto? """
        self.df['venta_neta'] = self.df['precio_venta'] * self.df['unidades_vendidas']
        return self.df.groupby('producto')['venta_neta'].sum()

    def create_new_dashboard(self, dashboard_name):
        self.shimoku_client.plt.set_dashboard(dashboard_name)

    def clothes_comparative(self):
        """ Nos gustaría ver, además, toda la información que nos puedas ofrecer respecto a
piezas de ropa superior vs piezas de ropa inferior."""
        bottom_clothes = self.df[self.df['producto'].isin(['pantalon', 'falda', 'vestido'])]
        upper_clothes = self.df[~self.df['producto'].isin(['pantalon', 'falda'])]

        return [
            {
                "name": "ropa superior",
                "coste total": float(upper_clothes['precio_coste'].mean() * upper_clothes['unidades_vendidas'].sum()),
                "ventas netas": float(upper_clothes['precio_venta'].sum() * upper_clothes['unidades_vendidas'].sum()),
                "ganancias": float(upper_clothes['ganancia_total'].sum()),
                "coste promedio": float(upper_clothes['precio_coste'].mean()),
                "precio venta promedio": float(upper_clothes['precio_venta'].mean())
            },
            {
                "name": "ropa inferior",
                "coste total": float(bottom_clothes['precio_coste'].mean() * bottom_clothes['unidades_vendidas'].sum()),
                "ventas netas": float(bottom_clothes['precio_venta'].sum() * bottom_clothes['unidades_vendidas'].sum()),
                "ganancias": float(bottom_clothes['ganancia_total'].sum()),
                "coste promedio": float(bottom_clothes['precio_coste'].mean()),
                "precio venta promedio": float(bottom_clothes['precio_venta'].mean()),
            },
        ]

    def report(self):
        self.create_new_dashboard(getenv('DASHBOARD_NAME'))
        data = {'Lista productos': self.stock_resume().tolist()}
        self.shimoku_client.plt.table(
            data=data,
            menu_path='dashboard',
            order=1,
            rows_size=1, cols_size=2,

        )
        data = self.top_sold_products().rename(columns={'producto': 'name', 'unidades_vendidas': 'value'}).to_dict('records')
        self.shimoku_client.plt.rose(
            data=data,
            menu_path='dashboard',
            order=2,
            rows_size=3, cols_size=5,
        )

        data = self.revenue_percentage_by_product().rename(
            columns={'index': 'name', 'margen_beneficio': 'Porcentaje de ganancias'}).to_dict('records')
        self.shimoku_client.plt.zero_centered_barchart(
            data=data,
            x='name', y=['Porcentaje de ganancias'],
            menu_path='dashboard ',
            order=3,
            rows_size=3, cols_size=5,
            title='Ganancias por producto',
        )

        data = self.weekly_sales_comparative().to_dict('records')
        self.shimoku_client.plt.line(
            data=data,
            menu_path='dashboard', order=4,
            x='semana', y=['tasa_crecimiento'],
            rows_size=2, cols_size=12,
            title='Crecimiento de ventas semanal',
        )


        data = [{
            "color": "success",
            "variant": "outlined",
            "description": "promedio del precio de facturas",
            "title": "Promedio por venta",
            "align": "right",
            "value": round(self.average_sale_price(), 2),
        }]
        self.shimoku_client.plt.indicator(
            data=data,
            menu_path='dashboard 2',
            order=0, rows_size=1, cols_size=2,
            value='value',
            header='title',
            footer='description',
            color='color',
            variant='variant',
        )

        data = [{"productos": day[0], "ventas": day[1]} for day in self.sales_amount_by_weekday().to_dict().items()]
        self.shimoku_client.plt.bar(
            data=data, order=1,
            menu_path='dashboard 2',
            x='productos', y=['ventas'],
            rows_size=2, cols_size=5,
            title='Ventas por día de la semana',
        )

        data = [{"name": day[0], "value": day[1]} for day in self.revenue_by_product().to_dict().items()]
        self.shimoku_client.plt.rose(
            data=data,
            menu_path='dashboard 2',
            order=2,
            rows_size=3, cols_size=5,
        )

        data = []
        for key, value in self.net_sale_by_product().to_dict().items():
            data.append({'producto': key, 'venta': value})

        self.shimoku_client.plt.table(
            data=data,
            menu_path='dashboard 2',
            order=3,
            rows_size=2, cols_size=2,
        )

        data = self.clothes_comparative()
        self.shimoku_client.plt.radar(
            data=data,
            x='name', y=['coste total', 'ventas netas', 'ganancias'],
            menu_path='dashboard 2',
            order=4, rows_size=2, cols_size=5,
            title='Comparativa de ropa superior vs inferior',
        )
