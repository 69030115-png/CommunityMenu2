# planner.py  แผนเมนูและ AI: ตั้งเงื่อนไข -> AI แนะนำ -> เลือกเมนู + จำนวนจาน -> ดูรายการซื้อ -> ยืนยัน

import threading
import tkinter as tk
from tkinter import ttk, messagebox

import logic
import ai_helper
from screens.widgets import make_table, clear_table, selected_id, to_float



class PlannerScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self.plan_items = []          # [(menu_id, ชื่อ, จำนวนจาน)]
        self.last_lines = None

        # ---------- 1) เงื่อนไข + AI ----------
        box1 = ttk.LabelFrame(self, text="1) เงื่อนไขและคำแนะนำจาก AI", padding=8)
        box1.pack(fill="x")
        ttk.Label(box1, text="งบซื้อเพิ่ม (บาท)").grid(row=0, column=0, sticky="w")
        self.budget_var = tk.StringVar(value="100")
        ttk.Entry(box1, textvariable=self.budget_var, width=10).grid(row=0, column=1, padx=4)
        ttk.Label(box1, text="จำนวนจานต่อเมนู").grid(row=0, column=2, sticky="w")
        self.dish_var = tk.StringVar(value="30")
        ttk.Entry(box1, textvariable=self.dish_var, width=8).grid(row=0, column=3, padx=4)
        ttk.Label(box1, text="เมนูที่ไม่ต้องการ (เลือกได้หลายเมนู)").grid(row=0, column=4, sticky="w", padx=(10, 0))
        self.ex_list = tk.Listbox(box1, selectmode="multiple", height=4, exportselection=False, width=28)
        self.ex_list.grid(row=0, column=5, rowspan=2, padx=4)
        self.ai_btn = ttk.Button(box1, text="ให้ AI แนะนำเมนู", style="Accent.TButton", command=self.ask_ai)
        self.ai_btn.grid(row=0, column=6, padx=6)
        self.ai_status = ttk.Label(box1, text="", foreground="gray")
        self.ai_status.grid(row=1, column=0, columnspan=5, sticky="w")

        f, self.tree_ai = make_table(box1, [("code", "รหัส"), ("name", "เมนู"), ("reason", "เหตุผลจาก AI"),
                                            ("buy", "ยอดซื้อเพิ่ม*"), ("note", "ข้อจำกัด")],
                                     [50, 150, 420, 90, 220], height=3)
        f.grid(row=2, column=0, columnspan=7, sticky="we", pady=4)
        # คลิกแถวแล้วแสดงเหตุผลเต็ม (ในตารางข้อความยาวจะถูกตัด)
        self.tree_ai.bind("<<TreeviewSelect>>", lambda e: self.show_reason())
        ttk.Button(box1, text="ใช้เมนูที่เลือกจาก AI", command=self.use_ai_pick).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(box1, text="* ตัวเลขคำนวณใหม่โดยโปรแกรม ไม่ได้ใช้ตัวเลขจาก AI",
                  foreground="gray").grid(row=3, column=2, columnspan=4, sticky="w")

        # ---------- 2) เลือกเมนู ----------
        box2 = ttk.LabelFrame(self, text="2) เมนูในแผนวันนี้ (เลือกเองได้ แม้ AI ใช้ไม่ได้)", padding=8)
        box2.pack(fill="x", pady=6)
        self.menu_var = tk.StringVar()
        self.menu_combo = ttk.Combobox(box2, textvariable=self.menu_var, state="readonly", width=30)
        self.menu_combo.pack(side="left")
        ttk.Label(box2, text="จำนวนจาน").pack(side="left", padx=(8, 2))
        self.n_var = tk.StringVar(value="30")
        ttk.Entry(box2, textvariable=self.n_var, width=6).pack(side="left")
        ttk.Button(box2, text="เพิ่ม", command=self.add_menu).pack(side="left", padx=4)
        ttk.Button(box2, text="ล้าง", command=self.clear_menus).pack(side="left")
        self.plan_label = ttk.Label(box2, text="-")
        self.plan_label.pack(side="left", padx=10)

        # ---------- 3) ผลคำนวณ ----------
        box3 = ttk.LabelFrame(self, text="3) วัตถุดิบที่ต้องใช้และต้องซื้อเพิ่ม", padding=8)
        box3.pack(fill="both", expand=True)
        f, self.tree_calc = make_table(box3, [("name", "วัตถุดิบ"), ("need", "ต้องใช้"), ("have", "มีในคลังที่ใช้ได้"),
                                              ("buy", "ต้องซื้อเพิ่ม"), ("seller", "ผู้ขายที่เสนอ"),
                                              ("cost", "ยอดซื้อ (บาท)")],
                                       [130, 100, 120, 110, 280, 100], height=5)
        f.pack(fill="both", expand=True)
        # สรุปยอด + ปุ่ม pack ไว้ด้านล่างก่อนตาราง (before=f) ให้แสดงเสมอ ตารางค่อยหดแทน
        b = ttk.Frame(box3)
        b.pack(side="bottom", fill="x", pady=(4, 0), before=f)
        self.warn_label = ttk.Label(box3, text="", justify="left", style="Warn.TLabel")
        self.warn_label.pack(side="bottom", anchor="w", before=f)
        self.sum_label = ttk.Label(box3, text="", justify="left", font=("Tahoma", 10, "bold"))
        self.sum_label.pack(side="bottom", anchor="w", pady=(6, 0), before=f)
        ttk.Button(b, text="✔ ยืนยันแผน + สร้างคำสั่งซื้อ", style="Accent.TButton",
                   command=self.confirm_plan).pack(side="left")
        ttk.Label(b, text="แถวสีส้ม = ต้องซื้อเพิ่ม  แดง = หาผู้ขายไม่ได้", style="Hint.TLabel").pack(side="left", padx=10)

        # ---------- 4) แผนที่ยืนยันแล้ว ----------
        box4 = ttk.LabelFrame(self, text="4) แผนที่ยืนยันแล้ว", padding=8)
        box4.pack(side="bottom", fill="x", pady=(6, 0), before=box3)   # ให้ส่วนที่ 4 แสดงเสมอ
        # ใช้ combobox บรรทัดเดียวแทนตาราง จะได้ไม่กินพื้นที่หน้าจอ
        ttk.Label(box4, text="แผนที่รอเบิก").pack(side="left")
        self.plan_var = tk.StringVar()
        self.plan_combo = ttk.Combobox(box4, textvariable=self.plan_var, state="readonly", width=70)
        self.plan_combo.pack(side="left", padx=6)
        ttk.Button(box4, text="⬆ ยืนยันเบิกวัตถุดิบตามแผน", style="Accent.TButton",
                   command=self.use_plan).pack(side="left", padx=6)
        self.used_label = ttk.Label(box4, text="", style="Hint.TLabel")
        self.used_label.pack(side="left", padx=6)

    # ---------------------------------------------------
    def refresh(self):
        self.menus = logic.list_menus()
        self.menu_combo["values"] = [f"{m['code']} {m['name']}" for m in self.menus]
        sel = [self.ex_list.get(i) for i in self.ex_list.curselection()]
        self.ex_list.delete(0, "end")
        for m in self.menus:
            self.ex_list.insert("end", f"{m['code']} {m['name']}")
            if f"{m['code']} {m['name']}" in sel:
                self.ex_list.selection_set("end")
        plans = logic.list_plans()
        waiting = [p for p in plans if p["status"] != "USED"]
        self.plan_ids = [p["id"] for p in waiting]
        self.plan_combo["values"] = [f"#{p['id']}  {p['plan_date']}  {p['menus']}" for p in waiting]
        self.plan_var.set(self.plan_combo["values"][0] if waiting else "")
        self.used_label.config(text=f"(เบิกแล้ว {len(plans) - len(waiting)} แผน)")
        self.calculate()

    # ---------- AI ----------
    def get_dishes(self, var):
        """อ่านจำนวนจาน ต้องเป็นจำนวนเต็มมากกว่า 0 (ไม่ถูกต้อง -> ValueError)"""
        n = to_float(var.get(), "จำนวนจาน")
        if n <= 0 or n != int(n):
            raise ValueError("จำนวนจานต้องเป็นจำนวนเต็มมากกว่า 0")
        return int(n)

    def ask_ai(self):
        try:
            budget = to_float(self.budget_var.get(), "งบ")
            if budget < 0:
                raise ValueError("งบต้องไม่ติดลบ")
            dishes = self.get_dishes(self.dish_var)
        except ValueError as e:
            messagebox.showerror("ผิดพลาด", str(e))
            return
        excluded = [self.ex_list.get(i).split()[0] for i in self.ex_list.curselection()]
        self.ai_btn.config(state="disabled")
        self.ai_status.config(text="กำลังถาม AI ...")

        # เรียก AI ใน thread แยก หน้าจอจะได้ไม่ค้าง
        # (thread ห้ามแตะหน้าจอโดยตรง จึงเก็บผลไว้ แล้วให้ check_ai มาอ่าน)
        self.ai_result = None

        def work():
            try:
                self.ai_result = ("ok", ai_helper.ask_ai(budget, dishes, excluded))
            except logic.AppError as e:
                self.ai_result = ("error", str(e))
            except Exception as e:      # error อื่นที่ไม่คาดคิด ไม่ให้ปุ่มค้างตลอดไป
                self.ai_result = ("error", f"เกิดข้อผิดพลาด: {e}\nเลือกเมนูเองได้ตามปกติ")

        threading.Thread(target=work, daemon=True).start()
        self.after(200, lambda: self.check_ai(budget, dishes))

    def check_ai(self, budget, dishes):
        if self.ai_result is None:
            self.after(200, lambda: self.check_ai(budget, dishes))     # ยังไม่เสร็จ รอต่อ
        elif self.ai_result[0] == "ok":
            self.show_ai(self.ai_result[1], budget, dishes)
        else:
            self.ai_failed(self.ai_result[1])

    def ai_failed(self, msg):
        self.ai_btn.config(state="normal")
        self.ai_status.config(text="AI ใช้งานไม่ได้ - เลือกเมนูเองในข้อ 2")
        messagebox.showwarning("AI", msg)

    def show_ai(self, recs, budget, dishes):
        self.ai_btn.config(state="normal")
        self.ai_status.config(text=f"AI เสนอ {len(recs)} เมนู (ตรวจรหัสเมนูกับฐานข้อมูลแล้ว)")
        clear_table(self.tree_ai)
        for menu, reason in recs:
            # คำนวณตัวเลขใหม่ด้วยโปรแกรม
            lines, s = logic.calc_plan([(menu["id"], dishes)])
            notes = list(s["problems"])
            if s["buy_cost"] > budget:
                notes.insert(0, f"เกินงบ {s['buy_cost'] - budget:,.2f} บาท")
            self.tree_ai.insert("", "end", iid=str(menu["id"]), tags="warn" if notes else "good", values=(
                menu["code"], menu["name"], reason, f"{s['buy_cost']:,.2f}", "; ".join(notes) or "-"))

    def show_reason(self):
        sel = self.tree_ai.selection()
        if sel:
            v = self.tree_ai.item(sel[0], "values")
            self.ai_status.config(text=f"{v[1]}: {v[2]}", wraplength=900)

    def use_ai_pick(self):
        menu_id = selected_id(self.tree_ai)
        if not menu_id:
            return
        name = self.tree_ai.item(str(menu_id), "values")[1]
        try:
            dishes = self.get_dishes(self.dish_var)
        except ValueError as e:
            messagebox.showerror("ผิดพลาด", str(e))
            return
        self.put_menu(menu_id, name, dishes)

    # ---------- เลือกเมนูเอง ----------
    def add_menu(self):
        i = self.menu_combo.current()
        if i < 0:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกเมนู")
            return
        try:
            n = self.get_dishes(self.n_var)
        except ValueError as e:
            messagebox.showerror("ผิดพลาด", str(e))
            return
        self.put_menu(self.menus[i]["id"], self.menus[i]["name"], n)

    def put_menu(self, menu_id, name, n):
        self.plan_items = [p for p in self.plan_items if p[0] != menu_id]
        self.plan_items.append((menu_id, name, n))
        self.calculate()

    def clear_menus(self):
        self.plan_items = []
        self.calculate()

    def calculate(self):
        clear_table(self.tree_calc)
        self.last_lines = None
        self.warn_label.config(text="")
        if not self.plan_items:
            self.plan_label.config(text="ยังไม่ได้เลือกเมนู")
            self.sum_label.config(text="")
            return
        self.plan_label.config(text=", ".join(f"{n} x{d}" for _, n, d in self.plan_items))
        lines, s = logic.calc_plan([(m, d) for m, _, d in self.plan_items])
        self.last_lines = lines
        for ln in lines:
            u = ln["unit"]
            seller = ""
            if ln["buy"] > 0:
                seller = (f"{ln['offer']['farmer']} (อัปเดต {ln['offer']['updated_at'][:10]})"
                          if ln["offer"] else "ไม่มีผู้ขายพร้อมส่ง")
            tag = ()
            if ln["buy"] > 0:
                tag = "warn" if ln["offer"] else "danger"
            self.tree_calc.insert("", "end", tags=tag, values=(
                ln["name"], logic.fmt_qty(ln["need"], u), logic.fmt_qty(ln["have"], u),
                logic.fmt_qty(ln["buy"], u) if ln["buy"] > 0 else "-", seller,
                f"{ln['buy_cost']:,.2f}" if ln["buy"] > 0 else "-"))

        text = (f"ต้นทุนวัตถุดิบจากคลัง: {s['stock_cost']:,.2f} บาท   |   "
                f"ยอดซื้อเพิ่ม: {s['buy_cost']:,.2f} บาท   |   ต้นทุนรวมประมาณการ: {s['total_cost']:,.2f} บาท")
        warns = []
        try:
            budget = float(self.budget_var.get())
            if s["buy_cost"] > budget:
                warns.append(f"⚠ ยอดซื้อเพิ่มเกินงบ {s['buy_cost'] - budget:,.2f} บาท")
        except ValueError:
            pass
        warns += ["⚠ " + p for p in s["problems"]]
        self.sum_label.config(text=text)
        self.warn_label.config(text="\n".join(warns))

    # ---------- ยืนยัน ----------
    def confirm_plan(self):
        if not self.plan_items or self.last_lines is None:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกเมนูก่อน")
            return
        try:
            budget = to_float(self.budget_var.get(), "งบ")
        except ValueError as e:
            messagebox.showerror("ผิดพลาด", str(e))
            return
        if not messagebox.askyesno("ยืนยัน", "ยืนยันแผนเมนู และสร้างคำสั่งซื้อสำหรับรายการที่ต้องซื้อเพิ่ม?\n"
                                             "(ควรโทรยืนยันราคา/ปริมาณกับผู้ขายก่อน)"):
            return
        plan_id = logic.create_plan([(m, d) for m, _, d in self.plan_items], budget)
        po_ids = logic.create_po_from_plan(self.last_lines, plan_id)
        msg = f"บันทึกแผน #{plan_id} แล้ว"
        msg += f"\nสร้างคำสั่งซื้อ: {', '.join('#' + str(i) for i in po_ids)}" if po_ids else "\nไม่ต้องซื้อเพิ่ม"
        messagebox.showinfo("สำเร็จ", msg + "\n\nไปบันทึกรับสินค้าที่หน้า 'การจัดซื้อ'")
        self.plan_items = []
        self.refresh()

    def use_plan(self):
        if self.plan_combo.current() < 0:
            messagebox.showinfo("แจ้งเตือน", "ยังไม่มีแผนที่รอเบิก\nกด 'ยืนยันแผน + สร้างคำสั่งซื้อ' ในข้อ 3 ก่อน")
            return
        plan_id = self.plan_ids[self.plan_combo.current()]
        if not messagebox.askyesno("ยืนยันเบิก", f"เบิกวัตถุดิบตามแผน #{plan_id} (ระบบเลือกล็อตที่ควรใช้ก่อน)\n"
                                                 "ตรวจสภาพวัตถุดิบจริงแล้วใช่หรือไม่?"):
            return
        try:
            logic.use_plan(plan_id)
            messagebox.showinfo("สำเร็จ", "เบิกวัตถุดิบตามแผนแล้ว")
            self.refresh()
        except logic.AppError as e:
            messagebox.showerror("ผิดพลาด", str(e))
