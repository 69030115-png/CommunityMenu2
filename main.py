# main.py
# เมนูชุมชน (Community Menu Planner)
# ระบบวางแผนเมนูและจัดซื้อผลผลิตชุมชนโดยใช้ AI
# รัน: python main.py

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from db import init_db
from screens.widgets import setup_style, GREEN, GREEN_DARK, GRAY
from screens.home import HomeScreen
from screens.inventory import InventoryScreen
from screens.recipes import RecipeScreen
from screens.community import CommunityScreen
from screens.planner import PlannerScreen
from screens.purchase import PurchaseScreen
from screens.report import ReportScreen

THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thai_date(d):
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("เมนูชุมชน - ระบบวางแผนเมนูและจัดซื้อผลผลิตชุมชน")
        self.geometry("1240x820")
        self.minsize(1050, 680)
        setup_style(self)
        # error ที่ไม่คาดคิดในปุ่มต่าง ๆ ให้ขึ้นกล่องข้อความ (ใน .exe ไม่มีหน้าจอดำให้ดู error)
        self.report_callback_exception = self.show_error

        # ---------- แถบหัว ----------
        header = tk.Frame(self, bg=GREEN, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="ม", bg="white", fg=GREEN, font=("Tahoma", 18, "bold"),
                 width=2).pack(side="left")
        title_box = tk.Frame(header, bg=GREEN)
        title_box.pack(side="left", padx=10)
        tk.Label(title_box, text="เมนูชุมชน", bg=GREEN, fg="white",
                 font=("Tahoma", 16, "bold")).pack(anchor="w")
        tk.Label(title_box, text="ระบบวางแผนเมนูและจัดซื้อผลผลิตชุมชนโดยใช้ AI", bg=GREEN, fg="#c8e6c9",
                 font=("Tahoma", 10)).pack(anchor="w")
        tk.Label(header, text="วันนี้ " + thai_date(date.today()), bg=GREEN_DARK, fg="white",
                 font=("Tahoma", 10, "bold"), padx=12, pady=4).pack(side="right")
        # ---------- แถบสถานะด้านล่าง ----------
        footer = tk.Frame(self, bg="#e5ebe3", padx=12, pady=4)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, text="ข้อมูลในระบบเป็นข้อมูลจำลองสำหรับสาธิต  •  AI ช่วยเสนอเมนูเท่านั้น "
                              "ผู้ใช้เป็นผู้ยืนยันคำสั่งซื้อและการเบิกทุกครั้ง",
                 bg="#e5ebe3", fg=GRAY, font=("Tahoma", 9)).pack(side="left")

        # ---------- แท็บ ----------
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(8, 6))
        self.screens = [
            ("หน้าหลัก", HomeScreen(self.tabs)),
            ("คลังวัตถุดิบ", InventoryScreen(self.tabs)),
            ("สูตรอาหาร", RecipeScreen(self.tabs)),
            ("ข้อมูลชุมชน", CommunityScreen(self.tabs)),
            ("แผนเมนูและ AI", PlannerScreen(self.tabs)),
            ("การจัดซื้อ", PurchaseScreen(self.tabs)),
            ("รายงาน", ReportScreen(self.tabs)),
        ]
        for name, screen in self.screens:
            self.tabs.add(screen, text=name)

        # เปลี่ยนแท็บเมื่อไหร่ ให้โหลดข้อมูลใหม่จากฐานข้อมูล
        self.tabs.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.screens[0][1].refresh()

    def show_error(self, exc_type, exc, tb):
        messagebox.showerror("เกิดข้อผิดพลาด", f"{exc_type.__name__}: {exc}")

    def on_tab_changed(self, event):
        index = self.tabs.index(self.tabs.select())
        self.screens[index][1].refresh()


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("เปิดฐานข้อมูลไม่ได้",
                             f"{e}\n\nลองย้ายโปรแกรมไปไว้ในโฟลเดอร์ที่เขียนไฟล์ได้ เช่น เอกสาร")
        raise SystemExit(1)
    App().mainloop()
