# recipes.py  สูตรอาหาร: ชื่อเมนู + วัตถุดิบ + ปริมาณต่อ 1 จาน

import tkinter as tk
from tkinter import ttk, messagebox

import logic
from screens.widgets import make_table, clear_table, to_float


class RecipeScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self.menu_id = None
        self.items = []          # [(ingredient_id, ชื่อ, หน่วย, ปริมาณต่อจาน)]

        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="รายการเมนู", style="Head.TLabel").pack(anchor="w")
        f, self.tree = make_table(left, [("code", "รหัส"), ("name", "ชื่อเมนู")], [60, 200], height=20)
        f.pack(fill="y", expand=True, pady=4)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_menu())
        ttk.Button(left, text="+ เมนูใหม่", command=self.new_menu).pack(fill="x")

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Label(top, text="รหัสเมนู").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.code_var, width=10).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="ชื่อเมนู").grid(row=0, column=2, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.name_var, width=30).grid(row=0, column=3, padx=4)

        ttk.Label(right, text="วัตถุดิบต่อ 1 จาน", style="Head.TLabel").pack(anchor="w", pady=(10, 0))
        f, self.tree_items = make_table(right, [("name", "วัตถุดิบ"), ("qty", "ปริมาณต่อจาน"), ("unit", "หน่วย")],
                                        [200, 120, 80], height=10)
        f.pack(fill="both", expand=True, pady=4)

        add = ttk.Frame(right)
        add.pack(fill="x")
        ttk.Label(add, text="วัตถุดิบ").pack(side="left")
        self.ing_var = tk.StringVar()
        self.ing_combo = ttk.Combobox(add, textvariable=self.ing_var, state="readonly", width=22)
        self.ing_combo.pack(side="left", padx=4)
        ttk.Label(add, text="ปริมาณ").pack(side="left")
        self.qty_var = tk.StringVar()
        ttk.Entry(add, textvariable=self.qty_var, width=8).pack(side="left", padx=4)
        self.qty_unit = tk.StringVar()
        self.qty_unit_combo = ttk.Combobox(add, textvariable=self.qty_unit, state="readonly", width=6)
        self.qty_unit_combo.pack(side="left")
        self.ing_combo.bind("<<ComboboxSelected>>", lambda e: self.on_pick_ing())
        ttk.Button(add, text="เพิ่ม/แก้ปริมาณ", command=self.add_item).pack(side="left", padx=4)
        ttk.Button(add, text="ลบแถวที่เลือก", command=self.remove_item).pack(side="left")

        ttk.Button(right, text="✔ บันทึกเมนู", style="Accent.TButton", command=self.save).pack(anchor="e", pady=10)

    def refresh(self):
        clear_table(self.tree)
        self.menu_rows = {}
        for m in logic.list_menus():
            self.menu_rows[m["id"]] = m
            self.tree.insert("", "end", iid=str(m["id"]), values=(m["code"], m["name"]))
        self.ingredients = logic.list_ingredients()
        self.ing_combo["values"] = [f"{i['code']} {i['name']}" for i in self.ingredients]

    def on_pick_ing(self):
        ing = self.ingredients[self.ing_combo.current()]
        units = ["กรัม", "กก."] if ing["unit"] == "กรัม" else [ing["unit"]]
        self.qty_unit_combo["values"] = units
        self.qty_unit.set(units[0])

    def load_menu(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.menu_id = int(sel[0])
        # อ่านจากฐานข้อมูล ไม่อ่านจากตาราง (ตารางแปลงรหัสอย่าง "001" เป็นตัวเลข 1)
        m = self.menu_rows[self.menu_id]
        self.code_var.set(m["code"])
        self.name_var.set(m["name"])
        self.items = [(r["ingredient_id"], r["name"], r["unit"], r["qty_per_dish"])
                      for r in logic.get_recipe(self.menu_id)]
        self.show_items()

    def new_menu(self):
        self.menu_id = None
        self.code_var.set("")
        self.name_var.set("")
        self.items = []
        self.tree.selection_remove(self.tree.selection())
        self.show_items()

    def show_items(self):
        clear_table(self.tree_items)
        for i, (ing_id, name, unit, qty) in enumerate(self.items):
            self.tree_items.insert("", "end", iid=str(i), values=(name, f"{qty:g}", unit))

    def add_item(self):
        if self.ing_combo.current() < 0:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกวัตถุดิบ")
            return
        ing = self.ingredients[self.ing_combo.current()]
        try:
            qty = logic.to_std(to_float(self.qty_var.get(), "ปริมาณ"), self.qty_unit.get(), ing["unit"])
        except (ValueError, logic.AppError) as e:
            messagebox.showerror("ผิดพลาด", str(e))
            return
        # ถ้ามีวัตถุดิบนี้อยู่แล้ว ให้แทนที่ปริมาณเดิม
        self.items = [it for it in self.items if it[0] != ing["id"]]
        self.items.append((ing["id"], ing["name"], ing["unit"], qty))
        self.qty_var.set("")
        self.show_items()

    def remove_item(self):
        sel = self.tree_items.selection()
        if sel:
            del self.items[int(sel[0])]
            self.show_items()

    def save(self):
        try:
            self.menu_id = logic.save_menu(self.menu_id, self.code_var.get().strip(), self.name_var.get().strip(),
                            [(it[0], it[3]) for it in self.items])
            messagebox.showinfo("สำเร็จ", "บันทึกเมนูแล้ว")
            self.refresh()
        except logic.AppError as e:
            messagebox.showerror("ผิดพลาด", str(e))
