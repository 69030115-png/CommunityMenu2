# logic.py
# ส่วนประมวลผล: แปลงหน่วย, คลังแบบล็อต, คำนวณแผนเมนู, ต้นทุน, จัดซื้อ, รายงาน
# ตัวเลขทุกตัวคำนวณจากฐานข้อมูลที่นี่ (AI ไม่ได้คำนวณ)

from datetime import date, timedelta

from db import get_conn, today_str, now_str


class AppError(Exception):
    """ข้อผิดพลาดที่ต้องแจ้งผู้ใช้ เช่น ยอดไม่พอ, กดซ้ำ"""
    pass


# ---------------- หน่วย ----------------

WEIGHT_UNITS = {"กรัม": 1, "กก.": 1000}       # แปลงเป็นกรัม
COUNT_UNITS = ["ฟอง", "ชิ้น"]


def to_std(qty, from_unit, std_unit):
    """แปลงปริมาณเป็นหน่วยมาตรฐานของวัตถุดิบ
    - กก. -> กรัม ได้
    - ห้ามแปลงน้ำหนักเป็นจำนวนชิ้น (ไม่มีข้อมูลรองรับ)"""
    if from_unit == std_unit:
        return qty
    if from_unit in WEIGHT_UNITS and std_unit in WEIGHT_UNITS:
        return qty * WEIGHT_UNITS[from_unit] / WEIGHT_UNITS[std_unit]
    raise AppError(f"แปลงหน่วย {from_unit} เป็น {std_unit} ไม่ได้")


def fmt_qty(qty, unit):
    """แสดงผล เช่น 3000 กรัม -> 3 กก."""
    if unit == "กรัม" and abs(qty) >= 1000:
        return f"{qty / 1000:,.2f}".rstrip("0").rstrip(".") + " กก."
    return f"{qty:,.2f}".rstrip("0").rstrip(".") + " " + unit


# ---------------- วัตถุดิบ ----------------

