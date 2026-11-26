import os
import re
import json
import sqlite3
import urllib3
import numpy as np
from datetime import datetime, time, date
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_storage_dir():
    app_data = os.getenv("FLET_APP_STORAGE_DATA")
    if app_data and os.path.isdir(app_data):
        return app_data
    base = os.path.join(os.path.expanduser("~"), ".lottoquant_pro")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def to_int(val, default=0):
    try:
        if val is None:
            return default
        f = float(val)
        if np.isnan(f):
            return default
        return int(round(f))
    except Exception:
        return default


def format_odds_int(val):
    try:
        v = int(round(float(val)))
        return str(v if v > 0 else 47)
    except Exception:
        return "47"


def clean_year_str(raw_year, fallback_date=""):
    if raw_year is not None:
        s = str(raw_year).strip()
        if s and s.lower() != "none" and s.lower() != "nan":
            m = re.search(r'\d{4}', s)
            if m:
                return m.group(0)
    if fallback_date:
        s_d = str(fallback_date).strip()
        if len(s_d) >= 4 and s_d[:4].isdigit():
            return s_d[:4]
    return str(datetime.now().year)


def normalize_target_key(target_str):
    if not target_str:
        return ""
    parts = [p.strip() for p in re.split(r'[,，\-]+', str(target_str)) if p.strip()]
    return ", ".join(parts)


class ZodiacCalendarEngine:
    ZODIAC_ORDER = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

    LUNAR_NEW_YEAR_DATES = {
        2022: date(2022, 2, 1),
        2023: date(2023, 1, 22),
        2024: date(2024, 2, 10),
        2025: date(2025, 1, 29),
        2026: date(2026, 2, 17),
        2027: date(2027, 2, 6),
        2028: date(2028, 1, 26),
        2029: date(2029, 2, 13),
        2030: date(2030, 2, 3),
    }

    @classmethod
    def get_lunar_year_by_date(cls, draw_date_str):
        if not draw_date_str:
            d = datetime.now().date()
        else:
            try:
                clean_s = str(draw_date_str).strip()[:10].replace("/", "-")
                d = datetime.strptime(clean_s, "%Y-%m-%d").date()
            except Exception:
                d = datetime.now().date()
        y = d.year
        lunar_new_year = cls.LUNAR_NEW_YEAR_DATES.get(y, date(y, 2, 10))
        return (y - 1) if d < lunar_new_year else y

    @classmethod
    def get_zodiac_by_date(cls, draw_date_str):
        lunar_y = cls.get_lunar_year_by_date(draw_date_str)
        return cls.ZODIAC_ORDER[(lunar_y - 2020) % 12]

    @classmethod
    def build_zodiac_mapping(cls, head_zodiac="马"):
        head_z = head_zodiac if head_zodiac in cls.ZODIAC_ORDER else "马"
        start_idx = cls.ZODIAC_ORDER.index(head_z)
        num_to_z_map = {}
        z_to_nums_map = {z: [] for z in cls.ZODIAC_ORDER}

        for num in range(1, 50):
            z_idx = (start_idx - (num - 1)) % 12
            z_name = cls.ZODIAC_ORDER[z_idx]
            num_to_z_map[num] = z_name
            z_to_nums_map[z_name].append(num)

        return num_to_z_map, z_to_nums_map


def num_to_zodiac(num, draw_date=""):
    try:
        num = int(num)
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(draw_date)
        num_map, _ = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        return num_map.get(num, "未知")
    except Exception:
        return "未知"


class LottoAttrClassifier:
    RED_BALLS = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
    BLUE_BALLS = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 32, 36, 37, 41, 42, 47, 48}
    GREEN_BALLS = {5, 6, 11, 16, 17, 21, 22, 27, 28, 33, 38, 39, 43, 44, 49}

    POULTRY_ZODIACS = {"牛", "马", "羊", "鸡", "狗", "猪"}
    BEAST_ZODIACS = {"鼠", "虎", "兔", "龙", "蛇", "猴"}

    WU_XING_YEARLY = {
        2024: {
            "金": [4, 5, 12, 13, 26, 27, 34, 35, 42, 43],
            "木": [2, 3, 10, 11, 18, 19, 32, 33, 40, 41, 48, 49],
            "水": [8, 9, 16, 17, 24, 25, 38, 39, 46, 47],
            "火": [1, 14, 15, 22, 23, 30, 31, 44, 45],
            "土": [6, 7, 20, 21, 28, 29, 36, 37]
        },
        2025: {
            "金": [1, 2, 15, 16, 23, 24, 31, 32, 45, 46],
            "木": [5, 6, 13, 14, 27, 28, 35, 36, 43, 44],
            "水": [11, 12, 19, 20, 33, 34, 41, 42],
            "火": [7, 8, 21, 22, 29, 30, 37, 38],
            "土": [3, 4, 9, 10, 17, 18, 25, 26, 39, 40, 47, 48, 49]
        },
        2026: {
            "金": [2, 3, 4, 5, 16, 17, 24, 25, 32, 33, 46, 47],
            "木": [6, 7, 14, 15, 28, 29, 36, 37, 44, 45],
            "水": [12, 13, 20, 21, 34, 35, 42, 43],
            "火": [8, 9, 22, 23, 30, 31, 38, 39],
            "土": [1, 10, 11, 18, 19, 26, 27, 40, 41, 48, 49]
        },
        2027: {
            "金": [3, 4, 5, 6, 17, 18, 25, 26, 33, 34, 47, 48],
            "木": [7, 8, 15, 16, 29, 30, 37, 38, 45, 46],
            "水": [13, 14, 21, 22, 35, 36, 43, 44],
            "火": [9, 10, 23, 24, 31, 32, 39, 40],
            "土": [1, 2, 11, 12, 19, 20, 27, 28, 41, 42, 49]
        }
    }

    @classmethod
    def get_wuxing_map_by_date(cls, draw_date_str=""):
        lunar_y = ZodiacCalendarEngine.get_lunar_year_by_date(draw_date_str)
        if lunar_y in cls.WU_XING_YEARLY:
            return cls.WU_XING_YEARLY[lunar_y]
        min_y = min(cls.WU_XING_YEARLY.keys())
        max_y = max(cls.WU_XING_YEARLY.keys())
        return cls.WU_XING_YEARLY[min_y if lunar_y < min_y else max_y]

    @classmethod
    def get_color(cls, num):
        try:
            n = int(num)
            if n in cls.RED_BALLS:
                return "红波"
            if n in cls.BLUE_BALLS:
                return "蓝波"
            if n in cls.GREEN_BALLS:
                return "绿波"
        except Exception:
            pass
        return "未知"

    @classmethod
    def get_color_hex(cls, num):
        c = cls.get_color(num)
        if c == "红波":
            return "#F87171"
        if c == "蓝波":
            return "#3B82F6"
        if c == "绿波":
            return "#10B981"
        return "#94A3B8"

    @classmethod
    def get_wuxing(cls, num, draw_date_str=""):
        try:
            n = int(num)
            w_map = cls.get_wuxing_map_by_date(draw_date_str)
            for element, nums in w_map.items():
                if n in nums:
                    return element
        except Exception:
            pass
        return "土"

    @classmethod
    def get_half_wave(cls, num):
        c = cls.get_color(num)
        if c == "未知":
            return "未知"
        ds = "单" if int(num) % 2 != 0 else "双"
        return f"{c[0]}{ds}"

    @classmethod
    def get_bs_oe(cls, num):
        try:
            n = int(num)
            if n == 49:
                return "和局(49)"
            dx = "大" if n >= 25 else "小"
            ds = "单" if n % 2 != 0 else "双"
            return f"{dx}{ds}"
        except Exception:
            return "未知"

    @classmethod
    def get_head_group(cls, num):
        try:
            n = int(num)
            h = n // 10
            if h == 0:
                return "0头(01-09)"
            if h == 1:
                return "1头(10-19)"
            if h == 2:
                return "2头(20-29)"
            if h == 3:
                return "3头(30-39)"
            if h == 4:
                return "4头(40-49)"
        except Exception:
            pass
        return "未知"

    @classmethod
    def get_tail_size(cls, num):
        try:
            n = int(num)
            t = n % 10
            return "大尾(5-9)" if t >= 5 else "小尾(0-4)"
        except Exception:
            return "未知"

    @classmethod
    def get_sum_oe(cls, num):
        try:
            n = int(num)
            s = (n // 10) + (n % 10)
            return "合单" if s % 2 != 0 else "合双"
        except Exception:
            return "未知"

    @classmethod
    def get_poultry_beast(cls, zodiac):
        if zodiac in cls.POULTRY_ZODIACS:
            return "家禽(牛马羊鸡狗猪)"
        if zodiac in cls.BEAST_ZODIACS:
            return "野兽(鼠虎兔龙蛇猴)"
        return "未知"


def extract_zodiac_series(rows, pos_col="特码"):
    z_col = "特码生肖" if pos_col == "特码" else f"{pos_col}肖"
    valid_z = set(ZodiacCalendarEngine.ZODIAC_ORDER)
    out = []
    for r in rows:
        z_val = r.get(z_col, "")
        if isinstance(z_val, str) and z_val in valid_z:
            out.append(z_val)
        else:
            out.append(num_to_zodiac(r.get(pos_col, 0), r.get("开奖时间", "")))
    return out


class BayesianRegimeEngine:
    @classmethod
    def compute_regime_from_seq(cls, full_seq, head_z, window_size=30, prior_weight=15.0, lock_head=True):
        if not full_seq or len(full_seq) < 6:
            return {
                "regime": "MOMENTUM_ATTACK",
                "desc": "数据预热期 (默认动量)",
                "mci": 0.25,
                "max_zscore": 0.0,
                "picks": [],
                "bet_multiplier": 1.0,
            }

        sub_seq = full_seq[-window_size:] if len(full_seq) >= window_size else full_seq
        w_len = len(sub_seq)

        zodiac_order = ZodiacCalendarEngine.ZODIAC_ORDER
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)

        posterior_expectations = {}
        omission_zscores = {}

        for z in zodiac_order:
            prior_p = len(z_to_nums.get(z, [])) / 49.0
            alpha_0 = prior_weight * prior_p
            beta_0 = prior_weight * (1.0 - prior_p)
            hits = sub_seq.count(z)
            post_e = (alpha_0 + hits) / (alpha_0 + beta_0 + w_len)
            posterior_expectations[z] = post_e

            omissions = []
            cur_om = 0
            for item in full_seq:
                if item == z:
                    if cur_om > 0:
                        omissions.append(cur_om)
                    cur_om = 0
                else:
                    cur_om += 1

            if omissions:
                mean_om = sum(omissions) / len(omissions)
                if len(omissions) > 1:
                    var_om = sum((x - mean_om) ** 2 for x in omissions) / len(omissions)
                    std_om = float(np.sqrt(var_om)) if var_om > 0 else 3.0
                else:
                    std_om = 3.0
            else:
                mean_om = 11.0
                std_om = 3.0
            omission_zscores[z] = (cur_om - mean_om) / std_om

        sorted_post = sorted(posterior_expectations.items(), key=lambda x: x[1], reverse=True)
        top3_mass = sum(x[1] for x in sorted_post[:3])
        total_mass = sum(posterior_expectations.values())
        mci = top3_mass / total_mass if total_mass > 0 else 0.25

        _, max_zscore = max(omission_zscores.items(), key=lambda x: x[1])

        def _apply_head_constraint(raw_candidates):
            picks = []
            if lock_head:
                picks.append(head_z)
            for z in raw_candidates:
                if z != head_z and z not in picks and len(picks) < 6:
                    picks.append(z)
            return picks

        if mci >= 0.36 and max_zscore < 2.2:
            regime = "MOMENTUM_ATTACK"
            desc = f"动量聚集态 (MCI={mci:.1%})"
            recommended_picks = _apply_head_constraint([x[0] for x in sorted_post])
            risk_bet_factor = 1.0
        else:
            max_cold_z, _ = max(omission_zscores.items(), key=lambda x: x[1])
            regime = "COLD_DEFENSE"
            desc = f"极冷均值回归 ({max_cold_z} 遗漏Z={max_zscore:.2f})"
            sorted_cold = sorted(omission_zscores.items(), key=lambda x: x[1], reverse=True)
            candidates = [sorted_cold[0][0], sorted_cold[1][0], sorted_cold[2][0]] + [x[0] for x in sorted_post]
            recommended_picks = _apply_head_constraint(candidates)
            risk_bet_factor = 0.5

        return {
            "regime": regime,
            "desc": desc,
            "mci": mci,
            "max_zscore": max_zscore,
            "picks": recommended_picks,
            "bet_multiplier": risk_bet_factor,
        }


