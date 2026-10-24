# home.py  หน้าหลัก: การ์ดสรุป + ของใกล้หมด / ใกล้วันควรใช้ก่อน / คำสั่งซื้อรอรับ

from tkinter import ttk
from datetime import date, timedelta

import logic
from screens.widgets import make_table, clear_table, make_card, RED, ORANGE, BLUE, GREEN


class HomeScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=12)

        # ---------- การ์ดสรุป ----------
        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=(0, 12))
        c1, self.v_low = make_card(cards, "วัตถุดิบใกล้หมด", RED)
        c2, self.v_near = make_card(cards, "ล็อตใกล้ถึงวันควรใช้ก่อน", ORANGE)
        c3, self.v_po = make_card(cards, "คำสั่งซื้อรอรับสินค้า", BLUE)
        c4, self.v_buy = make_card(cards, "ซื้อจากชุมชน 30 วันล่าสุด (บาท)", GREEN)
        for i, c in enumerate((c1, c2, c3, c4)):
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1)

        # ---------- ตาราง ----------
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True)
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        ttk.Label(left, text="⚠ วัตถุดิบคงเหลือน้อยกว่าขั้นต่ำ", style="Head.TLabel").pack(anchor="w")
        f1, self.tree_low = make_table(left, [("name", "วัตถุดิบ"), ("stock", "คงเหลือ"), ("min", "ขั้นต่ำ")],
                                       [200, 120, 120], height=8)
        f1.pack(fill="both", expand=True, pady=(4, 0))

        ttk.Label(right, text="ใกล้ถึง / เลยวันควรใช้ก่อน (ภายใน 2 วัน)", style="Head.TLabel").pack(anchor="w")
        f2, self.tree_near = make_table(right, [("name", "วัตถุดิบ"), ("qty", "คงเหลือในล็อต"),
                                                ("use_by", "ควรใช้ก่อน"), ("left", "เหลือ")],
                                        [160, 120, 110, 80], height=8)
        f2.pack(fill="both", expand=True, pady=(4, 0))

        ttk.Label(self, text="คำสั่งซื้อที่รอรับสินค้า", style="Head.TLabel").pack(anchor="w", pady=(12, 0))
        f3, self.tree_po = make_table(self, [("id", "เลขที่"), ("farmer", "ผู้ขาย"), ("date", "วันที่สั่ง"),
                                             ("total", "ยอด (บาท)")], [80, 380, 180, 120], height=4)
        f3.pack(fill="x", pady=(4, 0))

        ttk.Label(self, text="* ระบบใช้วันที่ช่วยเตือนเท่านั้น ผู้ใช้ต้องตรวจสภาพวัตถุดิบจริงเอง",
                  style="Hint.TLabel").pack(anchor="w", pady=(8, 0))

    def refresh(self):
        low, near, pos = logic.dashboard()
        for t in (self.tree_low, self.tree_near, self.tree_po):
            clear_table(t)
        for r in low:
            self.tree_low.insert("", "end", tags="danger" if r["stock"] == 0 else (), values=(
                r["name"], logic.fmt_qty(r["stock"], r["unit"]), logic.fmt_qty(r["min_stock"], r["unit"])))
        for r in near:
            days = (date.fromisoformat(r["use_by"]) - date.today()).days
            if days < 0:
                text, tag = "เลยแล้ว", "danger"
            elif days == 0:
                text, tag = "วันนี้", "danger"
            else:
                text, tag = f"{days} วัน", "warn"
            self.tree_near.insert("", "end", tags=tag, values=(
                r["name"], logic.fmt_qty(r["qty_left"], r["unit"]), r["use_by"], text))
        for r in pos:
            self.tree_po.insert("", "end", values=(r["id"], r["farmer"], r["created_at"], f"{r['total']:,.2f}"))

        buy, _ = logic.report((date.today() - timedelta(days=30)).isoformat(), date.today().isoformat())
        self.v_low.config(text=str(len(low)))
        self.v_near.config(text=str(len(near)))
        self.v_po.config(text=str(len(pos)))
        self.v_buy.config(text=f"{sum(r['total'] for r in buy):,.0f}")