def list_ingredients(keyword=""):
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, IFNULL(SUM(l.qty_left), 0) AS stock
        FROM ingredients i LEFT JOIN lots l ON l.ingredient_id = i.id AND l.qty_left > 0
        WHERE i.name LIKE ? OR i.code LIKE ?
        GROUP BY i.id ORDER BY i.code""", (f"%{keyword}%", f"%{keyword}%")).fetchall()
    conn.close()
    return rows


def get_ingredient(ing_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ingredients WHERE id=?", (ing_id,)).fetchone()
    conn.close()
    return row


def save_ingredient(ing_id, code, name, unit, min_stock, shelf_days):
    if not code or not name:
        raise AppError("กรุณากรอกรหัสและชื่อวัตถุดิบ")
    if unit not in ["กรัม"] + COUNT_UNITS:
        raise AppError("หน่วยมาตรฐานต้องเป็น กรัม / ฟอง / ชิ้น")
    if min_stock < 0 or shelf_days < 0:
        raise AppError("ขั้นต่ำและอายุต้องไม่ติดลบ")
    conn = get_conn()
    try:
        if ing_id:
            # ห้ามเปลี่ยนหน่วยถ้ามีล็อต/สูตร/ผลผลิตใช้อยู่แล้ว ไม่งั้นตัวเลขเดิมจะผิดความหมาย (เช่น 2000 กรัม กลายเป็น 2000 ฟอง)
            old = conn.execute("SELECT unit FROM ingredients WHERE id=?", (ing_id,)).fetchone()
            used = conn.execute("SELECT (SELECT COUNT(*) FROM lots WHERE ingredient_id=:i) + "
                                "(SELECT COUNT(*) FROM recipe_items WHERE ingredient_id=:i) + "
                                "(SELECT COUNT(*) FROM produce WHERE ingredient_id=:i)", {"i": ing_id}).fetchone()[0]
            if old["unit"] != unit and used:
                raise AppError(f"เปลี่ยนหน่วยไม่ได้ เพราะมีข้อมูลที่ใช้หน่วย {old['unit']} อยู่แล้ว")
            conn.execute("UPDATE ingredients SET code=?,name=?,unit=?,min_stock=?,shelf_days=? WHERE id=?",
                         (code, name, unit, min_stock, shelf_days, ing_id))
        else:
            conn.execute("INSERT INTO ingredients(code,name,unit,min_stock,shelf_days) VALUES (?,?,?,?,?)",
                         (code, name, unit, min_stock, shelf_days))
        conn.commit()
    except AppError:
        raise
    except Exception as e:
        raise AppError("บันทึกไม่ได้ (รหัสอาจซ้ำ): " + str(e))
    finally:
        conn.close()


def usable_stock(conn, ing_id):
    """ยอดคงเหลือที่ใช้ได้ = ล็อตที่ยังไม่เลยวันควรใช้ก่อน"""
    return conn.execute("SELECT IFNULL(SUM(qty_left),0) FROM lots WHERE ingredient_id=? AND qty_left>0 "
                        "AND use_by >= ?", (ing_id, today_str())).fetchone()[0]


def list_lots(ing_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM lots WHERE ingredient_id=? AND qty_left>0 "
                        "ORDER BY use_by, id", (ing_id,)).fetchall()
    conn.close()
    return rows


def list_movements(ing_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM movements WHERE ingredient_id=? ORDER BY id DESC",
                        (ing_id,)).fetchall()
    conn.close()
    return rows


# ---------------- รับเข้า / เบิก / ของเสีย / ปรับยอด ----------------

def receive_lot(conn, ing_id, qty, unit_cost, use_by, ref, note=""):
    """รับเข้าเป็นล็อตใหม่ (ใช้ conn ที่ส่งมา เพื่อให้อยู่ใน transaction เดียวกัน)"""
    if qty <= 0:
        raise AppError("จำนวนรับเข้าต้องมากกว่า 0")
    cur = conn.execute("INSERT INTO lots(ingredient_id,received_date,use_by,qty_left,unit_cost,note) "
                       "VALUES (?,?,?,?,?,?)", (ing_id, today_str(), use_by, qty, unit_cost, note))
    conn.execute("INSERT INTO movements(ingredient_id,lot_id,type,qty,unit_cost,created_at,ref) "
                 "VALUES (?,?,?,?,?,?,?)", (ing_id, cur.lastrowid, "IN", qty, unit_cost, now_str(), ref))


def receive_manual(ing_id, qty, unit_cost, use_by, note):
    conn = get_conn()
    try:
        receive_lot(conn, ing_id, qty, unit_cost, use_by, "รับเข้าเอง", note)
        conn.commit()
    finally:
        conn.close()


def suggest_lots(conn, ing_id, qty, only_usable=True):
    """เสนอล็อตที่ควรใช้ก่อน (วันควรใช้ก่อนเร็วสุดก่อน) คืนค่า [(lot, จำนวนที่จะเบิก)]
    ถ้าของไม่พอ -> AppError (ป้องกันยอดติดลบ)
    only_usable=True คือไม่เอาล็อตที่เลยวันควรใช้ก่อนแล้ว (ล็อตนั้นให้ผู้ใช้ตรวจและบันทึกของเสียเอง)"""
    min_date = today_str() if only_usable else "0000-00-00"
    lots = conn.execute("SELECT * FROM lots WHERE ingredient_id=? AND qty_left>0 AND use_by>=? "
                        "ORDER BY use_by, id", (ing_id, min_date)).fetchall()
    result = []
    remain = qty
    for lot in lots:
        if remain <= 0:
            break
        take = min(lot["qty_left"], remain)
        result.append((lot, take))
        remain -= take
    if remain > 1e-9:
        ing = conn.execute("SELECT name, unit FROM ingredients WHERE id=?", (ing_id,)).fetchone()
        raise AppError(f"{ing['name']} ในคลังไม่พอ ขาด {fmt_qty(remain, ing['unit'])}")
    return result


def issue(conn, ing_id, qty, mtype, ref, reason=""):
    """เบิกใช้ (USE) หรือของเสีย (WASTE) ตามล็อต"""
    if qty <= 0:
        raise AppError("จำนวนต้องมากกว่า 0")
    for lot, take in suggest_lots(conn, ing_id, qty, only_usable=(mtype == "USE")):
        conn.execute("UPDATE lots SET qty_left = qty_left - ? WHERE id=?", (take, lot["id"]))
        conn.execute("INSERT INTO movements(ingredient_id,lot_id,type,qty,unit_cost,created_at,ref,reason) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (ing_id, lot["id"], mtype, -take, lot["unit_cost"], now_str(), ref, reason))


def issue_manual(ing_id, qty, mtype, reason):
    conn = get_conn()
    try:
        issue(conn, ing_id, qty, mtype, "บันทึกเอง", reason)
        conn.commit()
    finally:
        conn.close()


def waste_lot(lot_id, qty, reason):
    """บันทึกของเสียจากล็อตที่ผู้ใช้เลือกเอง (หลังตรวจสภาพจริง)"""
    conn = get_conn()
    try:
        lot = conn.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        if qty <= 0 or qty > lot["qty_left"]:
            raise AppError("จำนวนของเสียต้องมากกว่า 0 และไม่เกินยอดในล็อต")
        conn.execute("UPDATE lots SET qty_left = qty_left - ? WHERE id=?", (qty, lot_id))
        conn.execute("INSERT INTO movements(ingredient_id,lot_id,type,qty,unit_cost,created_at,ref,reason) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (lot["ingredient_id"], lot_id, "WASTE", -qty, lot["unit_cost"], now_str(), "ของเสีย", reason))
        conn.commit()
    finally:
        conn.close()


def adjust_lot(lot_id, new_qty, reason):
    """ปรับยอดล็อต ต้องมีเหตุผลทุกครั้ง และเก็บประวัติ"""
    if not reason.strip():
        raise AppError("การปรับยอดต้องระบุเหตุผล")
    if new_qty < 0:
        raise AppError("ยอดใหม่ติดลบไม่ได้")
    conn = get_conn()
    try:
        lot = conn.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        diff = new_qty - lot["qty_left"]
        conn.execute("UPDATE lots SET qty_left=? WHERE id=?", (new_qty, lot_id))
        conn.execute("INSERT INTO movements(ingredient_id,lot_id,type,qty,unit_cost,created_at,ref,reason) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (lot["ingredient_id"], lot_id, "ADJUST", diff, lot["unit_cost"], now_str(), "ปรับยอด", reason))
        conn.commit()
    finally:
        conn.close()


# ---------------- เมนูและสูตร ----------------

def list_menus():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM menus ORDER BY code").fetchall()
    conn.close()
    return rows


def get_recipe(menu_id):
    conn = get_conn()
    rows = conn.execute("""SELECT r.*, i.name, i.unit FROM recipe_items r
                           JOIN ingredients i ON i.id = r.ingredient_id
                           WHERE r.menu_id=? ORDER BY r.id""", (menu_id,)).fetchall()
    conn.close()
    return rows


def save_menu(menu_id, code, name, items):
    """items = [(ingredient_id, qty_per_dish)]"""
    if not code or not name:
        raise AppError("กรุณากรอกรหัสและชื่อเมนู")
    if not items:
        raise AppError("สูตรต้องมีวัตถุดิบอย่างน้อย 1 รายการ")
    conn = get_conn()
    try:
        if menu_id:
            conn.execute("UPDATE menus SET code=?, name=? WHERE id=?", (code, name, menu_id))
            conn.execute("DELETE FROM recipe_items WHERE menu_id=?", (menu_id,))
        else:
            menu_id = conn.execute("INSERT INTO menus(code,name) VALUES (?,?)", (code, name)).lastrowid
        for ing_id, qty in items:
            if qty <= 0:
                raise AppError("ปริมาณต่อจานต้องมากกว่า 0")
            conn.execute("INSERT INTO recipe_items(menu_id,ingredient_id,qty_per_dish) VALUES (?,?,?)",
                         (menu_id, ing_id, qty))
        conn.commit()
        return menu_id
    except AppError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise AppError("บันทึกเมนูไม่ได้ (รหัสอาจซ้ำ): " + str(e))
    finally:
        conn.close()


# ---------------- เกษตรกรและผลผลิต ----------------

def list_farmers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM farmers ORDER BY id").fetchall()
    conn.close()
    return rows


def save_farmer(fid, name, area, contact):
    if not name:
        raise AppError("กรุณากรอกชื่อเกษตรกร/กลุ่ม")
    conn = get_conn()
    if fid:
        conn.execute("UPDATE farmers SET name=?,area=?,contact=? WHERE id=?", (name, area, contact, fid))
    else:
        conn.execute("INSERT INTO farmers(name,area,contact) VALUES (?,?,?)", (name, area, contact))
    conn.commit()
    conn.close()


def list_produce():
    conn = get_conn()
    rows = conn.execute("""SELECT p.*, f.name AS farmer, i.name AS ing_name, i.unit AS std_unit
                           FROM produce p JOIN farmers f ON f.id=p.farmer_id
                           JOIN ingredients i ON i.id=p.ingredient_id
                           ORDER BY i.name, p.price""").fetchall()
    conn.close()
    return rows


def save_produce(pid, farmer_id, ing_id, price, sell_unit, qty, ready_date):
    ing = get_ingredient(ing_id)
    to_std(1, sell_unit, ing["unit"])         # ตรวจว่าหน่วยขายแปลงได้
    if price <= 0 or qty < 0:
        raise AppError("ราคาต้องมากกว่า 0 และปริมาณต้องไม่ติดลบ")
    conn = get_conn()
    if pid:
        conn.execute("UPDATE produce SET farmer_id=?,ingredient_id=?,price=?,sell_unit=?,qty_available=?,"
                     "ready_date=?,updated_at=? WHERE id=?",
                     (farmer_id, ing_id, price, sell_unit, qty, ready_date, now_str(), pid))
    else:
        conn.execute("INSERT INTO produce(farmer_id,ingredient_id,price,sell_unit,qty_available,ready_date,updated_at) "
                     "VALUES (?,?,?,?,?,?,?)", (farmer_id, ing_id, price, sell_unit, qty, ready_date, now_str()))
    conn.commit()
    conn.close()


def best_offer(conn, ing_id):
    """หาผู้ขายที่ถูกที่สุดที่พร้อมส่งภายในวันนี้ คืน dict ราคา/ปริมาณเป็นหน่วยมาตรฐาน"""
    rows = conn.execute("""SELECT p.*, f.name AS farmer, i.unit AS std_unit FROM produce p
                           JOIN farmers f ON f.id=p.farmer_id JOIN ingredients i ON i.id=p.ingredient_id
                           WHERE p.ingredient_id=? AND p.qty_available>0 AND p.ready_date<=?""",
                        (ing_id, today_str())).fetchall()
    best = None
    for r in rows:
        factor = to_std(1, r["sell_unit"], r["std_unit"])     # 1 หน่วยขาย = กี่หน่วยมาตรฐาน
        offer = {"produce_id": r["id"], "farmer_id": r["farmer_id"], "farmer": r["farmer"],
                 "price_std": r["price"] / factor, "qty_std": r["qty_available"] * factor,
                 "updated_at": r["updated_at"]}
        if best is None or offer["price_std"] < best["price_std"]:
            best = offer
    return best


# ---------------- คำนวณแผนเมนู ----------------

def calc_plan(plan_items):
    """plan_items = [(menu_id, dishes)]
    1) ปริมาณที่ต้องใช้ = ปริมาณต่อจาน x จำนวนจาน
    2) รวมวัตถุดิบเดียวกันจากทุกเมนูก่อน แล้วค่อยหักคลัง
    3) ซื้อเพิ่ม = max(0, ต้องใช้ - คงเหลือที่ใช้ได้)
    คืนค่า (รายการต่อวัตถุดิบ, สรุป)"""
    conn = get_conn()
    need = {}
    for menu_id, dishes in plan_items:
        if dishes <= 0:
            raise AppError("จำนวนจานต้องมากกว่า 0")
        for r in conn.execute("SELECT ingredient_id, qty_per_dish FROM recipe_items WHERE menu_id=?", (menu_id,)):
            need[r["ingredient_id"]] = need.get(r["ingredient_id"], 0) + r["qty_per_dish"] * dishes

    lines = []
    stock_cost = 0
    buy_cost = 0
    problems = []
    for ing_id, qty_need in need.items():
        ing = conn.execute("SELECT * FROM ingredients WHERE id=?", (ing_id,)).fetchone()
        have = usable_stock(conn, ing_id)
        use_from_stock = min(have, qty_need)
        buy = max(0, qty_need - have)

        # ต้นทุนส่วนที่เบิกจากคลัง คิดตามล็อตที่ใช้ก่อน
        cost_s = 0
        remain = use_from_stock
        for lot in conn.execute("SELECT * FROM lots WHERE ingredient_id=? AND qty_left>0 AND use_by>=? "
                                "ORDER BY use_by, id", (ing_id, today_str())):
            if remain <= 0:
                break
            take = min(lot["qty_left"], remain)
            cost_s += take * lot["unit_cost"]
            remain -= take

        offer = None
        cost_b = 0
        if buy > 0:
            offer = best_offer(conn, ing_id)
            if offer is None:
                problems.append(f"{ing['name']}: ไม่มีผู้ขายที่พร้อมส่ง (ขาด {fmt_qty(buy, ing['unit'])})")
            else:
                cost_b = buy * offer["price_std"]
                if offer["qty_std"] < buy:
                    problems.append(f"{ing['name']}: ผู้ขายมีไม่พอ (มี {fmt_qty(offer['qty_std'], ing['unit'])})")

        stock_cost += cost_s
        buy_cost += cost_b
        lines.append({"ingredient_id": ing_id, "name": ing["name"], "unit": ing["unit"],
                      "need": qty_need, "have": have, "buy": buy,
                      "stock_cost": cost_s, "buy_cost": cost_b, "offer": offer})
    conn.close()
    lines.sort(key=lambda x: x["name"])
    summary = {"stock_cost": stock_cost, "buy_cost": buy_cost,
               "total_cost": stock_cost + buy_cost, "problems": problems}
    return lines, summary


def create_plan(plan_items, budget):
    conn = get_conn()
    pid = conn.execute("INSERT INTO menu_plans(plan_date,budget,status,created_at) VALUES (?,?,?,?)",
                       (today_str(), budget, "CONFIRMED", now_str())).lastrowid
    for menu_id, dishes in plan_items:
        conn.execute("INSERT INTO plan_items(plan_id,menu_id,dishes) VALUES (?,?,?)", (pid, menu_id, dishes))
    conn.commit()
    conn.close()
    return pid


def list_plans():
    conn = get_conn()
    rows = conn.execute("""SELECT p.*, GROUP_CONCAT(m.name || ' x' || pi.dishes, ', ') AS menus
                           FROM menu_plans p JOIN plan_items pi ON pi.plan_id=p.id
                           JOIN menus m ON m.id=pi.menu_id
                           GROUP BY p.id ORDER BY p.id DESC""").fetchall()
    conn.close()
    return rows


def get_plan_items(plan_id):
    conn = get_conn()
    rows = conn.execute("SELECT menu_id, dishes FROM plan_items WHERE plan_id=?", (plan_id,)).fetchall()
    conn.close()
    return [(r["menu_id"], r["dishes"]) for r in rows]


def use_plan(plan_id):
    """เบิกวัตถุดิบตามแผน ทั้งหมดใน transaction เดียว ถ้าตัวไหนไม่พอจะไม่เบิกเลย"""
    conn = get_conn()
    try:
        plan = conn.execute("SELECT * FROM menu_plans WHERE id=?", (plan_id,)).fetchone()
        if plan["status"] == "USED":
            raise AppError("แผนนี้เบิกวัตถุดิบไปแล้ว (ป้องกันเบิกซ้ำ)")
        need = {}
        for r in conn.execute("""SELECT r.ingredient_id, r.qty_per_dish * pi.dishes AS q
                                 FROM plan_items pi JOIN recipe_items r ON r.menu_id=pi.menu_id
                                 WHERE pi.plan_id=?""", (plan_id,)):
            need[r["ingredient_id"]] = need.get(r["ingredient_id"], 0) + r["q"]
        for ing_id, q in need.items():
            issue(conn, ing_id, q, "USE", f"แผนเมนู #{plan_id}")
        conn.execute("UPDATE menu_plans SET status='USED' WHERE id=?", (plan_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- จัดซื้อ ----------------

def create_po(farmer_id, items, plan_id=None):
    """items = [(ingredient_id, qty_std, unit_price_std)]"""
    if not items:
        raise AppError("คำสั่งซื้อต้องมีอย่างน้อย 1 รายการ")
    conn = get_conn()
    po_id = conn.execute("INSERT INTO purchase_orders(farmer_id,plan_id,created_at,status) VALUES (?,?,?,?)",
                         (farmer_id, plan_id, now_str(), "PENDING")).lastrowid
    for ing_id, qty, price in items:
        conn.execute("INSERT INTO po_items(po_id,ingredient_id,qty,unit_price) VALUES (?,?,?,?)",
                     (po_id, ing_id, qty, price))
    conn.commit()
    conn.close()
    return po_id


def create_po_from_plan(lines, plan_id=None):
    """แยกรายการซื้อเพิ่มตามผู้ขายที่ถูกสุด แล้วสร้างคำสั่งซื้อละ 1 ราย"""
    by_farmer = {}
    for ln in lines:
        if ln["buy"] > 0 and ln["offer"]:
            by_farmer.setdefault(ln["offer"]["farmer_id"], []).append(
                (ln["ingredient_id"], ln["buy"], ln["offer"]["price_std"]))
    return [create_po(fid, items, plan_id) for fid, items in by_farmer.items()]


def list_pos(status=None):
    conn = get_conn()
    sql = """SELECT po.*, f.name AS farmer, IFNULL(SUM(it.qty*it.unit_price),0) AS total
             FROM purchase_orders po JOIN farmers f ON f.id=po.farmer_id
             LEFT JOIN po_items it ON it.po_id=po.id"""
    args = ()
    if status:
        sql += " WHERE po.status=?"
        args = (status,)
    sql += " GROUP BY po.id ORDER BY po.id DESC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return rows


def get_po_items(po_id):
    conn = get_conn()
    rows = conn.execute("""SELECT it.*, i.name, i.unit FROM po_items it
                           JOIN ingredients i ON i.id=it.ingredient_id WHERE po_id=?""", (po_id,)).fetchall()
    conn.close()
    return rows


def reduce_produce(conn, farmer_id, ing_id, qty_std):
    """หักปริมาณพร้อมขายของเกษตรกรรายนั้นหลังรับสินค้า (ไม่ให้ติดลบ)"""
    rows = conn.execute("""SELECT p.*, i.unit AS std_unit FROM produce p JOIN ingredients i ON i.id=p.ingredient_id
                           WHERE p.farmer_id=? AND p.ingredient_id=? AND p.qty_available>0 ORDER BY p.id""",
                        (farmer_id, ing_id)).fetchall()
    remain = qty_std
    for r in rows:
        if remain <= 0:
            break
        factor = to_std(1, r["sell_unit"], r["std_unit"])
        have_std = r["qty_available"] * factor
        take = min(have_std, remain)
        conn.execute("UPDATE produce SET qty_available=?, updated_at=? WHERE id=?",
                     ((have_std - take) / factor, now_str(), r["id"]))
        remain -= take


def receive_po(po_id):
    """รับสินค้า -> สร้างล็อตใหม่เข้าคลัง ตรวจสถานะก่อน ป้องกันรับซ้ำ"""
    conn = get_conn()
    try:
        po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        if po["status"] != "PENDING":
            status_th = {"RECEIVED": "รับสินค้าไปแล้ว", "CANCELLED": "ถูกยกเลิกแล้ว"}.get(po["status"], po["status"])
            raise AppError(f"คำสั่งซื้อ #{po_id} {status_th} รับสินค้าซ้ำไม่ได้")
        for it in conn.execute("""SELECT it.*, i.shelf_days FROM po_items it
                                  JOIN ingredients i ON i.id=it.ingredient_id WHERE po_id=?""", (po_id,)).fetchall():
            use_by = (date.today() + timedelta(days=it["shelf_days"])).isoformat()
            receive_lot(conn, it["ingredient_id"], it["qty"], it["unit_price"], use_by,
                        f"คำสั่งซื้อ #{po_id}", "รับจากคำสั่งซื้อ")
            reduce_produce(conn, po["farmer_id"], it["ingredient_id"], it["qty"])
        conn.execute("UPDATE purchase_orders SET status='RECEIVED', received_at=? WHERE id=?", (now_str(), po_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_po(po_id):
    conn = get_conn()
    po = conn.execute("SELECT status FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
    if po["status"] != "PENDING":
        conn.close()
        raise AppError("ยกเลิกได้เฉพาะคำสั่งซื้อที่ยังรอรับ")
    conn.execute("UPDATE purchase_orders SET status='CANCELLED' WHERE id=?", (po_id,))
    conn.commit()
    conn.close()


# ---------------- หน้าหลัก / รายงาน ----------------

def dashboard():
    conn = get_conn()
    low = conn.execute("""SELECT i.name, i.unit, i.min_stock, IFNULL(SUM(l.qty_left),0) AS stock
                          FROM ingredients i LEFT JOIN lots l ON l.ingredient_id=i.id AND l.qty_left>0
                          GROUP BY i.id HAVING stock < i.min_stock ORDER BY i.name""").fetchall()
    soon = (date.today() + timedelta(days=2)).isoformat()
    near = conn.execute("""SELECT i.name, i.unit, l.qty_left, l.use_by FROM lots l
                           JOIN ingredients i ON i.id=l.ingredient_id
                           WHERE l.qty_left>0 AND l.use_by<=? ORDER BY l.use_by""", (soon,)).fetchall()
    conn.close()
    return low, near, list_pos("PENDING")


def report(date_from, date_to):
    """สรุปตามช่วงวันที่ (YYYY-MM-DD)"""
    conn = get_conn()
    d1, d2 = date_from, date_to + " 23:59:59"
    buy = conn.execute("""SELECT f.name AS farmer, COUNT(DISTINCT po.id) AS n, SUM(it.qty*it.unit_price) AS total
                          FROM purchase_orders po JOIN farmers f ON f.id=po.farmer_id
                          JOIN po_items it ON it.po_id=po.id
                          WHERE po.status='RECEIVED' AND po.received_at BETWEEN ? AND ?
                          GROUP BY f.id ORDER BY total DESC""", (d1, d2)).fetchall()
    moves = conn.execute("""SELECT i.name, i.unit, m.type, SUM(-m.qty) AS qty, SUM(-m.qty*m.unit_cost) AS value
                            FROM movements m JOIN ingredients i ON i.id=m.ingredient_id
                            WHERE m.type IN ('USE','WASTE') AND m.created_at BETWEEN ? AND ?
                            GROUP BY i.id, m.type ORDER BY m.type, i.name""", (d1, d2)).fetchall()
    conn.close()
    return buy, moves
