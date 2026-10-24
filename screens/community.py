# community.py  ข้อมูลชุมชน: เกษตรกร + ผลผลิตพร้อมขาย (ราคา ปริมาณ วันพร้อมส่ง)

from tkinter import ttk, messagebox
from datetime import date

import logic
from screens.widgets import make_table, clear_table, selected_id, FormDialog, to_float


class CommunityScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        ttk.Label(self, text="เกษตรกร / ผู้ขาย", style="Head.TLabel").pack(anchor="w")
        f, self.tree_f = make_table(self, [("id", "รหัส"), ("name", "ชื่อกลุ่มหรือผู้ขาย"), ("area", "พื้นที่"),
                                           ("contact", "ติดต่อ")], [50, 320, 150, 150], height=6)
        f.pack(fill="x", pady=3)
        b = ttk.Frame(self)
        b.pack(fill="x")
        ttk.Button(b, text="เพิ่มเกษตรกร", command=lambda: self.farmer_form(None)).pack(side="left", padx=2)
        ttk.Button(b, text="แก้ไข", command=self.edit_farmer).pack(side="left", padx=2)

        ttk.Label(self, text="ผลผลิตพร้อมขาย", style="Head.TLabel").pack(anchor="w", pady=(12, 0))
        f, self.tree_p = make_table(self, [("ing", "วัตถุดิบ"), ("farmer", "ผู้ขาย"), ("price", "ราคา"),
                                           ("qty", "ปริมาณพร้อมขาย"), ("ready", "วันพร้อมส่ง"),
                                           ("updated", "อัปเดตล่าสุด")],
                                    [120, 260, 110, 120, 100, 150], height=12)
        f.pack(fill="both", expand=True, pady=3)
        b = ttk.Frame(self)
        b.pack(fill="x")
        ttk.Button(b, text="เพิ่มผลผลิต", command=lambda: self.produce_form(None)).pack(side="left", padx=2)
        ttk.Button(b, text="แก้ไข/อัปเดตราคา", command=self.edit_produce).pack(side="left", padx=2)
        ttk.Label(b, text="* ราคาและปริมาณควรยืนยันกับผู้ขายก่อนสั่งทุกครั้ง  •  แถวสีเทา = ยังไม่พร้อมส่ง/หมด",
                  style="Hint.TLabel").pack(side="left", padx=10)

    def refresh(self):
        clear_table(self.tree_f)
        self.farmers = logic.list_farmers()
        for r in self.farmers:
            self.tree_f.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], r["area"], r["contact"]))
        clear_table(self.tree_p)
        self.produce = {r["id"]: r for r in logic.list_produce()}
        for r in self.produce.values():
            tag = "muted" if r["qty_available"] <= 0 or r["ready_date"] > date.today().isoformat() else ()
            self.tree_p.insert("", "end", iid=str(r["id"]), tags=tag, values=(
                r["ing_name"], r["farmer"], f"{r['price']:g} บาท/{r['sell_unit']}",
                f"{r['qty_available']:g} {r['sell_unit']}", r["ready_date"], r["updated_at"]))

    # ----- เกษตรกร -----
    def edit_farmer(self):
        fid = selected_id(self.tree_f)
        if fid:
            self.farmer_form(next(f for f in self.farmers if f["id"] == fid))

    def farmer_form(self, farmer):
        g = (lambda k: farmer[k] if farmer else "")
        dlg = FormDialog(self, "ข้อมูลเกษตรกร", [
            ("name", "ชื่อกลุ่ม/ผู้ขาย", None, g("name")),
            ("area", "พื้นที่", None, g("area")),
            ("contact", "ข้อมูลติดต่อ", None, g("contact")),
        ])
        if dlg.result:
            try:
                logic.save_farmer(farmer["id"] if farmer else None, **dlg.result)
                self.refresh()
            except logic.AppError as e:
                messagebox.showerror("ผิดพลาด", str(e))

    # ----- ผลผลิต -----
    def edit_produce(self):
        pid = selected_id(self.tree_p)
        if pid:
            self.produce_form(self.produce[pid])

    def produce_form(self, p):
        ings = logic.list_ingredients()
        ing_names = [f"{i['code']} {i['name']}" for i in ings]
        farmer_names = [f"{f['id']} {f['name']}" for f in self.farmers]
        dlg = FormDialog(self, "ผลผลิตพร้อมขาย", [
            ("farmer", "ผู้ขาย", farmer_names,
             next((n for n in farmer_names if p and n.startswith(f"{p['farmer_id']} ")), "")),
            ("ing", "วัตถุดิบ", ing_names,
             next((n for i, n in zip(ings, ing_names) if p and i["id"] == p["ingredient_id"]), "")),
            ("price", "ราคา (บาท ต่อหน่วยขาย)", None, p["price"] if p else ""),
            ("unit", "หน่วยขาย", ["กก.", "กรัม", "ฟอง", "ชิ้น"], p["sell_unit"] if p else "กก."),
            ("qty", "ปริมาณพร้อมขาย (หน่วยขาย)", None, p["qty_available"] if p else ""),
            ("ready", "วันพร้อมส่ง (YYYY-MM-DD)", None, p["ready_date"] if p else date.today().isoformat()),
        ])
        if not dlg.result:
            return
        r = dlg.result
        try:
            if not r["farmer"] or not r["ing"]:
                raise logic.AppError("กรุณาเลือกผู้ขายและวัตถุดิบ")
            farmer_id = int(r["farmer"].split()[0])
            ing_id = ings[ing_names.index(r["ing"])]["id"]
            date.fromisoformat(r["ready"])
            logic.save_produce(p["id"] if p else None, farmer_id, ing_id, to_float(r["price"], "ราคา"),
                               r["unit"], to_float(r["qty"], "ปริมาณ"), r["ready"])
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))
