# widgets.py
# ฟังก์ชันช่วยสร้างหน้าจอที่ใช้ซ้ำหลายหน้า + สีของโปรแกรม

import math
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- สีที่ใช้ทั้งโปรแกรม ----------
GREEN = "#2e7d32"
GREEN_DARK = "#1b5e20"
GREEN_LIGHT = "#e8f5e9"
BG = "#f6f8f5"
RED = "#c62828"
RED_LIGHT = "#fdecea"
ORANGE = "#ef6c00"
ORANGE_LIGHT = "#fff3e0"
BLUE = "#1565c0"
GRAY = "#6b7280"
STRIPE = "#f3f6f2"


def setup_style(root):
    """ตั้งค่าหน้าตา ttk ทั้งโปรแกรม (เรียกครั้งเดียวตอนเปิดแอป)"""
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BG)

    style.configure(".", font=("Tahoma", 10), background=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG)
    style.configure("Head.TLabel", font=("Tahoma", 11, "bold"), foreground=GREEN_DARK)
    style.configure("Hint.TLabel", foreground=GRAY, font=("Tahoma", 9))
    style.configure("Warn.TLabel", foreground=RED, font=("Tahoma", 10, "bold"))
    style.configure("TLabelframe", background=BG, bordercolor="#c8d6c5")
    style.configure("TLabelframe.Label", background=BG, foreground=GREEN_DARK, font=("Tahoma", 10, "bold"))

    # ปุ่ม
    style.configure("TButton", padding=(10, 4))
    style.configure("Accent.TButton", background=GREEN, foreground="white", bordercolor=GREEN)
    style.map("Accent.TButton", background=[("active", GREEN_DARK), ("disabled", "#9ccc9c")])
    style.configure("Danger.TButton", background=RED, foreground="white", bordercolor=RED)
    style.map("Danger.TButton", background=[("active", "#8e0000")])

    # แท็บ
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 7), font=("Tahoma", 10), background="#dfe7dc")
    style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", GREEN_DARK)])

    # ตาราง
    style.configure("Treeview", rowheight=24, background="white", fieldbackground="white")
    style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"), background=GREEN_LIGHT,
                    foreground=GREEN_DARK, relief="flat")
    style.map("Treeview", background=[("selected", GREEN)], foreground=[("selected", "white")])
    style.map("Treeview.Heading", background=[("active", "#c8e6c9")])


class Table(ttk.Treeview):
    """Treeview ที่ทำแถวสลับสีให้เอง  ใส่ tag เพิ่มได้: warn (ส้ม) / danger (แดง) / good (เขียว)"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        # tag ที่สร้างก่อนมีความสำคัญกว่า จึงสร้าง odd (แถวสลับสี) ไว้หลังสุด
        self.tag_configure("danger", background=RED_LIGHT, foreground=RED)
        self.tag_configure("warn", background=ORANGE_LIGHT, foreground=ORANGE)
        self.tag_configure("good", foreground=GREEN)
        self.tag_configure("muted", foreground=GRAY)
        self.tag_configure("odd", background=STRIPE)

    def insert(self, parent, index, iid=None, **kw):
        tags = kw.pop("tags", ())
        if isinstance(tags, str):
            tags = (tags,)
        if len(self.get_children(parent)) % 2 == 1:
            tags = tuple(tags) + ("odd",)
        return super().insert(parent, index, iid=iid, tags=tags, **kw)


def make_table(parent, columns, widths=None, height=12):
    """สร้างตารางพร้อม scrollbar  columns = [(key, หัวตาราง)]"""
    frame = ttk.Frame(parent)
    tree = Table(frame, columns=[c[0] for c in columns], show="headings", height=height)
    for i, (key, title) in enumerate(columns):
        tree.heading(key, text=title)
        w = widths[i] if widths else 120
        tree.column(key, width=w, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tree


def make_card(parent, title, color):
    """การ์ดสรุปตัวเลขในหน้าหลัก คืน label ตัวเลขไว้เปลี่ยนค่า"""
    card = tk.Frame(parent, bg="white", highlightbackground="#dde5da", highlightthickness=1)
    tk.Frame(card, bg=color, width=6).pack(side="left", fill="y")
    inner = tk.Frame(card, bg="white", padx=14, pady=10)
    inner.pack(side="left", fill="both", expand=True)
    tk.Label(inner, text=title, bg="white", fg=GRAY, font=("Tahoma", 10)).pack(anchor="w")
    value = tk.Label(inner, text="-", bg="white", fg=color, font=("Tahoma", 22, "bold"))
    value.pack(anchor="w")
    return card, value


def clear_table(tree):
    for item in tree.get_children():
        tree.delete(item)


def selected_id(tree):
    """คืน iid ของแถวที่เลือก (เราตั้ง iid = id ในฐานข้อมูล)"""
    sel = tree.selection()
    if not sel:
        messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกรายการในตารางก่อน")
        return None
    return int(sel[0])


def to_float(text, name):
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        raise ValueError(f"{name} ต้องเป็นตัวเลข")
    if math.isnan(value) or math.isinf(value):     # กันพิมพ์ nan / inf
        raise ValueError(f"{name} ต้องเป็นตัวเลข")
    return value


class FormDialog(tk.Toplevel):
    """หน้าต่างฟอร์มแบบง่าย
    fields = [(key, label, options_or_None, default)]  ถ้ามี options จะเป็น combobox
    หลังปิดหน้าต่างอ่านค่าที่ self.result (dict) ถ้ากดยกเลิกจะเป็น None"""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.configure(background=BG)
        self.result = None
        self.vars = {}

        tk.Label(self, text=title, bg=GREEN, fg="white", font=("Tahoma", 11, "bold"),
                 anchor="w", padx=12, pady=6).pack(fill="x")
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        first = None
        for row, (key, label, options, default) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
            var = tk.StringVar(value="" if default is None else str(default))
            if options:
                w = ttk.Combobox(body, textvariable=var, values=options, state="readonly", width=32)
            else:
                w = ttk.Entry(body, textvariable=var, width=35)
            w.grid(row=row, column=1, pady=4)
            first = first or w
            self.vars[key] = var

        btns = ttk.Frame(body)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(btns, text="ยกเลิก", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="บันทึก", style="Accent.TButton", command=self.on_ok).pack(side="right", padx=4)
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())

        self.wait_visibility()
        self.grab_set()          # บังคับให้กรอกฟอร์มนี้ก่อน
        if first:
            first.focus_set()
        self.wait_window()

    def on_ok(self):
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.destroy()
