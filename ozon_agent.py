import os
import requests
from datetime import datetime, timedelta
from telegram import Bot
import asyncio

OZON_CLIENT_ID = os.environ.get("OZON_CLIENT_ID")
OZON_API_KEY = os.environ.get("OZON_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

HEADERS = {
    "Client-Id": OZON_CLIENT_ID,
    "Api-Key": OZON_API_KEY,
    "Content-Type": "application/json"
}

THRESHOLD_FUNNEL = 0.10  # 10% порог просадки воронки
THRESHOLD_DRR = 0.02     # 2% порог роста ДРР

def get_analytics(date_from, date_to):
    """Получаем данные воронки продаж"""
    url = "https://api-seller.ozon.ru/v1/analytics/data"
    body = {
        "date_from": date_from,
        "date_to": date_to,
        "dimension": ["sku"],
        "metrics": [
            "hits_view",      # показы
            "hits_view_pdp",  # просмотры карточки
            "hits_tocart",    # добавления в корзину
            "ordered_units",  # заказы
            "delivered_units" # выкупы
        ],
        "limit": 1000
    }
    r = requests.post(url, json=body, headers=HEADERS)
    return r.json()

def get_campaigns():
    """Получаем список рекламных кампаний"""
    url = "https://api-seller.ozon.ru/v2/position/title"
    r = requests.get(url, headers=HEADERS)
    return r.json()

def get_campaign_stats(date_from, date_to):
    """Получаем статистику рекламных кампаний"""
    url = "https://api-seller.ozon.ru/v1/statistics/expenses"
    body = {
        "dateFrom": date_from,
        "dateTo": date_to
    }
    r = requests.post(url, json=body, headers=HEADERS)
    return r.json()

def calc_conversion(a, b):
    """Считаем конверсию между двумя этапами"""
    if a and a > 0:
        return b / a
    return 0

def analyze_funnel(today_data, avg_data):
    """Анализируем просадки в воронке"""
    alerts = []
    
    for item in today_data.get("result", {}).get("data", []):
        sku = item.get("dimensions", [{}])[0].get("id", "")
        name = item.get("dimensions", [{}])[0].get("name", sku)
        metrics = item.get("metrics", [0, 0, 0, 0, 0])
        
        views = metrics[0]
        pdp = metrics[1]
        cart = metrics[2]
        orders = metrics[3]
        delivered = metrics[4]
        
        # Ищем средние значения за 3 дня
        avg_item = next((x for x in avg_data.get("result", {}).get("data", [])
                        if x.get("dimensions", [{}])[0].get("id") == sku), None)
        
        if not avg_item:
            continue
            
        avg_metrics = avg_item.get("metrics", [0, 0, 0, 0, 0])
        avg_views = avg_metrics[0]
        avg_pdp = avg_metrics[1]
        avg_cart = avg_metrics[2]
        avg_orders = avg_metrics[3]
        avg_delivered = avg_metrics[4]
        
        issues = []
        
        # Проверяем абсолютные показатели
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
        
        # Проверяем конверсии
        conv_view_pdp = calc_conversion(views, pdp)
        conv_pdp_cart = calc_conversion(pdp, cart)
        conv_cart_order = calc_conversion(cart, orders)
        conv_order_delivered = calc_conversion(orders, delivered)
        
        avg_conv_view_pdp = calc_conversion(avg_views, avg_pdp)
        avg_conv_pdp_cart = calc_conversion(avg_pdp, avg_cart)
        avg_conv_cart_order = calc_conversion(avg_cart, avg_orders)
        avg_conv_order_delivered = calc_conversion(avg_orders, avg_delivered)
        
        if avg_conv_view_pdp > 0 and (avg_conv_view_pdp - conv_view_pdp) / avg_conv_view_pdp >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Конв. показы→карточка: {conv_view_pdp:.1%} vs {avg_conv_view_pdp:.1%}")
        
        if avg_conv_pdp_cart > 0 and (avg_conv_pdp_cart - conv_pdp_cart) / avg_conv_pdp_cart >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Конв. карточка→корзина: {conv_pdp_cart:.1%} vs {avg_conv_pdp_cart:.1%}")
        
        if avg_conv_cart_order > 0 and (avg_conv_cart_order - conv_cart_order) / avg_conv_cart_order >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Конв. корзина→заказ: {conv_cart_order:.1%} vs {avg_conv_cart_order:.1%}")
        
        if avg_conv_order_delivered > 0 and (avg_conv_order_delivered - conv_order_delivered) / avg_conv_order_delivered >= THRESHOLD_FUNNEL:
            issues.append(f"📉 Конв. заказ→выкуп: {conv_order_delivered:.1%} vs {avg_conv_order_delivered:.1%}")
        
        if issues:
            alerts.append({"name": name, "sku": sku, "issues": issues})
    
    return alerts

def analyze_ads(today_stats, avg_stats):
    """Анализируем рекламные кампании"""
    alerts = []
    
    for camp in today_stats.get("data", []):
        camp_id = camp.get("id")
        camp_name = camp.get("title", camp_id)
        revenue = camp.get("revenue", 0)
        expense = camp.get("expense", 0)
        
        drr = expense / revenue * 100 if revenue > 0 else 0
        
        # Ищем средние за 3 дня
        avg_camp = next((x for x in avg_stats.get("data", [])
                        if x.get("id") == camp_id), None)
        
        if not avg_camp:
            continue
        
        avg_revenue = avg_camp.get("revenue", 0)
        avg_expense = avg_camp.get("expense", 0)
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
    """Формируем утренний бриф"""
    msg = f"🌅 *УТРЕННИЙ БРИФ OZON*\n"
    msg += f"📅 {date}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Блок 1 — Воронка
    msg += "📊 *БЛОК 1: ВОРОНКА ПРОДАЖ*\n\n"
    
    if not funnel_alerts:
        msg += "✅ Все показатели в норме\n\n"
    else:
        msg += f"⚠️ Требуют внимания: {len(funnel_alerts)} товаров\n\n"
        for item in funnel_alerts:
            msg += f"🔴 *{item['name']}*\n"
            for issue in item['issues']:
                msg += f"  {issue}\n"
            msg += f"\n📋 *Что проверить:*\n"
            msg += f"  • Позиции в поиске и категории\n"
            msg += f"  • Цену vs конкуренты\n"
            msg += f"  • Фото и описание карточки\n"
            msg += f"  • Наличие отзывов\n"
            msg += f"  • Акции и скидки\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Блок 2 — Реклама
    msg += "💰 *БЛОК 2: РЕКЛАМНЫЕ КАМПАНИИ*\n\n"
    
    if not ads_alerts:
        msg += "✅ Все кампании в норме\n\n"
    else:
        msg += f"⚠️ Требуют внимания: {len(ads_alerts)} кампаний\n\n"
        for camp in ads_alerts:
            msg += f"🔴 *{camp['name']}*\n"
            msg += f"  ДРР: {camp['drr']:.1f}% vs среднее {camp['avg_drr']:.1f}% (+{camp['diff']:.1f}%)\n"
            msg += f"  Расход: {camp['expense']:,.0f}₽ | Выручка: {camp['revenue']:,.0f}₽\n"
            msg += f"\n📋 *Что проверить:*\n"
            msg += f"  • Ставки по ключевым фразам\n"
            msg += f"  • Нерелевантные ключи — отключить\n"
            msg += f"  • CTR объявлений\n"
            msg += f"  • Конверсию с рекламного трафика\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🤖 Подручный | Ozon Analytics"
    
    return msg

async def send_brief(chat_id, message):
    """Отправляем бриф в Telegram"""
    bot = Bot(token=TELEGRAM_TOKEN)
    # Разбиваем на части если сообщение длинное
    max_len = 4000
    for i in range(0, len(message), max_len):
        await bot.send_message(
            chat_id=chat_id,
            text=message[i:i+max_len],
            parse_mode="Markdown"
        )

async def run_daily_brief(chat_id):
    """Основная функция ежедневного брифа"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
