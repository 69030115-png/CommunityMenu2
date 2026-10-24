# purchase.py  การจัดซื้อ: สร้างคำสั่งซื้อ เลือกผู้ขาย บันทึกรับสินค้า (เพิ่มเข้าคลังอัตโนมัติ)

from tkinter import ttk, messagebox

import logic
from screens.widgets import make_table, clear_table, selected_id, FormDialog, to_float

STATUS_TH = {"PENDING": "รอรับสินค้า", "RECEIVED": "รับแล้ว", "CANCELLED": "ยกเลิก"}


class PurchaseScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        ttk.Label(self, text="คำสั่งซื้อ", style="Head.TLabel").pack(anchor="w")
        f, self.tree = make_table(self, [("id", "เลขที่"), ("farmer", "ผู้ขาย"), ("date", "วันที่สั่ง"),
                                         ("plan", "จากแผน"), ("total", "ยอด (บาท)"), ("status", "สถานะ"),
                                         ("recv", "วันที่รับ")],
                                  [60, 280, 150, 70, 100, 110, 150], height=12)
        f.pack(fill="both", expand=True, pady=3)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_items())

        b = ttk.Frame(self)
        b.pack(fill="x")
        ttk.Button(b, text="+ สร้างคำสั่งซื้อเอง", command=self.new_po).pack(side="left", padx=2)
        ttk.Button(b, text="✔ บันทึกรับสินค้า", style="Accent.TButton", command=self.receive).pack(side="left", padx=2)
        ttk.Button(b, text="✖ ยกเลิกคำสั่งซื้อ", style="Danger.TButton", command=self.cancel).pack(side="left", padx=2)

        ttk.Label(self, text="รายการในคำสั่งซื้อ", style="Head.TLabel").pack(anchor="w", pady=(10, 0))
        f, self.tree_items = make_table(self, [("name", "วัตถุดิบ"), ("qty", "จำนวน"), ("price", "ราคา/หน่วย"),
                                               ("sum", "รวม (บาท)")], [200, 140, 140, 120], height=6)
        f.pack(fill="x", pady=3)

    def refresh(self):
        keep = self.tree.selection()
        clear_table(self.tree)
        for r in logic.list_pos():
            tag = {"PENDING": "warn", "RECEIVED": "good", "CANCELLED": "muted"}.get(r["status"], ())
            self.tree.insert("", "end", iid=str(r["id"]), tags=tag, values=(
                r["id"], r["farmer"], r["created_at"], r["plan_id"] or "-", f"{r['total']:,.2f}",
                STATUS_TH.get(r["status"], r["status"]), r["received_at"] or ""))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        self.show_items()

    def show_items(self):
        clear_table(self.tree_items)
        sel = self.tree.selection()
        if not sel:
            return
        for it in logic.get_po_items(int(sel[0])):
            self.tree_items.insert("", "end", values=(
                it["name"], logic.fmt_qty(it["qty"], it["unit"]), f"{it['unit_price']:g} บาท/{it['unit']}",
                f"{it['qty'] * it['unit_price']:,.2f}"))

    def new_po(self):
        farmers = logic.list_farmers()
        ings = logic.list_ingredients()
        f_names = [f"{f['id']} {f['name']}" for f in farmers]
        i_names = [f"{i['code']} {i['name']}" for i in ings]
        dlg = FormDialog(self, "สร้างคำสั่งซื้อ", [
            ("farmer", "ผู้ขาย", f_names, ""),
            ("ing", "วัตถุดิบ", i_names, ""),
            ("qty", "จำนวน", None, ""),
            ("unit", "หน่วย", ["กก.", "กรัม", "ฟอง", "ชิ้น"], "กก."),
            ("price", "ราคาต่อหน่วยที่เลือก (บาท)", None, ""),
        ])
        if not dlg.result:
            return
        r = dlg.result
        try:
            if not r["farmer"] or not r["ing"]:
                raise logic.AppError("กรุณาเลือกผู้ขายและวัตถุดิบ")
            ing = ings[i_names.index(r["ing"])]
            factor = logic.to_std(1, r["unit"], ing["unit"])
            qty = to_float(r["qty"], "จำนวน") * factor
            price = to_float(r["price"], "ราคา") / factor
            if qty <= 0 or price < 0:
                raise logic.AppError("จำนวนต้องมากกว่า 0")
            po_id = logic.create_po(int(r["farmer"].split()[0]), [(ing["id"], qty, price)])
            messagebox.showinfo("สำเร็จ", f"สร้างคำสั่งซื้อ #{po_id} แล้ว")
            self.refresh()
        except (logic.AppError, ValueError) as e:
            messagebox.showerror("ผิดพลาด", str(e))

    def receive(self):
        po_id = selected_id(self.tree)
        if not po_id:
            return
        if not messagebox.askyesno("ยืนยัน", f"บันทึกรับสินค้าคำสั่งซื้อ #{po_id} และเพิ่มเข้าคลังเป็นล็อตใหม่?"):
            return
        try:
            logic.receive_po(po_id)
            messagebox.showinfo("สำเร็จ", "รับสินค้าแล้ว ยอดคลังอัปเดตเรียบร้อย")
            self.refresh()
        except logic.AppError as e:
            messagebox.showerror("ผิดพลาด", str(e))

    def cancel(self):
        po_id = selected_id(self.tree)
        if po_id and messagebox.askyesno("ยืนยัน", f"ยกเลิกคำสั่งซื้อ #{po_id}?"):
            try:
                logic.cancel_po(po_id)
                self.refresh()
            except logic.AppError as e:
                messagebox.showerror("ผิดพลาด", str(e))
