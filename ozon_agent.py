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
    try:
        r = requests.post(url, json=body, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            return {"result": {"data": []}}
    except Exception:
        return {"result": {"data": []}}


def get_campaign_stats(date_from, date_to):
    url = "https://api-seller.ozon.ru/v1/analytics/data"
    body = {
        "date_from": date_from,
        "date_to": date_to,
        "dimension": ["sku"],
        "metrics": [
            "adv_sum_all",
            "revenue"
        ],
        "limit": 1000
    }
    try:
        r = requests.post(url, json=body, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            camps = []
            for item in data.get("result", {}).get("data", []):
                sku = item.get("dimensions", [{}])[0].get("id", "")
                name = item.get("dimensions", [{}])[0].get("name", sku)
                metrics = item.get("metrics", [0, 0])
                expense = metrics[0] if len(metrics) > 0 else 0
                revenue = metrics[1] if len(metrics) > 1 else 0
                camps.append({
                    "id": sku,
                    "title": name,
                    "expense": expense,
                    "revenue": revenue
                })
            return {"data": camps}
        else:
            return {"data": []}
    except Exception:
        return {"data": []}


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
            issues.append(f"Показы: {int(views)} vs среднее {int(avg_views)} ({int((avg_views-views)/avg_views*100)}% вниз)")

        if avg_pdp > 0 and (avg_pdp - pdp) / avg_pdp >= THRESHOLD_FUNNEL:
            issues.append(f"Просмотры карточки: {int(pdp)} vs {int(avg_pdp)} ({int((avg_pdp-pdp)/avg_pdp*100)}% вниз)")

        if avg_cart > 0 and (avg_cart - cart) / avg_cart >= THRESHOLD_FUNNEL:
            issues.append(f"В корзину: {int(cart)} vs {int(avg_cart)} ({int((avg_cart-cart)/avg_cart*100)}% вниз)")

        if avg_orders > 0 and (avg_orders - orders) / avg_orders >= THRESHOLD_FUNNEL:
            issues.append(f"Заказы: {int(orders)} vs {int(avg_orders)} ({int((avg_orders-orders)/avg_orders*100)}% вниз)")

        if avg_delivered > 0 and (avg_delivered - delivered) / avg_delivered >= THRESHOLD_FUNNEL:
            issues.append(f"Выкупы: {int(delivered)} vs {int(avg_delivered)} ({int((avg_delivered-delivered)/avg_delivered*100)}% вниз)")

        conv_view_pdp = calc_conversion(views, pdp)
        avg_conv_view_pdp = calc_conversion(avg_views, avg_pdp)
        if avg_conv_view_pdp > 0 and (avg_conv_view_pdp - conv_view_pdp) / avg_conv_view_pdp >= THRESHOLD_FUNNEL:
            issues.append(f"Конв. показы-карточка: {conv_view_pdp:.1%} vs {avg_conv_view_pdp:.1%}")

        conv_pdp_cart = calc_conversion(pdp, cart)
        avg_conv_pdp_cart = calc_conversion(avg_pdp, avg_cart)
        if avg_conv_pdp_cart > 0 and (avg_conv_pdp_cart - conv_pdp_cart) / avg_conv_pdp_cart >= THRESHOLD_FUNNEL:
            issues.append(f"Конв. карточка-корзина: {conv_pdp_cart:.1%} vs {avg_conv_pdp_cart:.1%}")

        conv_cart_order = calc_conversion(cart, orders)
        avg_conv_cart_order = calc_conversion(avg_cart, avg_orders)
        if avg_conv_cart_order > 0 and (avg_conv_cart_order - conv_cart_order) / avg_conv_cart_order >= THRESHOLD_FUNNEL:
            issues.append(f"Конв. корзина-заказ: {conv_cart_order:.1%} vs {avg_conv_cart_order:.1%}")

        conv_order_delivered = calc_conversion(orders, delivered)
        avg_conv_order_delivered = calc_conversion(avg_orders, avg_delivered)
        if avg_conv_order_delivered > 0 and (avg_conv_order_delivered - conv_order_delivered) / avg_conv_order_delivered >= THRESHOLD_FUNNEL:
            issues.append(f"Конв. заказ-выкуп: {conv_order_delivered:.1%} vs {avg_conv_order_delivered:.1%}")

        if issues:
            alerts.append({"name": name, "sku": sku, "issues": issues})

    return alerts


def analyze_ads(today_stats, avg_stats):
    alerts = []
    today_camps = today_stats.get("data", [])
    avg_camps = avg_stats.get("data", [])

    for camp in today_camps:
        camp_id = camp.get("id")
        camp_name = camp.get("title", str(camp_id))
        revenue = camp.get("revenue", 0) or 0
        expense = camp.get("expense", 0) or 0

        drr = expense / revenue * 100 if revenue > 0 else 0

        avg_camp = next((x for x in avg_camps if x.get("id") == camp_id), None)
        if not avg_camp:
            continue

        avg_revenue = avg_camp.get("revenue", 0) or 0
        avg_expense = avg_camp.get("expense", 0) or 0
        avg_drr = avg_expense / avg_revenue * 100 if avg_revenue > 0 else 0

        if drr - avg_drr >= THRESHOLD_DRR * 100:
            alerts.append({
                "name": camp_name,
                "id": camp_id,
                "drr": drr,
                "avg_drr": avg_drr,
                "diff": drr - avg_drr,
                "expense": expense,
                "revenue": revenue
            })

    return alerts


def format_brief(funnel_alerts, ads_alerts, date):
    msg = "УТРЕННИЙ БРИФ OZON\n"
    msg += f"Дата: {date}\n"
    msg += "=" * 30 + "\n\n"

    msg += "БЛОК 1: ВОРОНКА ПРОДАЖ\n\n"
    if not funnel_alerts:
        msg += "Все показатели в норме\n\n"
    else:
        msg += f"Требуют внимания: {len(funnel_alerts)} товаров\n\n"
        for item in funnel_alerts:
            msg += f"[!] {item['name']}\n"
            for issue in item['issues']:
                msg += f"  - {issue}\n"
            msg += "\nЧто проверить:\n"
            msg += "  - Позиции в поиске\n"
            msg += "  - Цену vs конкуренты\n"
            msg += "  - Фото и описание карточки\n"
            msg += "  - Наличие отзывов\n"
            msg += "  - Акции и скидки\n\n"

    msg += "=" * 30 + "\n\n"

    msg += "БЛОК 2: РЕКЛАМНЫЕ КАМПАНИИ\n\n"
    if not ads_alerts:
        msg += "Все кампании в норме\n\n"
    else:
        msg += f"Требуют внимания: {len(ads_alerts)} кампаний\n\n"
        for camp in ads_alerts:
            msg += f"[!] {camp['name']}\n"
            msg += f"  ДРР: {camp['drr']:.1f}% vs среднее {camp['avg_drr']:.1f}% (+{camp['diff']:.1f}%)\n"
            msg += f"  Расход: {camp['expense']:,.0f} руб | Выручка: {camp['revenue']:,.0f} руб\n"
            msg += "\nЧто проверить:\n"
            msg += "  - Ставки по ключевым фразам\n"
            msg += "  - Нерелевантные ключи\n"
            msg += "  - CTR объявлений\n\n"

    msg += "=" * 30 + "\n"
    msg += "Подручный | Ozon Analytics"

    return msg


async def send_brief(chat_id, message):
    bot = Bot(token=TELEGRAM_TOKEN)
    max_len = 4000
    for i in range(0, len(message), max_len):
        await bot.send_message(
            chat_id=chat_id,
            text=message[i:i+max_len]
        )


async def run_daily_brief(chat_id):
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    three_days_ago = today - timedelta(days=4)

    date_yesterday = yesterday.strftime("%Y-%m-%d")
    date_from_avg = three_days_ago.strftime("%Y-%m-%d")
    date_to_avg = (yesterday - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        today_funnel = get_analytics(date_yesterday, date_yesterday)
        avg_funnel = get_analytics(date_from_avg, date_to_avg)
        today_ads = get_campaign_stats(date_yesterday, date_yesterday)
        avg_ads = get_campaign_stats(date_from_avg, date_to_avg)

        funnel_alerts = analyze_funnel(today_funnel, avg_funnel)
        ads_alerts = analyze_ads(today_ads, avg_ads)

        brief = format_brief(funnel_alerts, ads_alerts, date_yesterday)
        await send_brief(chat_id, brief)

    except Exception as e:
        import traceback
        error_text = "Ошибка:\n" + str(e) + "\n\n" + traceback.format_exc()
        await send_brief(chat_id, error_text[:4000])
