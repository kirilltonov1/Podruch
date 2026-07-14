import os
import requests
from datetime import datetime, timedelta
from telegram import Bot

OZON_CLIENT_ID = os.environ.get("OZON_CLIENT_ID")
OZON_API_KEY = os.environ.get("OZON_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

HEADERS = {
    "Client-Id": OZON_CLIENT_ID,
    "Api-Key": OZON_API_KEY,
    "Content-Type": "application/json"
}

THRESHOLD_FUNNEL = 0.10
THRESHOLD_DRR = 0.02

def get_analytics(date_from, date_to):
    url = "https://api-seller.ozon.ru/v1/analytics/data"
    body = {
        "date_from": date_from,
        "date_to": date_to,
        "dimension": ["sku"],
        "metrics": [
            "hits_view",
            "hits_view_pdp",
            "hits_tocart",
            "ordered_units",
            "delivered_units"
        ],
        "limit": 1000
    }
    r = requests.post(url, json=body, headers=HEADERS, timeout=30)
    return r.json()

def get_campaign_stats(date_from, date_to):
    url = "https://api-seller.ozon.ru/v1/statistics/expenses"
    body = {
        "dateFrom": date_from,
        "dateTo": date_to
    }
    r = requests.post(url, json=body, headers=HEADERS, timeout=30)
    return r.json()

def calc_conversion(a, b):
    if a and a > 0:
        return b / a
    return 0

def analyze_funnel(today_data, avg_data):
    alerts = []
    today_items = today_data.get("result", {}).get("data", [])
    avg_items = avg_data.get("result", {}).get("data", [])

    for item in today_items:
        sku = item.get("dimensions", [{}])[0].get("id", "")
        name = item.get("dimensions", [{}])[0].get("name", sku)
        metrics = item.get("metrics", [0, 0, 0, 0, 0])

        views = metrics[0] if len(metrics) > 0 else 0
        pdp = metrics[1] if len(metrics) > 1 else 0
        cart = metrics[2] if len(metrics) > 2 else 0
        orders = metrics[3] if len(metrics) > 3 else 0
        delivered = metrics[4] if len(metrics) > 4 else 0

        avg_item = next(
            (x for x in avg_items if x.get("dimensions", [{}])[0].get("id") == sku),
            None
        )
        if not avg_item:
            continue

        avg_metrics = avg_item.get("metrics", [0, 0, 0, 0, 0])
        avg_views = avg_metrics[0] if len(avg_metrics) > 0 else 0
        avg_pdp = avg_metrics[1] if len(avg_metrics) > 1 else 0
        avg_cart = avg_metrics[2] if len(avg_metrics) > 2 else 0
        avg_orders = avg_metrics[3] if len(avg_metrics) > 3 else 0
        avg_delivered = avg_metrics[4] if len(avg_metrics) > 4 else 0

        issues = []

        if avg_views > 0 and (avg_views - views) / avg_views >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Показы: {int(views)} vs среднее {int(avg_views)} ({int((avg_views-views)/avg_views*100)}%↓)")

        if avg_pdp > 0 and (avg_pdp - pdp) / avg_pdp >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Просмотры карточки: {int(pdp)} vs {int(avg_pdp)} ({int((avg_pdp-pdp)/avg_pdp*100)}%↓)")

        if avg_cart > 0 and (avg_cart - cart) / avg_cart >= THRESHOLD_FUNNEL:
            issues.append(f"📉 В корзину: {int(cart)} vs {int(avg_cart)} ({int((avg_cart-cart)/avg_cart*100)}%↓)")

        if avg_orders > 0 and (avg_orders - orders) / avg_orders >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Заказы: {int(orders)} vs {int(avg_orders)} ({int((avg_orders-orders)/avg_orders*100)}%↓)")

        if avg_delivered > 0 and (avg_delivered - delivered) / avg_delivered >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Выкупы: {int(delivered)} vs {int(avg_delivered)} ({int((avg_delivered-delivered)/avg_delivered*100)}%↓)")

        conv_view_pdp = calc_conversion(views, pdp)
        avg_conv_view_pdp = calc_conversion(avg_views, avg_pdp)
        if avg_conv_view_pdp > 0 and (avg_conv_view_pdp - conv_view_pdp) / avg_conv_view_pdp >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Конв. показы→карточка: {conv_view_pdp:.1%} vs {avg_conv_view_pdp:.1%}")

        conv_pdp_cart = calc_conversion(pdp, cart)
