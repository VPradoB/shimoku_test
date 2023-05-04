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
        return self.df['producto'].unique()

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
        self.df['semana'] = self.df['fecha_factura'].dt.isocalendar().week

        weekly_sales = self.df.groupby('semana')['precio_total'].sum().reset_index()

        weekly_sales['tasa_crecimiento'] = 100 * (
                weekly_sales['precio_total'] - weekly_sales['precio_total'].shift(1)
        ) / weekly_sales['precio_total'].shift(1)

        weekly_sales['tasa_crecimiento'] = weekly_sales['tasa_crecimiento'].round(2).fillna(0)

        return weekly_sales

    def average_sale_price(self):
        sales_qt = self.df.shape[0]
        return self.df['precio_total'].sum() / sales_qt

    def sales_amount_by_weekday(self):
        return self.df['fecha_factura'].dt.day_name().value_counts(normalize=False)

    def revenue_by_product(self):
        self.df['ganancia_por_unidad'] = self.df['precio_venta'] - self.df['precio_coste']
        self.df['ganancia_total'] = self.df['ganancia_por_unidad'] * self.df['unidades_vendidas']
        ganancias_por_producto = self.df.groupby('producto')['ganancia_total'].sum()
        return ganancias_por_producto.sort_values(ascending=False)

    def net_sale_by_product(self):
        self.df['venta_neta'] = self.df['precio_venta'] - self.df['precio_coste']
        return self.df.groupby('producto')['venta_neta'].sum()

    def create_new_dashboard(self, dashboard_name):
        self.shimoku_client.plt.set_dashboard(dashboard_name)

    def report(self):
        self.create_new_dashboard(getenv('DASHBOARD_NAME'))
        self.shimoku_client.plt.table(
            title='Productos',
            data=self.stock_resume().tolist(),
            menu_path='dashboard/productos',
            order=0,
            rows_size=2, cols_size=2,
        )

        data = [{
            "color": "success",
            "variant": "outlined",
            "description": "promedio del precio de facturas",
            "title": "Promedio por venta",
            "align": "right",
            "value": round(self.average_sale_price(), 2),
        }]
        for sale_day in self.sales_amount_by_weekday().to_dict().items():
            data.append(
                {
                    "color": "default",
                    "variant": "contained",
                    "description": f"Cantidad de ventas realizadas un {sale_day[0]}",
                    "title": f"Ventas los dias {sale_day[0]}",
                    "align": "right",
                    "value": round(sale_day[1], 2),
                }
            )
        self.shimoku_client.plt.indicator(
            data=data,
            menu_path='dashboard/indicadores',
            order=0, rows_size=1, cols_size=16,
            value='value',
            header='title',
            footer='description',
            color='color',
            variant='variant',
        )

        data = []
        for key, value in self.net_sale_by_product().to_dict().items():
            data.append({'producto': key, 'venta': value})

        self.shimoku_client.plt.bar(
            data=data, order=0, menu_path='dashboard/venta_por_producto',
            x='producto', y='venta',
            rows_size=10, cols_size=2,
            padding='0,1,0,1',
            x_axis_name='Producto',
            y_axis_name='Venta (USD)',
            title='Ganancias neta por producto',
        )

        data = self.top_sold_products().rename(columns={'producto': 'name', 'unidades_vendidas': 'value'})[
            ['name', 'value']].to_dict('records')
        self.shimoku_client.plt.pie(
            title='Venta por producto',
            data=data,
            x='name', y='value',
            menu_path='dashboard/ventas',
            order=0,
            rows_size=4, cols_size=12,
        )

        data = self.revenue_percentage_by_product().rename(
            columns={'index': 'name', 'margen_beneficio': 'value'}).to_dict('records')
        self.shimoku_client.plt.ring_gauge(
            data=data,
            name='name', value='value',
            menu_path='dashboard/ganancias',
            order=0,
            rows_size=4, cols_size=12,
            title='Ganancias por producto',
        )

        data = self.weekly_sales_comparative().to_dict('records')
        self.shimoku_client.plt.line(
            data=data,
            menu_path='dashboard/crecimiento_semanal', order=0,
            x='semana', y=['tasa_crecimiento'],
            rows_size=2, cols_size=12,
        )

        data = []
        for key, value in self.revenue_by_product().to_dict().items():
            data.append({'producto': key, 'venta': value})

        self.shimoku_client.plt.bar(
            data=data, order=0, menu_path='dashboard/venta_por_producto',
            x='producto', y='venta',
            rows_size=2, cols_size=10,
            padding='0,1,0,1',
            x_axis_name='Producto',
            y_axis_name='Venta (USD)',
            title='Venta por producto',
        )


