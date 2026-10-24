# inventory.py  คลังวัตถุดิบ: เพิ่ม/แก้ไข/ค้นหา/รับเข้า/เบิกใช้/ของเสีย/ปรับยอด (แยกล็อต)

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

import logic
from db import get_conn
from screens.widgets import make_table, clear_table, selected_id, FormDialog, to_float

TYPE_TH = {"IN": "รับเข้า", "USE": "เบิกใช้", "WASTE": "ของเสีย", "ADJUST": "ปรับยอด"}


def unit_choices(std_unit):
    return ["กรัม", "กก."] if std_unit == "กรัม" else [std_unit]


class InventoryScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        # ----- ซ้าย: รายการวัตถุดิบ -----
        left = ttk.Frame(self)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(fill="x")
        ttk.Label(bar, text="ค้นหา:").pack(side="left")
        self.search_var = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.search_var, width=20)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.refresh())

        f, self.tree = make_table(left, [("code", "รหัส"), ("name", "ชื่อ"), ("stock", "คงเหลือ"),
                                         ("min", "ขั้นต่ำ")], [60, 150, 110, 90], height=17)
        f.pack(fill="both", expand=True, pady=5)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_detail())

        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="+ เพิ่มวัตถุดิบ", command=self.add).pack(side="left", padx=2)
        ttk.Button(btns, text="แก้ไข", command=self.edit).pack(side="left", padx=2)
        ttk.Button(btns, text="⬇ รับเข้า", style="Accent.TButton", command=self.receive).pack(side="left", padx=2)
        ttk.Button(btns, text="⬆ เบิกใช้", command=self.use).pack(side="left", padx=2)
        ttk.Label(left, text="แถวสีแดง = คงเหลือต่ำกว่าขั้นต่ำ", style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        # ----- ขวา: ล็อต + ประวัติ -----
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ttk.Label(right, text="ล็อตคงเหลือ (เรียงตามวันควรใช้ก่อน)", style="Head.TLabel").pack(anchor="w")
        f, self.tree_lot = make_table(right, [("id", "ล็อต"), ("recv", "วันรับ"), ("use_by", "ควรใช้ก่อน"),
                                              ("qty", "คงเหลือ"), ("cost", "ต้นทุน/หน่วย")],
                                      [50, 100, 100, 100, 100], height=7)
        f.pack(fill="x", pady=3)
        b2 = ttk.Frame(right)
        b2.pack(fill="x")
        ttk.Button(b2, text="บันทึกของเสีย (ล็อตที่เลือก)", style="Danger.TButton",
                   command=self.waste).pack(side="left", padx=2)
        ttk.Button(b2, text="ปรับยอด (ล็อตที่เลือก)", command=self.adjust).pack(side="left", padx=2)
        ttk.Label(b2, text="ส้ม = ใกล้ถึงวัน  แดง = เลยวันแล้ว", style="Hint.TLabel").pack(side="left", padx=8)

        ttk.Label(right, text="ประวัติเคลื่อนไหว", style="Head.TLabel").pack(anchor="w", pady=(10, 0))
        f, self.tree_mv = make_table(right, [("time", "วันเวลา"), ("type", "ประเภท"), ("qty", "จำนวน"),
                                             ("lot", "ล็อต"), ("ref", "อ้างอิง"), ("reason", "เหตุผล")],
                                     [140, 70, 90, 50, 120, 120], height=10)
        f.pack(fill="both", expand=True, pady=3)

    # ---------- แสดงผล ----------
    def refresh(self):
        keep = self.tree.selection()
        clear_table(self.tree)
        for r in logic.list_ingredients(self.search_var.get().strip()):
            tag = "danger" if r["stock"] < r["min_stock"] else ()
            self.tree.insert("", "end", iid=str(r["id"]), tags=tag, values=(
                r["code"], r["name"], logic.fmt_qty(r["stock"], r["unit"]), logic.fmt_qty(r["min_stock"], r["unit"])))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        self.show_detail()

    def current_ing(self):
        sel = self.tree.selection()
        return logic.get_ingredient(int(sel[0])) if sel else None

    def show_detail(self):
        clear_table(self.tree_lot)
        clear_table(self.tree_mv)
        ing = self.current_ing()
        if not ing:
            return
        for lot in logic.list_lots(ing["id"]):
            days = (date.fromisoformat(lot["use_by"]) - date.today()).days
            tag = "danger" if days < 0 else ("warn" if days <= 2 else ())
            self.tree_lot.insert("", "end", iid=str(lot["id"]), tags=tag, values=(
                lot["id"], lot["received_date"], lot["use_by"], logic.fmt_qty(lot["qty_left"], ing["unit"]),
                f"{lot['unit_cost']:g}"))
        for m in logic.list_movements(ing["id"]):
            tag = {"IN": "good", "WASTE": "danger", "ADJUST": "warn"}.get(m["type"], ())
            self.tree_mv.insert("", "end", tags=tag, values=(
                m["created_at"], TYPE_TH.get(m["type"], m["type"]), logic.fmt_qty(m["qty"], ing["unit"]),
                m["lot_id"] or "", m["ref"] or "", m["reason"] or ""))

    # ---------- เพิ่ม / แก้ไข ----------
    def add(self):
        self.open_form(None)

    def edit(self):
        ing_id = selected_id(self.tree)
        if ing_id:
            self.open_form(logic.get_ingredient(ing_id))

    def open_form(self, ing):
        g = (lambda k, d="": ing[k] if ing else d)
        dlg = FormDialog(self, "ข้อมูลวัตถุดิบ", [
            ("code", "รหัส", None, g("code")),
            ("name", "ชื่อ", None, g("name")),
            ("unit", "หน่วยมาตรฐาน", ["กรัม", "ฟอง", "ชิ้น"], g("unit", "กรัม")),
            ("min", "คงเหลือขั้นต่ำ (หน่วยมาตรฐาน)", None, g("min_stock", 0)),
            ("days", "อายุโดยประมาณ (วัน)", None, g("shelf_days", 7)),
        ])
        if not dlg.result:
            return
        try:
            r = dlg.result
            logic.save_ingredient(ing["id"] if ing else None, r["code"], r["name"], r["unit"],
                                  to_float(r["min"], "ขั้นต่ำ"), int(to_float(r["days"], "อายุ")))
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))

    # ---------- รับเข้า ----------
    def receive(self):
        ing = self.current_ing()
        if not ing:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกวัตถุดิบก่อน")
            return
        default_use_by = (date.today() + timedelta(days=ing["shelf_days"])).isoformat()
        dlg = FormDialog(self, f"รับเข้า: {ing['name']}", [
            ("qty", "จำนวน", None, ""),
            ("unit", "หน่วย", unit_choices(ing["unit"]), ing["unit"]),
            ("price", "ราคาต่อหน่วยที่เลือก (บาท)", None, ""),
            ("use_by", "ควรใช้ก่อน (YYYY-MM-DD)", None, default_use_by),
            ("note", "หมายเหตุ", None, ""),
        ])
        if not dlg.result:
            return
        try:
            r = dlg.result
            qty = to_float(r["qty"], "จำนวน")
            price = to_float(r["price"], "ราคา")
            factor = logic.to_std(1, r["unit"], ing["unit"])
            date.fromisoformat(r["use_by"])
            logic.receive_manual(ing["id"], qty * factor, price / factor, r["use_by"], r["note"])
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))

    # ---------- เบิกใช้ ----------
    def use(self):
        ing = self.current_ing()
        if not ing:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกวัตถุดิบก่อน")
            return
        dlg = FormDialog(self, f"เบิกใช้: {ing['name']}", [
            ("qty", "จำนวน", None, ""),
            ("unit", "หน่วย", unit_choices(ing["unit"]), ing["unit"]),
            ("reason", "หมายเหตุ", None, ""),
        ])
        if not dlg.result:
            return
        try:
            r = dlg.result
            qty = logic.to_std(to_float(r["qty"], "จำนวน"), r["unit"], ing["unit"])
            # ระบบเสนอล็อตที่ควรใช้ก่อน ให้ผู้ใช้ยืนยัน
            conn = get_conn()
            plan = logic.suggest_lots(conn, ing["id"], qty)
            conn.close()
            text = "\n".join(f"- ล็อต {lot['id']} (ควรใช้ก่อน {lot['use_by']}): {logic.fmt_qty(t, ing['unit'])}"
                             for lot, t in plan)
            if messagebox.askyesno("ยืนยันการเบิก",
                                   f"ระบบเสนอให้เบิกจากล็อต:\n{text}\n\nตรวจสภาพวัตถุดิบจริงแล้วใช่หรือไม่?"):
                logic.issue_manual(ing["id"], qty, "USE", r["reason"])
                self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))

    # ---------- ของเสีย / ปรับยอด ----------
    def waste(self):
        ing = self.current_ing()
        lot_id = selected_id(self.tree_lot)
        if not ing or not lot_id:
            return
        dlg = FormDialog(self, f"บันทึกของเสีย ล็อต {lot_id}", [
            ("qty", f"จำนวน ({ing['unit']})", None, ""),
            ("reason", "สาเหตุ", None, "เสีย/เน่า"),
        ])
        if not dlg.result:
            return
        try:
            logic.waste_lot(lot_id, to_float(dlg.result["qty"], "จำนวน"), dlg.result["reason"])
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))

    def adjust(self):
        ing = self.current_ing()
        lot_id = selected_id(self.tree_lot)
        if not ing or not lot_id:
            return
        dlg = FormDialog(self, f"ปรับยอด ล็อต {lot_id}", [
            ("qty", f"ยอดที่นับได้จริง ({ing['unit']})", None, ""),
            ("reason", "เหตุผล (บังคับ)", None, ""),
        ])
        if not dlg.result:
            return
        try:
            logic.adjust_lot(lot_id, to_float(dlg.result["qty"], "ยอด"), dlg.result["reason"])
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))
