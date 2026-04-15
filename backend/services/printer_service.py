import os
import subprocess
from typing import Optional, Dict, Any
from datetime import datetime

from config import settings

class PrinterService:
    """Printer xizmati - cheklar va oshxona buyurtmalarini chop etish"""
    
    @staticmethod
    def is_available() -> bool:
        """Printer mavjudligini tekshirish"""
        return settings.PRINTER_ENABLED
    
    @staticmethod
    def print_kitchen_receipt(order) -> bool:
        """Oshxona uchun buyurtma chekini chop etish"""
        if not settings.PRINTER_ENABLED:
            print("[PRINTER] Printer o'chirilgan")
            return False
        
        try:
            receipt_content = PrinterService._generate_kitchen_receipt(order)
            return PrinterService._send_to_printer(receipt_content, "kitchen")
        except Exception as e:
            print(f"[PRINTER] Xatolik: {e}")
            return False
    
    @staticmethod
    def print_customer_receipt(order, payment) -> bool:
        """Mijoz uchun chek chop etish"""
        if not settings.PRINTER_ENABLED:
            print("[PRINTER] Printer o'chirilgan")
            return False
        
        try:
            receipt_content = PrinterService._generate_customer_receipt(order, payment)
            return PrinterService._send_to_printer(receipt_content, "receipt")
        except Exception as e:
            print(f"[PRINTER] Xatolik: {e}")
            return False
    
    @staticmethod
    def print_report(report_data: Dict[str, Any], report_type: str) -> bool:
        """Hisobotni chop etish"""
        if not settings.PRINTER_ENABLED:
            return False
        
        try:
            content = PrinterService._generate_report(report_data, report_type)
            return PrinterService._send_to_printer(content, "report")
        except Exception as e:
            print(f"[PRINTER] Xatolik: {e}")
            return False
    
    @staticmethod
    def _generate_kitchen_receipt(order) -> str:
        """Oshxona cheki mazmunini yaratish"""
        lines = []
        
        # Sarlavha
        lines.append("\n" + "=" * 40)
        lines.append("OSHXONA BUYURTMASI".center(40))
        lines.append("=" * 40)
        
        # Buyurtma ma'lumotlari
        lines.append(f"Buyurtma: #{order.order_number}")
        lines.append(f"Stol: {order.table.number if order.table else 'Olib ketish'}")
        lines.append(f"Ofitsiant: {order.waiter.full_name if order.waiter else '-'}")
        lines.append(f"Vaqt: {order.created_at.strftime('%H:%M:%S')}")
        lines.append("-" * 40)
        
        # Mahsulotlar
        for item in order.items:
            product_name = item.product.name[:30]
            quantity = item.quantity
            notes = f" ({item.notes})" if item.notes else ""
            lines.append(f"{quantity} x {product_name}{notes}")
        
        lines.append("-" * 40)
        
        # Izoh
        if order.notes:
            lines.append(f"IZOH: {order.notes}")
            lines.append("-" * 40)
        
        # Footer
        lines.append("Tayyorlash muddati: 15-20 daqiqa".center(40))
        lines.append("=" * 40)
        lines.append("\n\n\n")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_customer_receipt(order, payment) -> str:
        """Mijoz cheki mazmunini yaratish"""
        lines = []
        
        # Sarlavha
        lines.append("\n" + "=" * 40)
        lines.append("PREMIUM RESTAURANT".center(40))
        lines.append("Sizning tanlovingiz biz uchun muhim!".center(40))
        lines.append("=" * 40)
        
        # Ma'lumotlar
        lines.append(f"Chek: #{order.order_number}")
        lines.append(f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append(f"Stol: {order.table.number if order.table else '-'}")
        lines.append(f"Ofitsiant: {order.waiter.full_name if order.waiter else '-'}")
        lines.append("-" * 40)
        
        # Mahsulotlar
        lines.append("Mahsulot".ljust(25) + "Soni".rjust(5) + "Summa".rjust(10))
        lines.append("-" * 40)
        
        for item in order.items:
            name = item.product.name[:23]
            qty = str(item.quantity)
            price = f"{item.total_price:,.0f}".replace(",", " ")
            lines.append(f"{name.ljust(25)}{qty.rjust(5)}{price.rjust(10)}")
        
        lines.append("-" * 40)
        
        # Jami
        lines.append(f"Jami:".ljust(30) + f"{order.total_amount:,.0f}".replace(",", " ").rjust(10))
        
        if order.discount_amount:
            lines.append(f"Chegirma:".ljust(30) + f"-{order.discount_amount:,.0f}".replace(",", " ").rjust(10))
        
        lines.append(f"Umumiy:".ljust(30) + f"{order.final_amount:,.0f}".replace(",", " ").rjust(10))
        lines.append("=" * 40)
        
        # To'lov
        payment_methods = {
            "cash": "Naqd",
            "card": "Karta",
            "click": "Click",
            "payme": "Payme"
        }
        lines.append(f"To'lov: {payment_methods.get(payment.method, payment.method)}")
        
        if payment.method == "cash" and hasattr(payment, 'cash_received'):
            change = payment.cash_received - payment.amount
            lines.append(f"Qabul qilindi: {payment.cash_received:,.0f}".replace(",", " "))
            lines.append(f"Qaytim: {change:,.0f}".replace(",", " "))
        
        lines.append("=" * 40)
        lines.append("Xaridingiz uchun rahmat!".center(40))
        lines.append("Yana tashrif buyurishingizni kutamiz!".center(40))
        lines.append("=" * 40)
        lines.append("\n\n\n")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_report(report_data: Dict[str, Any], report_type: str) -> str:
        """Hisobot mazmunini yaratish"""
        lines = []
        
        lines.append("\n" + "=" * 40)
        lines.append(f"{report_type.upper()} HISOBOTI".center(40))
        lines.append("=" * 40)
        lines.append(f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("-" * 40)
        
        if report_type == "daily":
            lines.append(f"Kunlik savdo: {report_data.get('total_sales', 0):,.0f} UZS".replace(",", " "))
            lines.append(f"Buyurtmalar soni: {report_data.get('orders_count', 0)}")
            lines.append(f"O'rtacha chek: {report_data.get('avg_check', 0):,.0f} UZS".replace(",", " "))
        elif report_type == "shift":
            lines.append(f"Smena ochilgan: {report_data.get('start_time', '-')}")
            lines.append(f"Smena yopilgan: {report_data.get('end_time', '-')}")
            lines.append(f"Naqd savdo: {report_data.get('cash_sales', 0):,.0f} UZS".replace(",", " "))
            lines.append(f"Karta savdo: {report_data.get('card_sales', 0):,.0f} UZS".replace(",", " "))
        
        lines.append("=" * 40)
        lines.append("\n\n\n")
        
        return "\n".join(lines)
    
    @staticmethod
    def _send_to_printer(content: str, printer_type: str = "receipt") -> bool:
        """Printerga yuborish"""
        try:
            # ESC/POS formatda saqlash
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"static/receipts/{printer_type}_{timestamp}.txt"
            
            os.makedirs("static/receipts", exist_ok=True)
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Agar real printer ulangan bo'lsa
            if settings.PRINTER_PORT:
                try:
                    # Windows uchun
                    if os.name == 'nt':
                        subprocess.run(['print', f'/D:{settings.PRINTER_PORT}', filename], 
                                     capture_output=True, shell=True)
                    # Linux/Mac uchun
                    else:
                        with open(settings.PRINTER_PORT, 'wb') as printer:
                            printer.write(content.encode('utf-8'))
                except Exception as e:
                    print(f"[PRINTER] Printerga yuborishda xatolik: {e}")
            
            return True
            
        except Exception as e:
            print(f"[PRINTER] Xatolik: {e}")
            return False
    
    @staticmethod
    def test_printer() -> Dict[str, Any]:
        """Printerni test qilish"""
        test_content = "\n" + "=" * 40 + "\n"
        test_content += "PRINTER TEST".center(40) + "\n"
        test_content += "=" * 40 + "\n"
        test_content += "Agar bu matn chiqqan bo'lsa,".center(40) + "\n"
        test_content += "printer to'g'ri ishlayapti!".center(40) + "\n"
        test_content += "=" * 40 + "\n\n\n"
        
        success = PrinterService._send_to_printer(test_content, "test")
        
        return {
            "success": success,
            "printer_enabled": settings.PRINTER_ENABLED,
            "printer_port": settings.PRINTER_PORT if settings.PRINTER_ENABLED else None
        }