class LottoScheduleConfig:
    AM_DAYS = {0, 1, 2, 3, 4, 5, 6}
    AM_DRAW_START = time(21, 32)
    AM_DRAW_END = time(21, 45)

    HK_DAYS = {1, 3, 5, 6}
    HK_DRAW_START = time(21, 32)
    HK_DRAW_END = time(21, 50)

    @classmethod
    def is_draw_window(cls, source_type="am"):
        now_dt = datetime.now()
        cur_weekday = now_dt.weekday()
        cur_time = now_dt.time()
        if source_type == "hk":
            return cur_weekday in cls.HK_DAYS and cls.HK_DRAW_START <= cur_time <= cls.HK_DRAW_END
        return cur_weekday in cls.AM_DAYS and cls.AM_DRAW_START <= cur_time <= cls.AM_DRAW_END

    @classmethod
    def get_schedule_desc(cls, source_type="am"):
        if source_type == "hk":
            return "二/四/六/日 21:32~21:50 自动同步"
        return "每日 21:32~21:45 自动同步"


class LottoDatabase:
    DB_NAME = os.path.join(get_storage_dir(), "lotto_history.db")

    @classmethod
    def _connect(cls):
        os.makedirs(os.path.dirname(cls.DB_NAME), exist_ok=True)
        return sqlite3.connect(cls.DB_NAME, timeout=15.0, check_same_thread=False)

    @classmethod
    def init_db(cls):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lottery_records (
                    lottery_type TEXT,
                    year TEXT,
                    period INTEGER,
                    period_display TEXT,
                    p1 INTEGER, p1_zodiac TEXT,
                    p2 INTEGER, p2_zodiac TEXT,
                    p3 INTEGER, p3_zodiac TEXT,
                    p4 INTEGER, p4_zodiac TEXT,
                    p5 INTEGER, p5_zodiac TEXT,
                    p6 INTEGER, p6_zodiac TEXT,
                    sp INTEGER, sp_zodiac TEXT,
                    draw_date TEXT,
                    PRIMARY KEY (lottery_type, year, period)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS live_betting_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_type TEXT,
                    task_name TEXT,
                    start_period INTEGER,
                    target_type TEXT,
                    target_values TEXT,
                    target_codes TEXT,
                    stages INTEGER,
                    current_step INTEGER,
                    base_bet REAL,
                    plan_mode TEXT,
                    step_bets TEXT,
                    status TEXT,
                    accum_cost REAL,
                    total_payout REAL,
                    net_pnl REAL,
                    hit_period INTEGER,
                    create_time TEXT,
                    is_archived INTEGER DEFAULT 0,
                    start_year TEXT DEFAULT ''
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sys_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def get_config(cls, key, default=""):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("SELECT value FROM sys_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        finally:
            conn.close()

    @classmethod
    def set_config(cls, key, value):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT OR REPLACE INTO sys_config (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def save_records(cls, records):
        if not records:
            return 0
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            inserted_count = 0
            for r in records:
                draw_date = str(r.get("开奖时间", "")).strip()
                rec_year = clean_year_str(r.get("年份", ""), draw_date)
                cursor.execute("""
                    INSERT OR REPLACE INTO lottery_records (
                        lottery_type, year, period, period_display,
                        p1, p1_zodiac, p2, p2_zodiac, p3, p3_zodiac,
                        p4, p4_zodiac, p5, p5_zodiac, p6, p6_zodiac,
                        sp, sp_zodiac, draw_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("彩种", "am"), rec_year, int(r["期数"]), r["期数显示"],
                    r["平一"], r.get("平一肖", ""), r["平二"], r.get("平二肖", ""),
                    r["平三"], r.get("平三肖", ""), r["平四"], r.get("平四肖", ""),
                    r["平五"], r.get("平五肖", ""), r["平六"], r.get("平六肖", ""),
                    r["特码"], r.get("特码生肖", ""), draw_date
                ))
                inserted_count += 1
            conn.commit()
            return inserted_count
        finally:
            conn.close()

    @classmethod
    def clear_records(cls, lottery_type="am"):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lottery_records WHERE lottery_type = ?", (lottery_type,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()

    @classmethod
    def clear_live_bets(cls, lottery_type="am"):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM live_betting_records WHERE lottery_type = ?", (lottery_type,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()

    @classmethod
    def get_records(cls, lottery_type="am"):
        conn = cls._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT year, period, period_display, p1, p1_zodiac, p2, p2_zodiac,
                       p3, p3_zodiac, p4, p4_zodiac, p5, p5_zodiac,
                       p6, p6_zodiac, sp, sp_zodiac, draw_date
                FROM lottery_records
                WHERE lottery_type = ?
                ORDER BY CAST(year AS INTEGER) DESC, period DESC
            """, (lottery_type,))
            rows = cursor.fetchall()
            out = []
            for r in rows:
                out.append({
                    "年份": r["year"],
                    "期数": int(r["period"]),
                    "期数显示": r["period_display"],
                    "平一": int(r["p1"]), "平一肖": r["p1_zodiac"] or "",
                    "平二": int(r["p2"]), "平二肖": r["p2_zodiac"] or "",
                    "平三": int(r["p3"]), "平三肖": r["p3_zodiac"] or "",
                    "平四": int(r["p4"]), "平四肖": r["p4_zodiac"] or "",
                    "平五": int(r["p5"]), "平五肖": r["p5_zodiac"] or "",
                    "平六": int(r["p6"]), "平六肖": r["p6_zodiac"] or "",
                    "特码": int(r["sp"]), "特码生肖": r["sp_zodiac"] or "",
                    "开奖时间": r["draw_date"] or "",
                })
            return out
        finally:
            conn.close()

    @classmethod
    def add_live_bet(cls, bet_data):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO live_betting_records (
                    lottery_type, task_name, start_period, target_type,
                    target_values, target_codes, stages, current_step,
                    base_bet, plan_mode, step_bets, status, accum_cost,
                    total_payout, net_pnl, hit_period, create_time, is_archived, start_year
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                bet_data.get("lottery_type", "am"),
                bet_data.get("task_name", "实盘计划"),
                bet_data.get("start_period", 0),
                bet_data.get("target_type", "生肖"),
                bet_data.get("target_values", ""),
                json.dumps(bet_data.get("target_codes", [])),
                bet_data.get("stages", 3),
                1,
                to_int(bet_data.get("base_bet", 10)),
                bet_data.get("plan_mode", "盈利型(恒定每期盈利)"),
                json.dumps([to_int(x) for x in bet_data.get("step_bets", [])]),
                "待确认第 1 期下注",
                0, 0, 0, 0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                clean_year_str(bet_data.get("start_year", "")),
            ))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def get_live_bets(cls, lottery_type="am", only_active=True):
        conn = cls._connect()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if only_active:
                sql = "SELECT * FROM live_betting_records WHERE lottery_type = ? AND is_archived = 0 ORDER BY id DESC"
            else:
                sql = "SELECT * FROM live_betting_records WHERE lottery_type = ? ORDER BY id DESC"
            cursor.execute(sql, (lottery_type,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def get_active_live_orders(cls, lottery_type, target_type=None):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            if target_type:
                cursor.execute("""
                    SELECT id, task_name, target_type, target_values FROM live_betting_records
                    WHERE lottery_type = ? AND target_type = ?
                    AND is_archived = 0 AND status NOT LIKE '%胜出%' AND status NOT LIKE '%断缆%'
                    AND status NOT LIKE '%已中奖%' AND status NOT LIKE '%和局%' AND status NOT LIKE '%结束%'
                    ORDER BY id DESC
                """, (lottery_type, target_type))
            else:
                cursor.execute("""
                    SELECT id, task_name, target_type, target_values FROM live_betting_records
                    WHERE lottery_type = ?
                    AND is_archived = 0 AND status NOT LIKE '%胜出%' AND status NOT LIKE '%断缆%'
                    AND status NOT LIKE '%已中奖%' AND status NOT LIKE '%和局%' AND status NOT LIKE '%结束%'
                    ORDER BY id DESC
                """, (lottery_type,))
            return cursor.fetchall()
        finally:
            conn.close()

    @classmethod
    def is_target_active(cls, lottery_type, target_type, target_values_str):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            alt_hyphen = target_values_str.replace(", ", "-")
            cursor.execute("""
                SELECT count(*) FROM live_betting_records
                WHERE lottery_type = ? AND target_type = ?
                AND (target_values = ? OR target_values = ?)
                AND is_archived = 0 AND status NOT LIKE '%胜出%' AND status NOT LIKE '%断缆%'
                AND status NOT LIKE '%已中奖%' AND status NOT LIKE '%和局%' AND status NOT LIKE '%结束%'
            """, (lottery_type, target_type, target_values_str, alt_hyphen))
            return cursor.fetchone()[0] > 0
        finally:
            conn.close()

    @classmethod
    def update_live_bet(cls, task_id, update_dict):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            set_clauses = [f"{k} = ?" for k in update_dict.keys()]
            values = list(update_dict.values()) + [task_id]
            cursor.execute(f"UPDATE live_betting_records SET {', '.join(set_clauses)} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def archive_live_bet(cls, task_id):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE live_betting_records SET is_archived = 1 WHERE id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def delete_live_bet(cls, task_id):
        conn = cls._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM live_betting_records WHERE id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()


class RealHtmlParser:
    @staticmethod
    def _clean_period(p_str):
        nums = re.findall(r'\d+', p_str)
        if not nums:
            return None
        p_val = nums[-1] if len(nums[-1]) <= 4 else nums[-1][-3:]
        return int(p_val)

    @staticmethod
    def parse_html_source(html_text, source_type="am", year="2026"):
        records = []
        soup = BeautifulSoup(html_text, 'html.parser')
        li_items = soup.find_all("li")

        for li in li_items:
            header_el = li.find(["dt", "div", "span"], class_=re.compile(r'(title|info|period|date|head)', re.I)) or li.find("dt")
            text_context = header_el.get_text() if header_el else li.get_text()

            p_match = re.search(r'(\d+)\s*期', text_context) or re.search(r'第\s*(\d+)', text_context)
            if not p_match:
                continue

            period_num = RealHtmlParser._clean_period(p_match.group(0))
            if not period_num:
                continue

            date_match = re.search(r'(\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2})', text_context)
            draw_date = date_match.group(1).replace("/", "-") if date_match else ""
            rec_year = draw_date[:4] if len(draw_date) >= 4 else str(year)

            ball_classes = {"ball", "ball-te", "b-ball", "num"}
            raw_balls = li.find_all(
                lambda tag: tag.name in ["div", "span"] and any(c in ball_classes for c in tag.get("class", []))
            )
            ball_elements = []
            seen_ids = set(id(b) for b in raw_balls)
            for b in raw_balls:
                if not any(id(p) in seen_ids for p in b.parents):
                    ball_elements.append(b)

            valid_balls = [b for b in ball_elements if "+" not in b.get_text()]
            if len(valid_balls) < 7:
                continue

            balls_data = []
            for b in valid_balls[:7]:
                num_text = re.search(r'\d+', b.get_text())
                num_val = int(num_text.group(0)) if num_text else None
                z_val = b.get("data-name", "")
                if not z_val:
                    b_tag = b.find(["b", "i", "span", "em"])
                    if b_tag and not b_tag.text.strip().isdigit():
                        z_val = b_tag.text.strip()
                if num_val is not None:
                    zodiac = z_val if (z_val and z_val in ZodiacCalendarEngine.ZODIAC_ORDER) else num_to_zodiac(num_val, draw_date)
                    balls_data.append((num_val, zodiac))

            if len(balls_data) == 7:
                records.append({
                    "彩种": source_type, "年份": rec_year, "期数": period_num,
                    "期数显示": f"{str(period_num).zfill(3)}期",
                    "平一": balls_data[0][0], "平一肖": balls_data[0][1],
                    "平二": balls_data[1][0], "平二肖": balls_data[1][1],
                    "平三": balls_data[2][0], "平三肖": balls_data[2][1],
                    "平四": balls_data[3][0], "平四肖": balls_data[3][1],
                    "平五": balls_data[4][0], "平五肖": balls_data[4][1],
                    "平六": balls_data[5][0], "平六肖": balls_data[5][1],
                    "特码": balls_data[6][0], "特码生肖": balls_data[6][1],
                    "开奖时间": draw_date
                })
        return records


class FastHttpFetcher:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
        })

    def fetch(self, url):
        try:
            resp = self.session.get(url, timeout=15, verify=False)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
        except Exception:
            pass
        return None


def sync_official_data(source_type="am", year="2026", on_status=None):
    url = f"https://2026kj.zkclhb.com:2025/{source_type}.html"
    if on_status:
        on_status("正在连接官网数据节点...")
    fetcher = FastHttpFetcher()
    html = fetcher.fetch(url)
    records = RealHtmlParser.parse_html_source(html, source_type, str(year)) if html else []
    inserted = LottoDatabase.save_records(records) if records else 0
    final_rows = LottoDatabase.get_records(source_type)
    if records and final_rows:
        msg = f"同步成功！入库 {inserted} 期 (最新: 第 {final_rows[0]['期数']} 期)"
    else:
        msg = "未获取新数据，已载入本地记录"
    if on_status:
        on_status(msg)
    return final_rows, msg


class BayesianHMMHybridEngine:
    @staticmethod
    def markov_2nd_order_score(seq, zodiac, alpha=0.5):
        if len(seq) < 10:
            return 1.0 / 12.0
        last1, last2 = seq[-1], seq[-2]
        cnt1, tot1, cnt2, tot2 = 0, 0, 0, 0
        for i in range(2, len(seq)):
            if seq[i - 1] == last1:
                tot1 += 1
                if seq[i] == zodiac:
                    cnt1 += 1
            if seq[i - 2] == last2:
                tot2 += 1
                if seq[i] == zodiac:
                    cnt2 += 1
        p1 = (cnt1 + alpha) / (tot1 + 12.0 * alpha)
        p2 = (cnt2 + alpha) / (tot2 + 12.0 * alpha)
        return 0.65 * p1 + 0.35 * p2

    @staticmethod
    def multiscale_bayes_score(seq, zodiac, z_map):
        prior = z_map.get(zodiac, 4) / 49.0
        w_short = seq[-15:] if len(seq) >= 15 else seq
        w_mid = seq[-45:] if len(seq) >= 45 else seq
        alpha0 = prior * 12.0
        beta0 = (1.0 - prior) * 12.0
        post_short = (alpha0 + w_short.count(zodiac)) / (alpha0 + beta0 + len(w_short))
        post_mid = (alpha0 + w_mid.count(zodiac)) / (alpha0 + beta0 + len(w_mid))
        return (0.45 * post_short + 0.55 * post_mid) / (prior + 0.05)

    @staticmethod
    def omission_reversion_score(seq, zodiac):
        if len(seq) < 12:
            return 0.5
        omissions = []
        cur = 0
        for z in seq:
            if z == zodiac:
                if cur > 0:
                    omissions.append(cur)
                cur = 0
            else:
                cur += 1
        if omissions:
            mean_om = sum(omissions) / len(omissions)
            if len(omissions) > 1:
                var_om = sum((x - mean_om) ** 2 for x in omissions) / len(omissions)
                std_om = float(np.sqrt(var_om)) if var_om > 0 else 3.5
            else:
                std_om = 3.5
        else:
            mean_om = 11.0
            std_om = 3.5
        z_val = (cur - mean_om) / std_om
        reversion = 1.0 / (1.0 + np.exp(-z_val * 0.95))
        resonance = np.exp(-0.5 * ((cur - mean_om) / (std_om * 0.8)) ** 2)
        return float(0.7 * reversion + 0.3 * resonance)

    @classmethod
    def get_hybrid_scores(cls, seq, z_map):
        scores = {}
        for z in ZodiacCalendarEngine.ZODIAC_ORDER:
            s_markov = cls.markov_2nd_order_score(seq, z) * 12.0
            s_bayes = cls.multiscale_bayes_score(seq, z, z_map)
            s_reversion = cls.omission_reversion_score(seq, z)
            scores[z] = s_markov * 0.30 + s_bayes * 0.30 + s_reversion * 0.40
        return scores


class AnalyticsEngine:
    ALGO_NAMES = {
        1: "智能六肖偏离量化算法 (HTML专属)",
        2: "马尔可夫转移概率 (实测前一)",
        3: "⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)",
        4: "多策略交叉共识模型 (低断缆推荐)",
        5: "🏆 自适应三因子稳健融合模型 (优胜推荐)",
    }

    ALGO_SHORT_TAGS = {
        1: "智能六肖",
        2: "马尔可夫",
        3: "贝叶斯HMM",
        4: "多策略共识",
        5: "三因子融合",
    }

    @staticmethod
    def ensure_chrono(rows):
        if not rows:
            return []
        if len(rows) > 1:
            r0, r1 = rows[0], rows[1]
            y0, y1 = to_int(r0.get("年份"), 0), to_int(r1.get("年份"), 0)
            p0, p1 = to_int(r0.get("期数"), 0), to_int(r1.get("期数"), 0)
            if (y0 > y1) or (y0 == y1 and p0 > p1):
                return list(reversed(rows))
        return list(rows)

    @staticmethod
    def get_metrics(rows, pos_col="特码"):
        if not rows:
            return []
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(rows[0].get("开奖时间", ""))
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        chrono_rows = AnalyticsEngine.ensure_chrono(rows)
        series_zodiac = extract_zodiac_series(chrono_rows, pos_col)

        out = []
        for z in ZodiacCalendarEngine.ZODIAC_ORDER:
            count = 0
            cur_omission = 0
            omissions = []
            for item in series_zodiac:
                if item == z:
                    count += 1
                    omissions.append(cur_omission)
                    cur_omission = 0
                else:
                    cur_omission += 1

            avg_omission = (sum(omissions) / len(omissions)) if omissions else len(chrono_rows)
            if cur_omission >= avg_omission * 1.8:
                status = "长冷/警惕"
            elif cur_omission <= 1 and count >= (len(chrono_rows) / 12) * 1.1:
                status = "高热动量"
            else:
                status = "温态平稳"

            out.append({
                "生肖": z,
                "包含码数": len(z_to_nums.get(z, [])),
                "出现次数": count,
                "当前遗漏": cur_omission,
                "平均遗漏": to_int(avg_omission),
                "状态": status,
            })
        out.sort(key=lambda x: x["当前遗漏"])
        return out

    @staticmethod
    def get_half_wave_metrics(rows):
        if not rows:
            return []
        chrono_rows = AnalyticsEngine.ensure_chrono(rows)
        targets = ["红单", "红双", "蓝单", "蓝双", "绿单", "绿双"]
        series_hw = [LottoAttrClassifier.get_half_wave(r.get("特码", 0)) for r in chrono_rows]
        out = []
        for hw in targets:
            count = 0
            cur_om = 0
            omissions = []
            for item in series_hw:
                if item == hw:
                    count += 1
                    omissions.append(cur_om)
                    cur_om = 0
                else:
                    cur_om += 1
            avg_om = (sum(omissions) / len(omissions)) if omissions else len(chrono_rows)
            out.append({"半波": hw, "开出次数": count, "当前遗漏": cur_om, "平均遗漏": to_int(avg_om)})
        out.sort(key=lambda x: x["当前遗漏"])
        return out

    @staticmethod
    def get_bs_oe_metrics(rows):
        if not rows:
            return []
        chrono_rows = AnalyticsEngine.ensure_chrono(rows)
        targets = ["大单", "大双", "小单", "小双"]
        series_bsoe = [LottoAttrClassifier.get_bs_oe(r.get("特码", 0)) for r in chrono_rows]
        out = []
        for b in targets:
            count = 0
            cur_om = 0
            omissions = []
            for item in series_bsoe:
                if item == b:
                    count += 1
                    omissions.append(cur_om)
                    cur_om = 0
                else:
                    cur_om += 1
            avg_om = (sum(omissions) / len(omissions)) if omissions else len(chrono_rows)
            out.append({"两面形态": b, "开出次数": count, "当前遗漏": cur_om, "平均遗漏": to_int(avg_om)})
        out.sort(key=lambda x: x["当前遗漏"])
        return out

    @staticmethod
    def _predict_smart_six_from_seq(seq, head_z, z_map, count=6, lock_head=True):
        if not seq:
            if lock_head:
                return [head_z] + [z for z in ZodiacCalendarEngine.ZODIAC_ORDER if z != head_z][:count - 1]
            return [z for z in ZodiacCalendarEngine.ZODIAC_ORDER if z != head_z][:count]

        n = len(seq)
        last1 = seq[-1]
        last2 = seq[-2] if n >= 2 else None
        last3 = seq[-3] if n >= 3 else None

        t1 = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
        t2 = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
        t3 = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
        tot1, tot2, tot3 = 0.0, 0.0, 0.0

        for k in range(n - 1):
            age = (n - 2) - k
            w_rec = float(1.0 + 1.2 * np.exp(-0.04 * age))
            if seq[k] == last1:
                t1[seq[k + 1]] += w_rec
                tot1 += w_rec
            if last2 is not None and k + 2 < n and seq[k] == last2:
                t2[seq[k + 2]] += w_rec
                tot2 += w_rec
            if last3 is not None and k + 3 < n and seq[k] == last3:
                t3[seq[k + 3]] += w_rec
                tot3 += w_rec

        w10 = seq[-10:] if n >= 10 else seq
        w24 = seq[-24:] if n >= 24 else seq
        l10, l24 = max(1, len(w10)), max(1, len(w24))

        hy = BayesianHMMHybridEngine.get_hybrid_scores(seq, z_map)
        max_hy = max(hy.values()) if hy else 1.0

        scores = {}
        for z in ZodiacCalendarEngine.ZODIAC_ORDER:
            prior_p = max(0.03, z_map.get(z, 4) / 49.0)
            p1 = (t1[z] + 0.35 * prior_p) / (tot1 + 0.35)
            p2 = (t2[z] + 0.35 * prior_p) / (tot2 + 0.35)
            p3 = (t3[z] + 0.35 * prior_p) / (tot3 + 0.35)
            tr_score = (0.60 * p1 + 0.25 * p2 + 0.15 * p3) * 16.0

            f10 = (w10.count(z) / l10) / prior_p
            f24 = (w24.count(z) / l24) / prior_p
            freq_score = min(2.2, 0.65 * f10 + 0.35 * f24) * 1.15
            nh = ((hy.get(z, 0.5) / max_hy) if max_hy > 0 else 0.5) * 1.25

            om = 0
            for item in reversed(seq):
                if item == z:
                    break
                om += 1
            exp_om = max(1.5, (1.0 / prior_p) - 1.0)
            om_ratio = om / max(1.0, exp_om)
            if om_ratio <= 1.4:
                om_adj = 0.5 + 0.45 * om_ratio
            elif om_ratio <= 2.0:
                om_adj = 0.75
            else:
                om_adj = max(0.15, 0.75 - 0.45 * (om_ratio - 2.0))

            scores[z] = tr_score + freq_score + nh + om_adj

        sorted_z = [x[0] for x in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
        final_picks = [head_z] if lock_head else []
        for z in sorted_z:
            if z != head_z and z not in final_picks and len(final_picks) < count:
                final_picks.append(z)
        return final_picks[:count]

    @staticmethod
    def _predict_high_win_ensemble(seq, head_z, z_map, count=6, lock_head=True):
        if not seq:
            base = [head_z] if lock_head else []
            for z in ZodiacCalendarEngine.ZODIAC_ORDER:
                if z != head_z and len(base) < count:
                    base.append(z)
            return base[:count]

        n = len(seq)
        last1 = seq[-1]
        last2 = seq[-2] if n >= 2 else None

        trans1 = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
        trans2 = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
        for idx in range(n - 1):
            decay = float(np.exp(-0.025 * ((n - 2) - idx)))
            if seq[idx] == last1:
                trans1[seq[idx + 1]] += 1.0 + 0.8 * decay
            if last2 is not None and seq[idx] == last2 and idx + 2 < n:
                trans2[seq[idx + 2]] += 1.0 + 0.6 * decay

        max_t1 = max(trans1.values()) if trans1 else 1.0
        max_t2 = max(trans2.values()) if trans2 else 1.0
        hy = BayesianHMMHybridEngine.get_hybrid_scores(seq, z_map)
        max_hy = max(hy.values()) if hy else 1.0
        w16 = seq[-16:] if n >= 16 else seq
        l16 = max(1, len(w16))

        scores = {}
        for z in ZodiacCalendarEngine.ZODIAC_ORDER:
            prior_p = z_map.get(z, 4) / 49.0
            n1 = (trans1[z] / max_t1) if max_t1 > 0 else 0.5
            n2 = (trans2[z] / max_t2) if max_t2 > 0 else 0.5
            nh = (hy.get(z, 0.5) / max_hy) if max_hy > 0 else 0.5
            h_rate = min(1.8, (w16.count(z) / l16) / max(0.03, prior_p))

            om = 0
            for item in reversed(seq):
                if item == z:
                    break
                om += 1
            exp_om = max(1.5, (1.0 / max(0.03, prior_p)) - 1.0)
            om_pen = 0.45 if (om > exp_om * 2.4 and n1 < 0.5) else 0.0
            scores[z] = n1 * 1.60 + n2 * 0.85 + nh * 1.15 + h_rate * 0.75 - om_pen

        sorted_z = [x[0] for x in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
        final_picks = [head_z] if lock_head else []
        for z in sorted_z:
            if z != head_z and len(final_picks) < count:
                final_picks.append(z)
        return final_picks[:count]

    @staticmethod
    def _run_prediction_from_seq(seq, head_z, z_map, algo_idx=1, count=6, lock_head=True):
        if algo_idx == 1:
            return AnalyticsEngine._predict_smart_six_from_seq(seq, head_z, z_map, count, lock_head)
        if algo_idx == 5:
            return AnalyticsEngine._predict_high_win_ensemble(seq, head_z, z_map, count, lock_head)

        last_z = seq[-1] if seq else head_z
        scores = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}

        if algo_idx == 2:
            trans = {z: 0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
            for i in range(len(seq) - 1):
                if seq[i] == last_z:
                    trans[seq[i + 1]] += 1
            for z in ZodiacCalendarEngine.ZODIAC_ORDER:
                scores[z] = trans[z] * 6.0
        elif algo_idx == 3:
            scores = BayesianHMMHybridEngine.get_hybrid_scores(seq, z_map)
        elif algo_idx == 4:
            markov_scores = {z: 0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
            for i in range(len(seq) - 1):
                if seq[i] == last_z:
                    markov_scores[seq[i + 1]] += 1
            hybrid_scores = BayesianHMMHybridEngine.get_hybrid_scores(seq, z_map)
            six_picks = AnalyticsEngine._predict_smart_six_from_seq(seq, head_z, z_map, 6, False)
            vote_table = {z: 0.0 for z in ZodiacCalendarEngine.ZODIAC_ORDER}
            for z, _ in sorted(markov_scores.items(), key=lambda x: x[1], reverse=True)[:6]:
                vote_table[z] += 1.4
            for z, _ in sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:6]:
                vote_table[z] += 1.5
            for z in six_picks:
                vote_table[z] += 1.5
            scores = vote_table

        sorted_z = [x[0] for x in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
        final_picks = [head_z] if lock_head else []
        for z in sorted_z:
            if z != head_z and z not in final_picks and len(final_picks) < count:
                final_picks.append(z)
        return final_picks

    @staticmethod
    def run_prediction(rows, algo_idx=1, count=6, lock_head=True, pos_col="特码"):
        if not rows:
            return []
        chrono_rows = AnalyticsEngine.ensure_chrono(rows)
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(chrono_rows[-1].get("开奖时间", ""))
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        z_map = {z: len(nums) for z, nums in z_to_nums.items()}
        seq = extract_zodiac_series(chrono_rows, pos_col)
        return AnalyticsEngine._run_prediction_from_seq(seq, head_z, z_map, algo_idx, count, lock_head)

    @staticmethod
    def _get_regime_adjusted_picks_from_seq(seq, head_z, z_map, algo_idx, lock_head=True, use_circuit_breaker=True):
        regime_info = BayesianRegimeEngine.compute_regime_from_seq(seq, head_z, lock_head=lock_head)
        base_picks = AnalyticsEngine._run_prediction_from_seq(seq, head_z, z_map, algo_idx, 6, lock_head)

        if regime_info["regime"] == "COLD_DEFENSE" and use_circuit_breaker:
            cold_picks = regime_info["picks"]
            merged = [head_z] if lock_head else []
            for idx_p in range(6):
                for src_list in (base_picks, cold_picks):
                    if idx_p < len(src_list):
                        cand_z = src_list[idx_p]
                        if not lock_head and cand_z == head_z:
                            continue
                        if cand_z not in merged and len(merged) < 6:
                            merged.append(cand_z)
            picks = merged
            current_multiplier = regime_info["bet_multiplier"]
        else:
            picks = base_picks
            current_multiplier = 1.0
        return picks, current_multiplier, regime_info

    @staticmethod
    def get_regime_adjusted_picks(chrono_rows, algo_idx, lock_head=True, use_circuit_breaker=True):
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(chrono_rows[-1].get("开奖时间", "")) if chrono_rows else "马"
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        z_map = {z: len(nums) for z, nums in z_to_nums.items()}
        seq = extract_zodiac_series(chrono_rows, "特码")
        picks, mult, regime_info = AnalyticsEngine._get_regime_adjusted_picks_from_seq(
            seq, head_z, z_map, algo_idx, lock_head, use_circuit_breaker
        )
        return picks, mult, regime_info, head_z

    @staticmethod
    def calc_breakeven_3_rate(codes_count, odds=47):
        odds_f = max(1.0, float(to_int(odds, 47)))
        p_be = min(0.99, max(0.01, float(codes_count) / odds_f))
        return 1.0 - ((1.0 - p_be) ** 3)

    @staticmethod
    def compute_edge_matched_multiplier(settled_outcomes, codes_count, odds, regime_info, use_circuit_breaker=True):
        be_3_rate = AnalyticsEngine.calc_breakeven_3_rate(codes_count, odds)
        if not use_circuit_breaker:
            return 1.0, be_3_rate
        if len(settled_outcomes) < 8:
            mult = 0.85 if regime_info.get("regime") == "COLD_DEFENSE" else 1.0
            return mult, be_3_rate
        recent = settled_outcomes[-18:]
        edge = (sum(1 for w in recent if w) / len(recent)) - be_3_rate
        if edge >= 0.025:
            mult = 1.2
        elif edge >= 0.0:
            mult = 1.0
        elif edge >= -0.03:
            mult = 0.75
        else:
            mult = 0.5
        return mult, be_3_rate

    @staticmethod
    def compute_adaptive_bets(base_bet, actual_codes_count, stages=3, odds=47, mode="盈利型(恒定每期盈利)", target_profit=None):
        bets = []
        cum_cost = 0
        odds = to_int(odds, 47)
        denom = odds - actual_codes_count
        t_profit = max(10, to_int(target_profit) if target_profit is not None else (to_int(500 * (base_bet / 10.0)) if base_bet > 0 else 500))

        if "平注" in mode:
            flat_b = max(1, int(np.ceil(max(1, to_int(t_profit * 0.85)) / denom))) if denom > 0 else max(1, to_int(base_bet))
            return [flat_b] * stages

        inc_base_b = min(10, max(1, to_int(base_bet, 10))) if to_int(base_bet, 10) >= 10 else max(1, to_int(base_bet, 10))
        p1_actual = max(1, inc_base_b * max(1, denom))

        for s in range(1, stages + 1):
            if "盈利型(递增" in mode:
                if s == 1:
                    b = inc_base_b
                elif s == 2:
                    desired_p = max(to_int(p1_actual * 1.50), to_int(t_profit * 0.70))
                    b = max(inc_base_b + 1, int(np.ceil((desired_p + cum_cost) / denom))) if denom > 0 else max(1, to_int(inc_base_b * 2.6))
                else:
                    p_mult = 2.20 + 0.80 * (s - 3)
                    t_factor = min(2.05, 1.00 + 0.35 * (s - 3))
                    desired_p = max(to_int(p1_actual * p_mult), to_int(t_profit * t_factor))
                    b = max(bets[-1] + 1, int(np.ceil((desired_p + cum_cost) / denom))) if denom > 0 else max(1, to_int(inc_base_b * (2.5 ** (s - 1))))
            elif "盈利型(恒定" in mode or "断缆对冲" in mode:
                b = max(1, int(np.ceil((t_profit + cum_cost) / denom))) if denom > 0 else max(1, to_int(base_bet * (2 ** (s - 1))))
            elif "防守型" in mode or "防守" in mode or "微损" in mode:
                if s == 1:
                    b = max(1, int(np.ceil((max(1, to_int(t_profit * 0.85)) + cum_cost) / denom))) if denom > 0 else max(1, to_int(base_bet))
                elif s == 2:
                    b = max(1, int(np.ceil((max(1, to_int(t_profit * 0.05)) + cum_cost) / denom))) if denom > 0 else max(1, to_int(base_bet * 1.2))
                else:
                    b = max(1, int(np.ceil(cum_cost / denom))) if denom > 0 else max(1, to_int(base_bet * 2.0))
            else:
                b = max(1, to_int(base_bet * (2 ** (s - 1))))
            bets.append(b)
            cum_cost += b * actual_codes_count
        return bets

    @staticmethod
    def slice_backtest_result(full_res, span_limit):
        total_len = full_res.get("total_len", 0)
        all_details = full_res.get("all_details", [])
        min_idx = max(0, total_len - span_limit)
        filtered_details = [d for d in all_details if d.get("settle_idx", -1) >= min_idx]
        if not filtered_details and all_details:
            filtered_details = all_details[-1:]

        real_rounds = [d for d in filtered_details if not d.get("is_cooldown", False)]
        total_rounds = len(real_rounds)
        win_rounds = sum(1 for d in real_rounds if d.get("won", False))
        loss_rounds = total_rounds - win_rounds
        total_turnover = sum(to_int(d.get("cost", 0)) for d in real_rounds)
        total_pnl = sum(to_int(d.get("pnl", 0)) for d in real_rounds)

        window_consec_bust = 0
        w_last_bust = False
        for d in real_rounds:
            if not d.get("won", False):
                if w_last_bust:
                    window_consec_bust += 1
                w_last_bust = True
            else:
                w_last_bust = False

        res = dict(full_res)
        res.update({
            "rounds": total_rounds, "win_rounds": win_rounds, "loss_rounds": loss_rounds,
            "consec_bust": window_consec_bust, "turnover": total_turnover, "pnl": total_pnl,
            "details": filtered_details, "span_limit": span_limit,
        })
        return res

    @staticmethod
    def simulate_walk_forward_backtest(raw_rows, span_limit, algo_idx, mode_text, lock_head, use_circuit_breaker, odds=47):
        odds = to_int(odds, 47)
        algo_name = AnalyticsEngine.ALGO_NAMES.get(algo_idx, f"算法 {algo_idx}")
        default_codes_count = 25 if lock_head else 24
        default_be_rate = AnalyticsEngine.calc_breakeven_3_rate(default_codes_count, odds)
        default_bets = AnalyticsEngine.compute_adaptive_bets(10, default_codes_count, stages=3, odds=odds, mode=mode_text, target_profit=500)

        if not raw_rows or len(raw_rows) < 5:
            return {
                "rounds": 0, "win_rounds": 0, "loss_rounds": 0, "consec_bust": 0,
                "turnover": 0, "pnl": 0, "bets": default_bets,
                "codes_in_round": default_codes_count, "be_3_rate": default_be_rate, "last_edge_mult": 1.0,
                "details": [], "all_details": [], "next_step": 1, "span_limit": span_limit,
                "last_pending_picks": [], "in_cooldown": False, "total_len": len(raw_rows) if raw_rows else 0,
            }

        full_chrono = AnalyticsEngine.ensure_chrono(raw_rows)
        total_len = len(full_chrono)
        full_seq = extract_zodiac_series(full_chrono, "特码")
        full_codes = [to_int(r.get("特码"), 0) for r in full_chrono]
        full_dates = [str(r.get("开奖时间", "") or "") for r in full_chrono]
        full_periods = [to_int(r.get("期数"), 0) for r in full_chrono]
        full_pdisplays = [str(r.get("期数显示") or f"{p}期") for r, p in zip(full_chrono, full_periods)]

        zodiac_map_cache = {}
        for hz in ZodiacCalendarEngine.ZODIAC_ORDER:
            _, z_to_n = ZodiacCalendarEngine.build_zodiac_mapping(hz)
            zodiac_map_cache[hz] = (z_to_n, {z: len(nums) for z, nums in z_to_n.items()})

        all_details = []
        settled_outcomes = []
        consecutive_bust_count = 0
        last_round_bust = False
        in_cooldown = False

        codes_count = default_codes_count
        be_3_rate = default_be_rate
        edge_mult = 1.0
        bets = default_bets
        last_pending_picks = []

        i = 5
        round_idx = 1
        while i < total_len:
            head_z = ZodiacCalendarEngine.get_zodiac_by_date(full_dates[i - 1])
            z_to_nums, z_map = zodiac_map_cache[head_z]
            picks, _, regime_info = AnalyticsEngine._get_regime_adjusted_picks_from_seq(
                full_seq[:i], head_z, z_map, algo_idx, lock_head, use_circuit_breaker
            )

            picks_str = "-".join(picks)
            round_codes = set()
            for z in picks:
                round_codes.update(z_to_nums.get(z, []))
            codes_count = max(1, len(round_codes))

            edge_mult, be_3_rate = AnalyticsEngine.compute_edge_matched_multiplier(
                settled_outcomes, codes_count, odds, regime_info, use_circuit_breaker
            )
            t_profit = max(10, to_int(500 * edge_mult))
            base_b = max(1, to_int(10 * edge_mult))
            bets = AnalyticsEngine.compute_adaptive_bets(base_b, codes_count, stages=3, odds=odds, mode=mode_text, target_profit=t_profit)

            r_cost, r_payout, won, hit_step, last_hit_code, last_hit_z, actual_steps_run = 0, 0, False, 0, 0, "", 0
            for s in range(min(3, total_len - i)):
                actual_steps_run += 1
                idx_cur = i + s
                act_code = full_codes[idx_cur]
                act_z = full_seq[idx_cur]
                r_cost += bets[s] * codes_count
                if act_z in picks:
                    r_payout = bets[s] * odds
                    r_pnl = r_payout - r_cost
                    won = True
                    hit_step = s + 1
                    last_hit_code = act_code
                    last_hit_z = act_z
                    break

            if won:
                settle_idx = i + hit_step - 1
                i += hit_step
                status_txt = f"第 {hit_step} 期命中"
            else:
                if actual_steps_run == 3:
                    r_pnl = -r_cost
                    settle_idx = i + 2
                    last_hit_code = full_codes[settle_idx]
                    last_hit_z = full_seq[settle_idx]
                    i += 3
                    status_txt = "3期断缆"
                else:
                    if not in_cooldown:
                        last_pending_picks = picks
                    break

            used_steps = hit_step if won else 3
            used_bets = bets[:used_steps]
            used_stakes = [b * codes_count for b in used_bets]

            if in_cooldown:
                all_details.append({
                    "round_title": "虚拟试探", "algo_idx": algo_idx, "algo_name": algo_name,
                    "period_display": full_pdisplays[settle_idx], "settle_period": full_periods[settle_idx],
                    "settle_idx": settle_idx, "step_count": used_steps, "codes_count": codes_count,
                    "bets_used": used_bets, "stakes_used": used_stakes, "payout": 0,
                    "picks_str": picks_str, "hit_code": last_hit_code, "hit_z": last_hit_z,
                    "status_txt": "虚拟命中 (解除熔断)" if won else "虚拟断缆 (吸收风险)",
                    "cost": 0, "pnl": 0, "is_cooldown": True, "won": won,
                })
                if won:
                    in_cooldown = False
                continue

            all_details.append({
                "round_title": f"第 {round_idx} 轮", "algo_idx": algo_idx, "algo_name": algo_name,
                "period_display": full_pdisplays[settle_idx], "settle_period": full_periods[settle_idx],
                "settle_idx": settle_idx, "step_count": used_steps, "codes_count": codes_count,
                "bets_used": used_bets, "stakes_used": used_stakes, "payout": r_payout,
                "picks_str": picks_str, "hit_code": last_hit_code, "hit_z": last_hit_z,
                "status_txt": status_txt, "cost": r_cost, "pnl": r_pnl, "is_cooldown": False, "won": won,
            })
            settled_outcomes.append(won)

            if not won:
                if last_round_bust:
                    consecutive_bust_count += 1
                last_round_bust = True
                recent_wr = (sum(1 for w in settled_outcomes[-18:] if w) / len(settled_outcomes[-18:])) if settled_outcomes else 1.0
                neg_edge_slump = len(settled_outcomes) >= 8 and recent_wr < be_3_rate
                if use_circuit_breaker and (regime_info["regime"] == "COLD_DEFENSE" or neg_edge_slump):
                    in_cooldown = True
            else:
                last_round_bust = False

            round_idx += 1

        pending_step = (total_len - i) + 1 if i < total_len else 1
        if pending_step > 3:
            pending_step = 1

        base_res = {
            "bets": bets, "codes_in_round": codes_count, "be_3_rate": be_3_rate,
            "last_edge_mult": edge_mult, "all_details": all_details, "next_step": pending_step,
            "last_pending_picks": last_pending_picks, "in_cooldown": in_cooldown, "total_len": total_len,
        }
        return AnalyticsEngine.slice_backtest_result(base_res, span_limit)

    @staticmethod
    def simulate_ai_smart_walk_forward_backtest(raw_rows, span_limit, mode_text, lock_head, use_circuit_breaker, odds=47):
        odds = to_int(odds, 47)
        default_codes_count = 25 if lock_head else 24
        default_be_rate = AnalyticsEngine.calc_breakeven_3_rate(default_codes_count, odds)
        default_bets = AnalyticsEngine.compute_adaptive_bets(10, default_codes_count, stages=3, odds=odds, mode=mode_text, target_profit=500)

        if not raw_rows or len(raw_rows) < 5:
            return {
                "rounds": 0, "win_rounds": 0, "loss_rounds": 0, "consec_bust": 0,
                "turnover": 0, "pnl": 0, "bets": default_bets,
                "codes_in_round": default_codes_count, "be_3_rate": default_be_rate, "last_edge_mult": 1.0,
                "details": [], "all_details": [], "next_step": 1, "span_limit": span_limit,
                "last_pending_picks": [], "last_pending_algo_name": "", "in_cooldown": False,
                "total_len": len(raw_rows) if raw_rows else 0,
            }

        full_chrono = AnalyticsEngine.ensure_chrono(raw_rows)
        total_len = len(full_chrono)
        full_seq = extract_zodiac_series(full_chrono, "特码")
        full_codes = [to_int(r.get("特码"), 0) for r in full_chrono]
        full_dates = [str(r.get("开奖时间", "") or "") for r in full_chrono]
        full_periods = [to_int(r.get("期数"), 0) for r in full_chrono]
        full_pdisplays = [str(r.get("期数显示") or f"{p}期") for r, p in zip(full_chrono, full_periods)]

        zodiac_map_cache = {}
        for hz in ZodiacCalendarEngine.ZODIAC_ORDER:
            _, z_to_n = ZodiacCalendarEngine.build_zodiac_mapping(hz)
            zodiac_map_cache[hz] = (z_to_n, {z: len(nums) for z, nums in z_to_n.items()})

        algo_ids = [1, 2, 3, 4, 5]
        algo_states_by_t = {a: {} for a in algo_ids}
        for a in algo_ids:
            algo_name = AnalyticsEngine.ALGO_NAMES.get(a, f"算法 {a}")
            settled_rounds = []
            in_cd = False
            idx_a = 5
            while idx_a < total_len:
                head_z_a = ZodiacCalendarEngine.get_zodiac_by_date(full_dates[idx_a - 1])
                _, z_map_a = zodiac_map_cache[head_z_a]
                picks_a, _, regime_a = AnalyticsEngine._get_regime_adjusted_picks_from_seq(
                    full_seq[:idx_a], head_z_a, z_map_a, a, lock_head, use_circuit_breaker
                )

                won_a, steps_a = False, 0
                for s in range(min(3, total_len - idx_a)):
                    steps_a += 1
                    if full_seq[idx_a + s] in picks_a:
                        won_a = True
                        break

                for s_offset in range(steps_a):
                    t = idx_a + s_offset
                    min_idx_t = max(0, t - span_limit)
                    recent_r = [sr for sr in settled_rounds if sr[0] >= min_idx_t and not sr[2]]
                    win_rate_val = (sum(1 for sr in recent_r if sr[1]) / len(recent_r) * 100.0) if recent_r else 0.0

                    last_bust_idx = None
                    for sr_idx in range(len(settled_rounds) - 1, -1, -1):
                        if settled_rounds[sr_idx][3]:
                            last_bust_idx = settled_rounds[sr_idx][0]
                            break
                    is_bust_alert = last_bust_idx is not None and last_bust_idx == t - 1

                    if not in_cd:
                        step_t = s_offset + 1
                        picks_t = picks_a
                    else:
                        step_t = 1
                        if s_offset == 0:
                            picks_t = picks_a
                        else:
                            hz_t = ZodiacCalendarEngine.get_zodiac_by_date(full_dates[t - 1])
                            _, zm_t = zodiac_map_cache[hz_t]
                            picks_t, _, _ = AnalyticsEngine._get_regime_adjusted_picks_from_seq(
                                full_seq[:t], hz_t, zm_t, a, lock_head, use_circuit_breaker
                            )

                    algo_states_by_t[a][t] = {
                        "algo_idx": a, "name": algo_name, "picks": picks_t,
                        "step": step_t, "win_rate_val": win_rate_val, "is_bust_alert": is_bust_alert,
                    }

                if won_a or steps_a == 3:
                    settle_idx_a = idx_a + steps_a - 1
                    settled_rounds.append((settle_idx_a, won_a, in_cd, not won_a))
                    if in_cd:
                        if won_a:
                            in_cd = False
                    else:
                        if not won_a and use_circuit_breaker and regime_a["regime"] == "COLD_DEFENSE":
                            in_cd = True
                    idx_a += steps_a
                else:
                    break

        all_details = []
        settled_outcomes = []
        consecutive_bust_count = 0
        last_round_bust = False
        in_cooldown = False
        codes_count = default_codes_count
        be_3_rate = default_be_rate
        edge_mult = 1.0
        bets = default_bets
        last_pending_picks = []
        last_pending_algo_name = ""

        i = 5
        round_idx = 1
        while i < total_len:
            cands = [algo_states_by_t[a][i] for a in algo_ids if i in algo_states_by_t[a]]
            if not cands:
                break

            z_freq = {}
            for c in cands:
                for z in c["picks"]:
                    z_freq[z] = z_freq.get(z, 0) + 1

            best_cand = None
            best_score = -1.0
            for c in cands:
                step_bonus = 10.0 if c["step"] == 2 else (15.0 if c["step"] == 3 else 5.0)
                if c["is_bust_alert"]:
                    step_bonus -= 10.0
                avg_cons = sum(z_freq.get(z, 1) for z in c["picks"]) / max(1, len(c["picks"]))
                conf_score = min(98.5, max(50.0, c["win_rate_val"] * 0.55 + (avg_cons / 5.0) * 30.0 + step_bonus))
                if conf_score > best_score:
                    best_score = conf_score
                    best_cand = c

            picks = best_cand["picks"]
            chosen_algo_idx = best_cand["algo_idx"]
            chosen_algo_name = best_cand["name"]
            chosen_conf = round(best_score, 1)

            head_z = ZodiacCalendarEngine.get_zodiac_by_date(full_dates[i - 1])
            z_to_nums, _ = zodiac_map_cache[head_z]
            regime_info = BayesianRegimeEngine.compute_regime_from_seq(full_seq[:i], head_z, lock_head=lock_head)

            picks_str = "-".join(picks)
            round_codes = set()
            for z in picks:
                round_codes.update(z_to_nums.get(z, []))
            codes_count = max(1, len(round_codes))

            edge_mult, be_3_rate = AnalyticsEngine.compute_edge_matched_multiplier(
                settled_outcomes, codes_count, odds, regime_info, use_circuit_breaker
            )
            t_profit = max(10, to_int(500 * edge_mult))
            base_b = max(1, to_int(10 * edge_mult))
            bets = AnalyticsEngine.compute_adaptive_bets(base_b, codes_count, stages=3, odds=odds, mode=mode_text, target_profit=t_profit)

            r_cost, r_payout, won, hit_step, last_hit_code, last_hit_z, actual_steps_run = 0, 0, False, 0, 0, "", 0
            for s in range(min(3, total_len - i)):
                actual_steps_run += 1
                idx_cur = i + s
                act_code = full_codes[idx_cur]
                act_z = full_seq[idx_cur]
                r_cost += bets[s] * codes_count
                if act_z in picks:
                    r_payout = bets[s] * odds
                    r_pnl = r_payout - r_cost
                    won = True
                    hit_step = s + 1
                    last_hit_code = act_code
                    last_hit_z = act_z
                    break

            if won:
                settle_idx = i + hit_step - 1
                i += hit_step
                status_txt = f"第 {hit_step} 期命中"
            else:
                if actual_steps_run == 3:
                    r_pnl = -r_cost
                    settle_idx = i + 2
                    last_hit_code = full_codes[settle_idx]
                    last_hit_z = full_seq[settle_idx]
                    i += 3
                    status_txt = "3期断缆"
                else:
                    if not in_cooldown:
                        last_pending_picks = picks
                        last_pending_algo_name = chosen_algo_name
                    break

            used_steps = hit_step if won else 3
            used_bets = bets[:used_steps]
            used_stakes = [b * codes_count for b in used_bets]

            if in_cooldown:
                all_details.append({
                    "round_title": "虚拟试探", "algo_idx": chosen_algo_idx, "algo_name": chosen_algo_name,
                    "conf_score": chosen_conf, "period_display": full_pdisplays[settle_idx],
                    "settle_period": full_periods[settle_idx], "settle_idx": settle_idx, "step_count": used_steps,
                    "codes_count": codes_count, "bets_used": used_bets, "stakes_used": used_stakes,
                    "payout": 0, "picks_str": picks_str, "hit_code": last_hit_code, "hit_z": last_hit_z,
                    "status_txt": "虚拟命中 (解除熔断)" if won else "虚拟断缆 (吸收风险)",
                    "cost": 0, "pnl": 0, "is_cooldown": True, "won": won,
                })
                if won:
                    in_cooldown = False
                continue

            all_details.append({
                "round_title": f"第 {round_idx} 轮", "algo_idx": chosen_algo_idx, "algo_name": chosen_algo_name,
                "conf_score": chosen_conf, "period_display": full_pdisplays[settle_idx],
                "settle_period": full_periods[settle_idx], "settle_idx": settle_idx, "step_count": used_steps,
                "codes_count": codes_count, "bets_used": used_bets, "stakes_used": used_stakes,
                "payout": r_payout, "picks_str": picks_str, "hit_code": last_hit_code, "hit_z": last_hit_z,
                "status_txt": status_txt, "cost": r_cost, "pnl": r_pnl, "is_cooldown": False, "won": won,
            })
            settled_outcomes.append(won)

            if not won:
                if last_round_bust:
                    consecutive_bust_count += 1
                last_round_bust = True
                recent_wr = (sum(1 for w in settled_outcomes[-18:] if w) / len(settled_outcomes[-18:])) if settled_outcomes else 1.0
                neg_edge_slump = len(settled_outcomes) >= 8 and recent_wr < be_3_rate
                if use_circuit_breaker and (regime_info["regime"] == "COLD_DEFENSE" or neg_edge_slump):
                    in_cooldown = True
            else:
                last_round_bust = False

            round_idx += 1

        pending_step = (total_len - i) + 1 if i < total_len else 1
        if pending_step > 3:
            pending_step = 1

        base_res = {
            "bets": bets, "codes_in_round": codes_count, "be_3_rate": be_3_rate,
            "last_edge_mult": edge_mult, "all_details": all_details, "next_step": pending_step,
            "last_pending_picks": last_pending_picks, "last_pending_algo_name": last_pending_algo_name,
            "in_cooldown": in_cooldown, "total_len": total_len,
        }
        return AnalyticsEngine.slice_backtest_result(base_res, span_limit)

    @staticmethod
    def get_algo_live_status(raw_rows, algo_idx, lock_head=True, span_limit=7, use_circuit_breaker=True, detailed_backtest_res=None, odds=47):
        if not raw_rows or len(raw_rows) < 5:
            return {
                "picks": [], "step": 1, "dist_bust": "数据不足", "dist_bust_color": "#94A3B8",
                "period_rate": "0.0% (0/0轮)", "regime": "MOMENTUM_ATTACK", "regime_desc": "数据不足", "bet_multiplier": 1.0,
            }

        chrono_rows = AnalyticsEngine.ensure_chrono(raw_rows)
        total_len = len(chrono_rows)

        if detailed_backtest_res and detailed_backtest_res.get("all_details") and detailed_backtest_res.get("span_limit") == span_limit:
            full_res = detailed_backtest_res
        else:
            full_res = AnalyticsEngine.simulate_walk_forward_backtest(
                raw_rows, span_limit, algo_idx, "盈利型(恒定每期盈利)", lock_head, use_circuit_breaker, odds=odds
            )

        scan_details = full_res.get("all_details", []) or full_res.get("details", [])
        current_step = full_res.get("next_step", 1)
        in_cooldown = full_res.get("in_cooldown", False)
        picks_latest, mult_latest, regime_info, _ = AnalyticsEngine.get_regime_adjusted_picks(
            chrono_rows, algo_idx, lock_head, use_circuit_breaker
        )

        if not in_cooldown and current_step > 1 and full_res.get("last_pending_picks"):
            picks = full_res["last_pending_picks"]
        else:
            picks = picks_latest
            if in_cooldown:
                current_step = 1

        last_bust_detail_pos = None
        for idx in range(len(scan_details) - 1, -1, -1):
            if "断缆" in scan_details[idx].get("status_txt", ""):
                last_bust_detail_pos = idx
                break

        if last_bust_detail_pos is not None:
            last_bust_idx = scan_details[last_bust_detail_pos].get("settle_idx", total_len - 1)
            dist_bust_periods = max(0, (total_len - 1) - last_bust_idx)
            win_rounds_after_bust = len([d for d in scan_details[last_bust_detail_pos + 1:] if not d.get("is_cooldown", False)])
            if dist_bust_periods == 0:
                dist_bust_str, dist_bust_color = "上轮计划断缆 (警惕)", "#F87171"
            else:
                dist_bust_str, dist_bust_color = f"连胜 {win_rounds_after_bust} 轮 (共{dist_bust_periods}期)", "#38BDF8"
        else:
            total_real_rounds = len([d for d in scan_details if not d.get("is_cooldown", False)])
            dist_bust_str, dist_bust_color = f"全样本连胜 ({total_real_rounds}轮/{len(raw_rows)}期)", "#10B981"

        min_idx = max(0, total_len - span_limit)
        recent_rounds = [d for d in scan_details if d.get("settle_idx", -1) >= min_idx and not d.get("is_cooldown", False)]
        if recent_rounds:
            tot_r = len(recent_rounds)
            win_r = sum(1 for d in recent_rounds if d.get("won", False))
            period_rate_str = f"{(win_r / tot_r * 100.0):.1f}% ({win_r}/{tot_r}轮)"
        else:
            period_rate_str = "0.0% (0/0轮)"

        return {
            "picks": picks, "step": current_step, "dist_bust": dist_bust_str,
            "dist_bust_color": dist_bust_color, "period_rate": period_rate_str,
            "regime": regime_info["regime"],
            "regime_desc": regime_info["desc"] + (" [冷却试探]" if in_cooldown else ""),
            "bet_multiplier": mult_latest,
        }

    @staticmethod
    def _calc_max_consec_miss(sub_seq, target_set, ignore_vals=None):
        max_miss, cur_miss = 0, 0
        for item in sub_seq:
            if ignore_vals and item in ignore_vals:
                continue
            if item in target_set:
                cur_miss = 0
            else:
                cur_miss += 1
                if cur_miss > max_miss:
                    max_miss = cur_miss
        return max_miss

    @staticmethod
    def get_multi_dim_metrics(rows, span_limit=30, precomputed_all33=None):
        if not rows:
            return []
        all_sp = [to_int(r.get("特码"), 0) for r in rows]
        all_dates = [str(r.get("开奖时间", "") or "") for r in rows]
        all_z = [num_to_zodiac(val, d) for val, d in zip(all_sp, all_dates)]

        seq_map = {
            "五行": [LottoAttrClassifier.get_wuxing(n, d) for n, d in zip(all_sp, all_dates)],
            "半波": [LottoAttrClassifier.get_half_wave(n) for n in all_sp],
            "大小": ["和局" if n == 49 else ("大" if n >= 25 else "小") for n in all_sp],
            "单双": ["和局" if n == 49 else ("单" if n % 2 != 0 else "双") for n in all_sp],
            "生肖区": [
                "一区(鼠牛虎)" if z in ("鼠", "牛", "虎") else (
                    "二区(兔龙蛇)" if z in ("兔", "龙", "蛇") else (
                        "三区(马羊猴)" if z in ("马", "羊", "猴") else "四区(鸡狗猪)"
                    )
                ) for z in all_z
            ],
            "波色": [LottoAttrClassifier.get_color(n) for n in all_sp],
            "家禽野兽": [LottoAttrClassifier.get_poultry_beast(z) for z in all_z],
            "头数": [LottoAttrClassifier.get_head_group(n) for n in all_sp],
            "尾数大小": [LottoAttrClassifier.get_tail_size(n) for n in all_sp],
            "合数单双": [LottoAttrClassifier.get_sum_oe(n) for n in all_sp],
        }

        prior_map = {
            "五行": 10.0 / 49.0, "半波": 8.0 / 49.0, "大小": 24.0 / 48.0, "单双": 24.0 / 48.0,
            "生肖区": 12.25 / 49.0, "波色": 16.33 / 49.0, "家禽野兽": 24.5 / 49.0,
            "头数": 9.8 / 49.0, "尾数大小": 24.5 / 49.0, "合数单双": 24.5 / 49.0,
        }

        base_items = precomputed_all33 if precomputed_all33 is not None else AnalyticsEngine.get_all_multi_dim_metrics(rows, len(rows))
        if not base_items:
            return []

        scored_candidates = []
        for item in base_items:
            r_type = item.get("raw_type", "")
            r_vals = item.get("raw_vals", [])
            if not r_vals or r_type not in seq_map:
                continue
            target_val = r_vals[0]
            seq_desc = seq_map[r_type]
            ignore_set = {"和局"} if r_type in ("大小", "单双") else set()
            valid_desc = [x for x in seq_desc if x not in ignore_set]
            n_valid = len(valid_desc)
            if n_valid < 5:
                continue

            cur_om = next((idx for idx, x in enumerate(valid_desc) if x == target_val), n_valid)
            chrono_valid = list(reversed(valid_desc))
            intervals, run_miss = [], 0
            for x in chrono_valid:
                if x == target_val:
                    intervals.append(run_miss)
                    run_miss = 0
                else:
                    run_miss += 1
            full_max_miss = max(1, max([cur_om, run_miss] + (intervals if intervals else [0])))
            mean_om = (sum(intervals) / len(intervals)) if intervals else max(2.0, (1.0 / prior_map.get(r_type, 0.2)) - 1.0)

            at_risk = sum(1 for iv in intervals if iv >= cur_om)
            hit_now = sum(1 for iv in intervals if iv == cur_om)
            hazard_rate = (hit_now + 0.5) / (at_risk + 1.5)

            extremum_ratio = cur_om / full_max_miss
            if extremum_ratio >= 0.85:
                extremum_score = 32.0 + min(12.0, (extremum_ratio - 0.85) * 40.0)
            elif extremum_ratio >= 0.55:
                extremum_score = 18.0 + (extremum_ratio - 0.55) * 46.0
            else:
                extremum_score = 6.0 + extremum_ratio * 20.0

            prior_p = prior_map.get(r_type, 0.25)
            w15 = valid_desc[:min(15, n_valid)]
            w45 = valid_desc[:min(45, n_valid)]
            post_15 = (w15.count(target_val) + 4.0 * prior_p) / (len(w15) + 4.0)
            post_45 = (w45.count(target_val) + 8.0 * prior_p) / (len(w45) + 8.0)
            full_hit_rate = valid_desc.count(target_val) / n_valid
            bayes_rel = (0.40 * post_15 + 0.35 * post_45 + 0.25 * full_hit_rate) / max(0.05, prior_p)
            bayes_score = min(28.0, bayes_rel * 16.0)

            last1 = valid_desc[0]
            last2 = valid_desc[1] if n_valid >= 2 else None
            t1_cnt, t1_tot, t2_cnt, t2_tot = 0, 0, 0, 0
            for k in range(1, n_valid):
                if valid_desc[k] == last1:
                    t1_tot += 1
                    if valid_desc[k - 1] == target_val:
                        t1_cnt += 1
                if last2 is not None and k >= 2 and valid_desc[k] == last2:
                    t2_tot += 1
                    if valid_desc[k - 2] == target_val:
                        t2_cnt += 1
            p_m1 = (t1_cnt + 0.5 * prior_p) / (t1_tot + 0.5)
            p_m2 = (t2_cnt + 0.5 * prior_p) / (t2_tot + 0.5)
            markov_score = min(24.0, ((0.65 * p_m1 + 0.35 * p_m2) / max(0.05, prior_p)) * 13.5)

            composite_score = hazard_rate * 26.0 + extremum_score + bayes_score + markov_score
            rem_to_max = max(1, full_max_miss - cur_om)
            est_window = 1 if (extremum_ratio >= 0.72 or hazard_rate >= 0.35) else min(3, max(1, int(round(mean_om - cur_om)) if cur_om < mean_om else 1))
            est_prob_pct = min(96.5, max(52.0, 48.0 + composite_score * 0.48))

            cand = dict(item)
            cand["cnt"] = f"{valid_desc.count(target_val)}次(全量{n_valid}期)"
            cand["om"] = f"{cur_om}期(均{mean_om:.1f})"
            cand["max_miss"] = f"{full_max_miss}期"
            cand["prob"] = f"预计{est_window}期内(余{rem_to_max}期)"
            cand["rate"] = f"{est_prob_pct:.1f}%(胜率{full_hit_rate*100:.1f}%)"
            cand["_rank_score"] = composite_score
            scored_candidates.append(cand)

        scored_candidates.sort(key=lambda x: x["_rank_score"], reverse=True)
        top3_picks, used_dims = [], set()
        for cand in scored_candidates:
            if cand["dim"] not in used_dims:
                top3_picks.append(cand)
                used_dims.add(cand["dim"])
                if len(top3_picks) >= 3:
                    break
        return top3_picks

    @staticmethod
    def get_all_multi_dim_metrics(rows, span_limit=30):
        if not rows:
            return []
        calc_rows = rows[:span_limit]
        actual_span = len(calc_rows)
        all_sp = [to_int(r.get("特码"), 0) for r in rows]
        all_dates = [str(r.get("开奖时间", "") or "") for r in rows]
        all_z = [num_to_zodiac(val, d) for val, d in zip(all_sp, all_dates)]
        results = []

        def _add_group(dim_name, raw_type, all_seq, candidates, ignore_set=None, default_avg=4.0, is_two_side=False):
            sub_slice = all_seq[:actual_span]
            sub_valid = [x for x in sub_slice if not (ignore_set and x in ignore_set)]
            for label, members in candidates:
                m_set = set(members)
                cnt = sum(1 for x in sub_valid if x in m_set)
                om = next((idx for idx, x in enumerate(all_seq) if x in m_set), len(all_seq))
                if is_two_side:
                    prob_str = "预计1~2期内"
                else:
                    intervals, cur_i = [], 0
                    for x in all_seq:
                        if x in m_set:
                            if cur_i > 0:
                                intervals.append(cur_i)
                            cur_i = 0
                        else:
                            cur_i += 1
                    avg_om = (sum(intervals) / len(intervals)) if intervals else default_avg
                    prob_cycle = max(1, int(round(avg_om - om))) if om < avg_om else 1
                    prob_str = f"预计{prob_cycle}期内"
                max_miss = AnalyticsEngine._calc_max_consec_miss(sub_slice, m_set, ignore_vals=ignore_set)
                denom_cnt = len(sub_valid) if ignore_set else actual_span
                rate_str = f"{(cnt/denom_cnt)*100:.1f}% ({cnt}/{denom_cnt}期)" if denom_cnt else "50.0%"
                results.append({
                    "dim": dim_name, "val": f"【{label}】", "cnt": f"{cnt}次", "om": f"{om}期",
                    "max_miss": f"{max_miss}期", "prob": prob_str, "rate": rate_str,
                    "raw_type": raw_type, "raw_vals": [members[0] if raw_type in ("大小", "单双", "家禽野兽") else label],
                })

        _add_group("五行形态", "五行", [LottoAttrClassifier.get_wuxing(n, d) for n, d in zip(all_sp, all_dates)], [(w, [w]) for w in ["金", "木", "水", "火", "土"]], default_avg=5.0)
        _add_group("半波形态", "半波", [LottoAttrClassifier.get_half_wave(n) for n in all_sp], [(h, [h]) for h in ["红单", "红双", "蓝单", "蓝双", "绿单", "绿双"]], default_avg=6.0)
        _add_group("两面盘: 大小", "大小", ["和局" if n == 49 else ("大" if n >= 25 else "小") for n in all_sp], [("大", ["大"]), ("小", ["小"])], ignore_set={"和局"}, is_two_side=True)
        _add_group("两面盘: 单双", "单双", ["和局" if n == 49 else ("单" if n % 2 != 0 else "双") for n in all_sp], [("单", ["单"]), ("双", ["双"])], ignore_set={"和局"}, is_two_side=True)
        _add_group(
            "生肖分区", "生肖区", all_z,
            [("一区(鼠牛虎)", ["鼠", "牛", "虎"]), ("二区(兔龙蛇)", ["兔", "龙", "蛇"]), ("三区(马羊猴)", ["马", "羊", "猴"]), ("四区(鸡狗猪)", ["鸡", "狗", "猪"])],
            default_avg=4.0,
        )
        _add_group("波色形态", "波色", [LottoAttrClassifier.get_color(n) for n in all_sp], [(c, [c]) for c in ["红波", "蓝波", "绿波"]], default_avg=3.0)
        _add_group("家禽野兽", "家禽野兽", [LottoAttrClassifier.get_poultry_beast(z) for z in all_z], [("家禽", ["家禽(牛马羊鸡狗猪)"]), ("野兽", ["野兽(鼠虎兔龙蛇猴)"])], is_two_side=True)
        _add_group("头数分区", "头数", [LottoAttrClassifier.get_head_group(n) for n in all_sp], [(h, [h]) for h in ["0头(01-09)", "1头(10-19)", "2头(20-29)", "3头(30-39)", "4头(40-49)"]], default_avg=5.0)
        _add_group("尾数大小", "尾数大小", [LottoAttrClassifier.get_tail_size(n) for n in all_sp], [(t, [t]) for t in ["大尾(5-9)", "小尾(0-4)"]], is_two_side=True)
        _add_group("合数单双", "合数单双", [LottoAttrClassifier.get_sum_oe(n) for n in all_sp], [(s, [s]) for s in ["合单", "合双"]], is_two_side=True)
        return results


def resolve_target_codes(raw_type, raw_vals, latest_date=""):
    head_z = ZodiacCalendarEngine.get_zodiac_by_date(latest_date)
    _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
    w_map = LottoAttrClassifier.get_wuxing_map_by_date(latest_date)
    zone_map = {
        "一区(鼠牛虎)": ["鼠", "牛", "虎"],
        "二区(兔龙蛇)": ["兔", "龙", "蛇"],
        "三区(马羊猴)": ["马", "羊", "猴"],
        "四区(鸡狗猪)": ["鸡", "狗", "猪"],
    }
    target_codes = []
    if raw_type == "生肖":
        for z in raw_vals:
            target_codes.extend(z_to_nums.get(z, []))
    elif raw_type == "五行":
        for wx_name in raw_vals:
            target_codes.extend(w_map.get(wx_name, []))
    elif raw_type == "半波":
        for n in range(1, 50):
            if LottoAttrClassifier.get_half_wave(n) in raw_vals:
                target_codes.append(n)
    elif raw_type == "大小":
        target_codes = [n for n in range(1, 49) if ("大" if n >= 25 else "小") == raw_vals[0]]
    elif raw_type == "单双":
        target_codes = [n for n in range(1, 49) if ("单" if n % 2 != 0 else "双") == raw_vals[0]]
    elif raw_type == "生肖区":
        for z_name in raw_vals:
            for z in zone_map.get(z_name, []):
                target_codes.extend(z_to_nums.get(z, []))
    elif raw_type == "波色":
        for col_name in raw_vals:
            if col_name == "红波":
                target_codes.extend(LottoAttrClassifier.RED_BALLS)
            elif col_name == "蓝波":
                target_codes.extend(LottoAttrClassifier.BLUE_BALLS)
            elif col_name == "绿波":
                target_codes.extend(LottoAttrClassifier.GREEN_BALLS)
    elif raw_type == "家禽野兽":
        for pb_name in raw_vals:
            z_set = LottoAttrClassifier.POULTRY_ZODIACS if "家禽" in pb_name else LottoAttrClassifier.BEAST_ZODIACS
            for z in z_set:
                target_codes.extend(z_to_nums.get(z, []))
    elif raw_type == "头数":
        for h_name in raw_vals:
            for n in range(1, 50):
                if LottoAttrClassifier.get_head_group(n) == h_name:
                    target_codes.append(n)
    elif raw_type == "尾数大小":
        for t_name in raw_vals:
            for n in range(1, 50):
                if LottoAttrClassifier.get_tail_size(n) == t_name:
                    target_codes.append(n)
    elif raw_type == "合数单双":
        for s_name in raw_vals:
            for n in range(1, 50):
                if LottoAttrClassifier.get_sum_oe(n) == s_name:
                    target_codes.append(n)
    return sorted(list(set(target_codes)))
