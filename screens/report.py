# report.py  รายงาน: ยอดจัดซื้อจากเกษตรกร / การเบิกใช้ / ของเสีย ตามช่วงเวลา

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

import logic
from screens.widgets import make_table, clear_table


class ReportScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="ตั้งแต่ (YYYY-MM-DD)").pack(side="left")
        self.from_var = tk.StringVar(value=(date.today() - timedelta(days=30)).isoformat())
        ttk.Entry(bar, textvariable=self.from_var, width=12).pack(side="left", padx=4)
        ttk.Label(bar, text="ถึง").pack(side="left")
        self.to_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(bar, textvariable=self.to_var, width=12).pack(side="left", padx=4)
        ttk.Button(bar, text="ดูรายงาน", style="Accent.TButton", command=self.refresh).pack(side="left", padx=6)

        ttk.Label(self, text="มูลค่าซื้อจากเกษตรกร (รับสินค้าแล้ว)", style="Head.TLabel").pack(anchor="w", pady=(10, 0))
        f, self.tree_buy = make_table(self, [("farmer", "เกษตรกร/ผู้ขาย"), ("n", "จำนวนคำสั่งซื้อ"),
                                             ("total", "มูลค่า (บาท)")], [350, 130, 130], height=6)
        f.pack(fill="x", pady=3)
        self.buy_total = ttk.Label(self, text="")
        self.buy_total.pack(anchor="e")

        ttk.Label(self, text="การเบิกใช้และของเสีย", style="Head.TLabel").pack(anchor="w", pady=(10, 0))
        f, self.tree_mv = make_table(self, [("type", "ประเภท"), ("name", "วัตถุดิบ"), ("qty", "ปริมาณ"),
                                            ("value", "มูลค่า (บาท)")], [100, 200, 140, 130], height=10)
        f.pack(fill="both", expand=True, pady=3)
        self.mv_total = ttk.Label(self, text="")
        self.mv_total.pack(anchor="e")

    def refresh(self):
        try:
            d1 = date.fromisoformat(self.from_var.get()).isoformat()
            d2 = date.fromisoformat(self.to_var.get()).isoformat()
        except ValueError:
            messagebox.showerror("ผิดพลาด", "รูปแบบวันที่ไม่ถูกต้อง")
            return
        buy, moves = logic.report(d1, d2)
        clear_table(self.tree_buy)
        total = 0
        for r in buy:
            self.tree_buy.insert("", "end", values=(r["farmer"], r["n"], f"{r['total']:,.2f}"))
            total += r["total"]
        self.buy_total.config(text=f"รวมซื้อจากชุมชน {total:,.2f} บาท")

        clear_table(self.tree_mv)
        use_v = waste_v = 0
        for r in moves:
            t = "เบิกใช้" if r["type"] == "USE" else "ของเสีย"
            self.tree_mv.insert("", "end", tags="danger" if r["type"] == "WASTE" else (), values=(t, r["name"], logic.fmt_qty(r["qty"], r["unit"]), f"{r['value']:,.2f}"))
            if r["type"] == "USE":
                use_v += r["value"]
            else:
                waste_v += r["value"]
        self.mv_total.config(text=f"มูลค่าเบิกใช้ {use_v:,.2f} บาท   |   มูลค่าของเสีย {waste_v:,.2f} บาท")
