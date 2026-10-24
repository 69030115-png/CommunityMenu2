# db.py
# จัดการฐานข้อมูล SQLite: สร้างตาราง + ใส่ข้อมูลจำลองสำหรับเดโม

import os
import sys
import sqlite3
from datetime import date, datetime, timedelta

# ถ้าเป็นไฟล์ .exe (PyInstaller) ให้เก็บฐานข้อมูลไว้ข้างไฟล์ .exe
# ไม่งั้นจะไปอยู่ในโฟลเดอร์ชั่วคราวที่ถูกลบทุกครั้งที่ปิดโปรแกรม
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(APP_DIR, "community_menu.db")


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row      # ให้เรียก row["name"] ได้
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_tables():
    conn = get_conn()
    c = conn.cursor()

    # วัตถุดิบ  unit = หน่วยมาตรฐาน (กรัม / ฟอง / ชิ้น)
    c.execute("""CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        unit TEXT NOT NULL,
        min_stock REAL DEFAULT 0,
        shelf_days INTEGER DEFAULT 7
    )""")

    # ล็อตวัตถุดิบ (ราคาต่อหน่วยมาตรฐาน)
    c.execute("""CREATE TABLE IF NOT EXISTS lots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
        received_date TEXT NOT NULL,
        use_by TEXT NOT NULL,
        qty_left REAL NOT NULL,
        unit_cost REAL NOT NULL,
        note TEXT
    )""")

    # ประวัติเคลื่อนไหว  type = IN / USE / WASTE / ADJUST
    c.execute("""CREATE TABLE IF NOT EXISTS movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
        lot_id INTEGER REFERENCES lots(id),
        type TEXT NOT NULL,
        qty REAL NOT NULL,
        unit_cost REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        ref TEXT,
        reason TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
    )""")

    # สูตร: ปริมาณต่อ 1 จาน (หน่วยมาตรฐาน)
    c.execute("""CREATE TABLE IF NOT EXISTS recipe_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_id INTEGER NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
        ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
        qty_per_dish REAL NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        area TEXT,
        contact TEXT
    )""")

    # ผลผลิตพร้อมขาย  sell_unit = หน่วยที่เกษตรกรขาย (กก. / กรัม / ฟอง / ชิ้น)
    c.execute("""CREATE TABLE IF NOT EXISTS produce (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
        ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
        price REAL NOT NULL,
        sell_unit TEXT NOT NULL,
        qty_available REAL NOT NULL,
        ready_date TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")

    # แผนเมนู  status = DRAFT / CONFIRMED / USED
    c.execute("""CREATE TABLE IF NOT EXISTS menu_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_date TEXT NOT NULL,
        budget REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL REFERENCES menu_plans(id) ON DELETE CASCADE,
        menu_id INTEGER NOT NULL REFERENCES menus(id),
        dishes INTEGER NOT NULL
    )""")

    # คำสั่งซื้อ  status = PENDING / RECEIVED / CANCELLED
    c.execute("""CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER NOT NULL REFERENCES farmers(id),
        plan_id INTEGER REFERENCES menu_plans(id),
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        received_at TEXT
    )""")
    # qty / unit_price เก็บเป็นหน่วยมาตรฐาน
    c.execute("""CREATE TABLE IF NOT EXISTS po_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
        ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
        qty REAL NOT NULL,
        unit_price REAL NOT NULL
    )""")

    conn.commit()
    conn.close()


def is_empty():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
    conn.close()
    return n == 0


def seed_demo_data():
    """ใส่ข้อมูลจำลอง (ไม่ใช่ข้อมูลจริงของร้าน) วัตถุดิบ 20 / สูตร 10 / เกษตรกร 5"""
    conn = get_conn()
    c = conn.cursor()
    t = date.today()

    def d(days):
        return (t + timedelta(days=days)).isoformat()

    # (code, name, unit, min_stock, shelf_days)
    ingredients = [
        ("I01", "ฟักทอง", "กรัม", 1000, 10),
        ("I02", "ไข่ไก่", "ฟอง", 30, 14),
        ("I03", "กระเทียม", "กรัม", 200, 30),
        ("I04", "น้ำมันพืช", "กรัม", 500, 180),
        ("I05", "ซอสหอยนางรม", "กรัม", 300, 180),
        ("I06", "ผักบุ้ง", "กรัม", 500, 3),
        ("I07", "หมูสับ", "กรัม", 500, 3),
        ("I08", "อกไก่", "กรัม", 500, 3),
        ("I09", "ข้าวสาร", "กรัม", 5000, 180),
        ("I10", "ใบกะเพรา", "กรัม", 100, 3),
        ("I11", "พริกขี้หนู", "กรัม", 100, 7),
        ("I12", "คะน้า", "กรัม", 500, 4),
        ("I13", "มะเขือเทศ", "กรัม", 300, 7),
        ("I14", "หอมหัวใหญ่", "กรัม", 300, 20),
        ("I15", "เต้าหู้ไข่", "ชิ้น", 10, 7),
        ("I16", "ถั่วฝักยาว", "กรัม", 300, 5),
        ("I17", "ตำลึง", "กรัม", 200, 3),
        ("I18", "น้ำปลา", "กรัม", 300, 365),
        ("I19", "น้ำตาลทราย", "กรัม", 300, 365),
        ("I20", "แตงกวา", "กรัม", 300, 5),
    ]
    c.executemany("INSERT INTO ingredients(code,name,unit,min_stock,shelf_days) VALUES (?,?,?,?,?)",
                  ingredients)
    ing = {row["name"]: row["id"] for row in c.execute("SELECT id,name FROM ingredients")}

    # ล็อตเริ่มต้น (ชื่อ, รับเข้าเมื่อกี่วันก่อน, ใช้ก่อนอีกกี่วัน, จำนวน, ราคา/หน่วยมาตรฐาน)
    lots = [
        ("ฟักทอง", -6, 2, 2000, 0.03),       # 2 กก. ใกล้วันควรใช้ก่อน
        ("ไข่ไก่", -3, 10, 20, 5),
        ("กระเทียม", -10, 20, 1000, 0.08),
        ("น้ำมันพืช", -20, 150, 3000, 0.05),
        ("ซอสหอยนางรม", -20, 150, 2000, 0.09),
        ("ผักบุ้ง", -1, 1, 600, 0.03),
        ("หมูสับ", -1, 2, 1500, 0.14),
        ("อกไก่", -1, 2, 400, 0.11),
        ("ข้าวสาร", -15, 150, 10000, 0.03),
        ("ใบกะเพรา", -1, 2, 150, 0.06),
        ("พริกขี้หนู", -2, 5, 200, 0.1),
        ("คะน้า", -2, 2, 300, 0.04),
        ("มะเขือเทศ", -2, 5, 800, 0.04),
        ("หอมหัวใหญ่", -5, 15, 1000, 0.04),
        ("เต้าหู้ไข่", -2, 5, 8, 10),
        ("ถั่วฝักยาว", -1, 4, 500, 0.04),
        ("น้ำปลา", -30, 300, 1500, 0.05),
        ("น้ำตาลทราย", -30, 300, 2000, 0.03),
        ("แตงกวา", -1, 4, 200, 0.03),
    ]
    for name, recv, useby, qty, cost in lots:
        c.execute("INSERT INTO lots(ingredient_id,received_date,use_by,qty_left,unit_cost,note) "
                  "VALUES (?,?,?,?,?,?)", (ing[name], d(recv), d(useby), qty, cost, "ข้อมูลจำลอง"))
        c.execute("INSERT INTO movements(ingredient_id,lot_id,type,qty,unit_cost,created_at,ref,reason) "
                  "VALUES (?,?,?,?,?,?,?,?)",
                  (ing[name], c.lastrowid, "IN", qty, cost, d(recv) + " 08:00:00", "ยอดยกมา", "ข้อมูลจำลอง"))

    # เมนู + สูตรต่อ 1 จาน
    menus = {
        ("M01", "ฟักทองผัดไข่"): [("ฟักทอง", 100), ("ไข่ไก่", 1), ("กระเทียม", 5), ("น้ำมันพืช", 10), ("ซอสหอยนางรม", 10)],
        ("M02", "ผัดผักบุ้งไฟแดง"): [("ผักบุ้ง", 150), ("กระเทียม", 5), ("พริกขี้หนู", 3), ("น้ำมันพืช", 10), ("ซอสหอยนางรม", 15)],
        ("M03", "ข้าวกะเพราหมูสับ"): [("หมูสับ", 100), ("ใบกะเพรา", 10), ("พริกขี้หนู", 5), ("กระเทียม", 5), ("ข้าวสาร", 120), ("น้ำมันพืช", 10), ("น้ำปลา", 10)],
        ("M04", "ไข่เจียวหมูสับ"): [("ไข่ไก่", 2), ("หมูสับ", 40), ("น้ำมันพืช", 30), ("น้ำปลา", 5)],
        ("M05", "ผัดคะน้าหมูสับ"): [("คะน้า", 150), ("หมูสับ", 60), ("กระเทียม", 5), ("ซอสหอยนางรม", 15), ("น้ำมันพืช", 10)],
        ("M06", "ไก่ผัดมะเขือเทศ"): [("อกไก่", 100), ("มะเขือเทศ", 80), ("หอมหัวใหญ่", 40), ("น้ำมันพืช", 10), ("น้ำตาลทราย", 5)],
        ("M07", "แกงจืดเต้าหู้หมูสับ"): [("เต้าหู้ไข่", 1), ("หมูสับ", 50), ("ตำลึง", 30), ("น้ำปลา", 10)],
        ("M08", "ผัดถั่วฝักยาวหมูสับ"): [("ถั่วฝักยาว", 120), ("หมูสับ", 50), ("กระเทียม", 5), ("น้ำปลา", 10), ("น้ำมันพืช", 10)],
        ("M09", "ไข่ผัดมะเขือเทศ"): [("ไข่ไก่", 2), ("มะเขือเทศ", 100), ("หอมหัวใหญ่", 30), ("น้ำมันพืช", 10), ("น้ำตาลทราย", 5)],
        ("M10", "แกงจืดฟักทองหมูสับ"): [("ฟักทอง", 120), ("หมูสับ", 50), ("น้ำปลา", 10)],
    }
    for (code, name), items in menus.items():
        c.execute("INSERT INTO menus(code,name) VALUES (?,?)", (code, name))
        mid = c.lastrowid
        for ing_name, qty in items:
            c.execute("INSERT INTO recipe_items(menu_id,ingredient_id,qty_per_dish) VALUES (?,?,?)",
                      (mid, ing[ing_name], qty))

    # เกษตรกรจำลอง
    farmers = [
        ("กลุ่มเกษตรกรบ้านหนองบัว (จำลอง)", "ต.หนองบัว", "081-000-0001"),
        ("ฟาร์มไข่ลุงชัย (จำลอง)", "ต.ท่าช้าง", "081-000-0002"),
        ("สวนผักป้าแดง (จำลอง)", "ต.บ้านใหม่", "081-000-0003"),
        ("วิสาหกิจชุมชนผักปลอดภัย (จำลอง)", "ต.โนนสูง", "081-000-0004"),
        ("ฟาร์มหมูพี่เอก (จำลอง)", "ต.หนองบัว", "081-000-0005"),
    ]
    c.executemany("INSERT INTO farmers(name,area,contact) VALUES (?,?,?)", farmers)
    fid = [row["id"] for row in c.execute("SELECT id FROM farmers ORDER BY id")]

    # ผลผลิตพร้อมขาย (เกษตรกร, วัตถุดิบ, ราคา, หน่วยขาย, ปริมาณ, พร้อมส่งอีกกี่วัน)
    produce = [
        (0, "ฟักทอง", 30, "กก.", 50, 0),
        (2, "ฟักทอง", 35, "กก.", 20, 1),
        (1, "ไข่ไก่", 5, "ฟอง", 300, 0),
        (3, "ไข่ไก่", 5.5, "ฟอง", 200, 0),
        (2, "ผักบุ้ง", 30, "กก.", 15, 0),
        (2, "คะน้า", 40, "กก.", 10, 0),
        (3, "ถั่วฝักยาว", 40, "กก.", 10, 1),
        (3, "ตำลึง", 50, "กก.", 5, 0),
        (3, "มะเขือเทศ", 40, "กก.", 15, 0),
        (0, "แตงกวา", 25, "กก.", 20, 0),
        (4, "หมูสับ", 140, "กก.", 30, 0),
        (0, "ใบกะเพรา", 60, "กก.", 3, 0),
    ]
    for f, name, price, unit, qty, ready in produce:
        c.execute("INSERT INTO produce(farmer_id,ingredient_id,price,sell_unit,qty_available,ready_date,updated_at) "
                  "VALUES (?,?,?,?,?,?,?)", (fid[f], ing[name], price, unit, qty, d(ready), now_str()))

    # ประวัติซื้อย้อนหลัง (รับแล้ว) เพื่อให้รายงานมีข้อมูล
    history = [(1, -7, "ไข่ไก่", 60, 5), (2, -5, "ผักบุ้ง", 2000, 0.03), (4, -3, "หมูสับ", 3000, 0.14)]
    for f, day, name, qty, price in history:
        c.execute("INSERT INTO purchase_orders(farmer_id,created_at,status,received_at) VALUES (?,?,?,?)",
                  (fid[f], d(day) + " 09:00:00", "RECEIVED", d(day) + " 15:00:00"))
        c.execute("INSERT INTO po_items(po_id,ingredient_id,qty,unit_price) VALUES (?,?,?,?)",
                  (c.lastrowid, ing[name], qty, price))

    conn.commit()
    conn.close()


def init_db():
    create_tables()
    if is_empty():
        seed_demo_data()


if __name__ == "__main__":
    # รันไฟล์นี้ตรง ๆ เพื่อลบแล้วสร้างฐานข้อมูลเดโมใหม่
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    init_db()
    print("สร้างฐานข้อมูลเดโมแล้ว:", DB_FILE)
