# test_logic.py
# ทดสอบส่วนคำนวณ  รัน: python -m unittest -v test_logic.py
# ใช้ฐานข้อมูลชั่วคราว ไม่ยุ่งกับฐานข้อมูลจริง

import os
import tempfile
import unittest

import db
import logic
import ai_helper


def ing_id(name):
    conn = db.get_conn()
    i = conn.execute("SELECT id FROM ingredients WHERE name=?", (name,)).fetchone()["id"]
    conn.close()
    return i


def menu_id(code):
    conn = db.get_conn()
    i = conn.execute("SELECT id FROM menus WHERE code=?", (code,)).fetchone()["id"]
    conn.close()
    return i


def stock(name):
    conn = db.get_conn()
    s = logic.usable_stock(conn, ing_id(name))
    conn.close()
    return s


class TestLogic(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.path)
        db.DB_FILE = self.path
        db.init_db()

    def tearDown(self):
        os.remove(self.path)

    # ----- แปลงหน่วย -----
    def test_unit_kg_to_g(self):
        self.assertEqual(logic.to_std(3, "กก.", "กรัม"), 3000)

    def test_unit_weight_to_piece_not_allowed(self):
        with self.assertRaises(logic.AppError):
            logic.to_std(100, "กรัม", "ฟอง")

    # ----- ตัวอย่างในเอกสาร: ฟักทองผัดไข่ 30 จาน -----
    def test_demo_pumpkin_egg_30(self):
        lines, s = logic.calc_plan([(menu_id("M01"), 30)])
        d = {ln["name"]: ln for ln in lines}
        self.assertEqual(d["ฟักทอง"]["need"], 3000)
        self.assertEqual(d["ฟักทอง"]["have"], 2000)
        self.assertEqual(d["ฟักทอง"]["buy"], 1000)
        self.assertEqual(d["ไข่ไก่"]["need"], 30)
        self.assertEqual(d["ไข่ไก่"]["have"], 20)
        self.assertEqual(d["ไข่ไก่"]["buy"], 10)
        self.assertAlmostEqual(s["buy_cost"], 80)            # 1 กก. x 30 + 10 ฟอง x 5

    def test_combine_menus_before_deduct(self):
        # ฟักทองผัดไข่ 30 จาน (3000 g) + แกงจืดฟักทอง 10 จาน (1200 g) = 4200 g
        lines, s = logic.calc_plan([(menu_id("M01"), 30), (menu_id("M10"), 10)])
        pumpkin = [ln for ln in lines if ln["name"] == "ฟักทอง"][0]
        self.assertEqual(pumpkin["need"], 4200)
        self.assertEqual(pumpkin["buy"], 2200)

    # ----- คลัง -----
    def test_issue_more_than_stock(self):
        before = stock("ไข่ไก่")
        with self.assertRaises(logic.AppError):
            logic.issue_manual(ing_id("ไข่ไก่"), before + 1, "USE", "")
        self.assertEqual(stock("ไข่ไก่"), before)            # ยอดไม่เปลี่ยน ไม่ติดลบ

    def test_issue_oldest_lot_first(self):
        egg = ing_id("ไข่ไก่")
        conn = db.get_conn()
        logic.receive_lot(conn, egg, 50, 5, "2099-01-01", "test")
        conn.commit()
        conn.close()
        logic.issue_manual(egg, 5, "USE", "")
        lots = logic.list_lots(egg)
        self.assertEqual(lots[0]["qty_left"], 15)              # ล็อตเก่าถูกเบิกก่อน
        self.assertEqual(lots[1]["qty_left"], 50)

    def test_adjust_needs_reason(self):
        lot = logic.list_lots(ing_id("ฟักทอง"))[0]
        with self.assertRaises(logic.AppError):
            logic.adjust_lot(lot["id"], 1500, "   ")

    # ----- จัดซื้อ -----
    def test_receive_po_updates_stock_and_no_double(self):
        lines, _ = logic.calc_plan([(menu_id("M01"), 30)])
        po_ids = logic.create_po_from_plan(lines)
        for p in po_ids:
            logic.receive_po(p)
        self.assertEqual(stock("ฟักทอง"), 3000)
        self.assertEqual(stock("ไข่ไก่"), 30)
        with self.assertRaises(logic.AppError):
            logic.receive_po(po_ids[0])                        # รับซ้ำไม่ได้
        self.assertEqual(stock("ฟักทอง"), 3000)

    def test_use_plan_no_double(self):
        pid = logic.create_plan([(menu_id("M02"), 2)], 0)
        logic.use_plan(pid)
        with self.assertRaises(logic.AppError):
            logic.use_plan(pid)

    def test_use_plan_not_enough_rolls_back(self):
        pid = logic.create_plan([(menu_id("M01"), 30)], 0)     # ฟักทองไม่พอ
        egg_before = stock("ไข่ไก่")
        with self.assertRaises(logic.AppError):
            logic.use_plan(pid)
        self.assertEqual(stock("ไข่ไก่"), egg_before)        # ไม่มีอะไรถูกเบิกไปบางส่วน

    def test_receive_po_reduces_produce(self):
        conn = db.get_conn()
        before = conn.execute("SELECT qty_available FROM produce WHERE price=30 AND sell_unit='กก.'").fetchone()[0]
        conn.close()
        lines, _ = logic.calc_plan([(menu_id("M01"), 30)])     # ซื้อฟักทอง 1 กก. จากเจ้าที่ 30 บาท
        for p in logic.create_po_from_plan(lines):
            logic.receive_po(p)
        conn = db.get_conn()
        after = conn.execute("SELECT qty_available FROM produce WHERE price=30 AND sell_unit='กก.'").fetchone()[0]
        conn.close()
        self.assertAlmostEqual(before - after, 1)

    def test_cannot_change_unit_when_used(self):
        ing = logic.get_ingredient(ing_id("ฟักทอง"))
        with self.assertRaises(logic.AppError):
            logic.save_ingredient(ing["id"], ing["code"], ing["name"], "ฟอง", 0, 7)

    # ----- ตรวจคำตอบ AI -----
    def test_ai_answer_wrong_item_types(self):
        result = ai_helper.check_answer('{"recommendations":["M01", {"menu_code":"M02","reason":"ok"}]}')
        self.assertEqual([m["code"] for m, _ in result], ["M02"])
        with self.assertRaises(logic.AppError):
            ai_helper.check_answer('{"recommendations":"M01"}')

    def test_ai_answer_unknown_code_removed(self):
        text = '{"recommendations":[{"menu_code":"M99","reason":"x"},{"menu_code":"M01","reason":"ใช้ฟักทอง"}]}'
        result = ai_helper.check_answer(text)
        self.assertEqual([m["code"] for m, _ in result], ["M01"])

    def test_ai_answer_bad_format(self):
        with self.assertRaises(logic.AppError):
            ai_helper.check_answer("ไม่ใช่ JSON")
        with self.assertRaises(logic.AppError):
            ai_helper.check_answer('{"recommendations":[{"menu_code":"ZZZ","reason":""}]}')


if __name__ == "__main__":
    unittest.main()
