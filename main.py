import os
import re
import json
import traceback
import threading
import time as pytime
from datetime import datetime
import flet as ft

from engine import (
    LottoDatabase,
    ZodiacCalendarEngine,
    LottoAttrClassifier,
    LottoScheduleConfig,
    RealHtmlParser,
    AnalyticsEngine,
    sync_official_data,
    resolve_target_codes,
    num_to_zodiac,
    to_int,
    format_odds_int,
    clean_year_str,
    normalize_target_key,
    get_storage_dir,
)

BG_DARK = "#0B0F17"
CARD_BG = "#131A26"
CARD_BG_ALT = "#161F2E"
BORDER_COLOR = "#232E42"
ACCENT_BLUE = "#1D63DC"
ACCENT_CYAN = "#38BDF8"
ACCENT_GREEN = "#10B981"
ACCENT_AMBER = "#FBBF24"
ACCENT_RED = "#F87171"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"


def single_line_text(text, size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"):
    return ft.Text(
        text,
        size=size,
        weight=weight,
        color=color,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


class SmoothMarquee(ft.Container):
    """缓速从右向左无缝循环滚动的走马灯组件"""

    def __init__(self, text="● 系统就绪", size=11, weight=ft.FontWeight.BOLD, color=ACCENT_GREEN):
        super().__init__(clip_behavior=ft.ClipBehavior.HARD_EDGE, height=24, expand=True)
        self._text_val = text
        self._size = size
        self._weight = weight
        self._color = color
        self._stop_event = threading.Event()
        self._pos_x = 0.0
        self._anim = ft.animation.Animation(180, ft.AnimationCurve.LINEAR)

        self._txt = ft.Text(
            self._text_val,
            size=self._size,
            weight=self._weight,
            color=self._color,
            max_lines=1,
        )
        self._mover = ft.Container(
            content=self._txt,
            offset=ft.transform.Offset(0.0, 0.0),
            animate_offset=self._anim,
        )
        self.content = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self._mover],
        )
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    @property
    def value(self):
        return self._text_val

    @value.setter
    def value(self, new_val):
        self._text_val = str(new_val)
        self._txt.value = self._text_val
        self._pos_x = 0.85
        self._mover.animate_offset = None
        self._mover.offset = ft.transform.Offset(self._pos_x, 0.0)
        if self.page is not None:
            try:
                self._mover.update()
            except Exception:
                pass
        self._mover.animate_offset = self._anim

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, new_color):
        self._color = new_color
        self._txt.color = new_color
        if self.page is not None:
            try:
                self._txt.update()
            except Exception:
                pass

    def _run_loop(self):
        while not self._stop_event.is_set():
            pytime.sleep(0.16)
            if self.page is None:
                continue
            if len(self._text_val) > 8:
                if self._pos_x <= -1.05:
                    self._pos_x = 0.95
                    self._mover.animate_offset = None
                    self._mover.offset = ft.transform.Offset(self._pos_x, 0.0)
                    try:
                        self._mover.update()
                    except Exception:
                        pass
                    self._mover.animate_offset = self._anim
                else:
                    self._pos_x -= 0.035
                    self._mover.animate_offset = self._anim
                    self._mover.offset = ft.transform.Offset(self._pos_x, 0.0)
                    try:
                        self._mover.update()
                    except Exception:
                        pass
            else:
                if self._pos_x != 0.0:
                    self._pos_x = 0.0
                    self._mover.animate_offset = None
                    self._mover.offset = ft.transform.Offset(0.0, 0.0)
                    try:
                        self._mover.update()
                    except Exception:
                        pass


def smooth_listview(controls, spacing=10):
    return ft.Column(
        expand=True,
        spacing=spacing,
        scroll=ft.ScrollMode.AUTO,
        controls=controls,
    )


def action_btn(label, on_click, bgcolor="#12945E", color="#FFFFFF", height=36, expand=False, width=None, disabled=False, size=12):
    return ft.ElevatedButton(
        content=single_line_text(label, size=size, weight=ft.FontWeight.BOLD, color=color),
        on_click=on_click,
        bgcolor=bgcolor,
        color=color,
        height=height,
        width=width,
        expand=expand,
        disabled=disabled,
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=10, vertical=0),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


def outline_btn(label, on_click, color=TEXT_PRIMARY, border_color="#334155", height=36, expand=False, width=None, disabled=False, size=12):
    return ft.OutlinedButton(
        content=single_line_text(label, size=size, weight=ft.FontWeight.BOLD, color=color),
        on_click=on_click,
        height=height,
        width=width,
        expand=expand,
        disabled=disabled,
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=10, vertical=0),
            side=ft.BorderSide(1, border_color),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


def card_box(content, padding=12):
    return ft.Container(
        content=content,
        bgcolor=CARD_BG,
        border=ft.border.all(1, BORDER_COLOR),
        border_radius=12,
        padding=padding,
    )


def pill_badge(text, color=ACCENT_CYAN, bg="#162235"):
    return ft.Container(
        content=single_line_text(text, size=11, weight=ft.FontWeight.BOLD, color=color),
        bgcolor=bg,
        border=ft.border.all(1, color),
        border_radius=8,
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
    )


def ball_chip(num_val, zodiac_str="", size=30):
    c_hex = LottoAttrClassifier.get_color_hex(num_val)
    txt = f"{str(int(num_val)).zfill(2)}\n{zodiac_str}" if zodiac_str else f"{str(int(num_val)).zfill(2)}"
    return ft.Container(
        content=ft.Text(txt, size=10 if zodiac_str else 12, weight=ft.FontWeight.BOLD, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
        width=size,
        height=size + (10 if zodiac_str else 0),
        bgcolor=c_hex,
        border_radius=size // 2,
        alignment=ft.alignment.center,
    )


class LottoQuantMobileApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "LottoQuant Pro"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG_DARK
        self.page.padding = 0
        self.page.spacing = 0

        self.raw_full_rows = []
        self.filtered_rows = []
        self.current_picks = []
        self.active_codes_count = 25
        self.active_stages = 3
        self.current_rec_metrics = []
        self.current_all_rec_metrics = []
        self._pnl_result_cards = []
        self.is_syncing = False
        self.current_tab_idx = 0
        self.active_dialog = None

        LottoDatabase.init_db()
        self.build_ui()
        self.auto_scan_local_first()
        threading.Thread(target=self._auto_sync_loop, daemon=True).start()

    def get_source_code(self):
        return "am" if self.dd_source.value == "澳门彩" else "hk"

    def get_current_odds(self):
        try:
            v = int(round(float((self.tf_odds.value or "47").strip())))
            if v > 0:
                return v
        except Exception:
            pass
        try:
            v = int(round(float(LottoDatabase.get_config("global_odds", "47"))))
            return v if v > 0 else 47
        except Exception:
            return 47

    def show_snack(self, msg, color=ACCENT_GREEN):
        self.lbl_status.value = f"● {msg}"
        self.lbl_status.color = color
        try:
            self.page.open(ft.SnackBar(content=ft.Text(msg, color="#FFFFFF", weight=ft.FontWeight.BOLD), bgcolor="#1E293B", duration=2000))
        except Exception:
            self.page.update()

    def copy_text(self, text_str, tip_prefix="已复制"):
        self.page.set_clipboard(text_str)
        cnt = len([x for x in text_str.split(",") if x.strip()])
        self.show_snack(f"{tip_prefix} ({cnt}项) 至剪贴板！", ACCENT_CYAN)

    def open_dialog(self, dlg):
        if self.active_dialog:
            try:
                self.page.close(self.active_dialog)
            except Exception:
                pass
        self.active_dialog = dlg
        self.page.open(dlg)

    def close_dialog(self, dlg=None):
        target = dlg or self.active_dialog
        if target:
            try:
                self.page.close(target)
            except Exception:
                self.page.update()

    def build_ui(self):
        self.dd_source = ft.Dropdown(
            value="澳门彩",
            options=[ft.dropdown.Option("澳门彩"), ft.dropdown.Option("香港彩")],
            width=96,
            height=38,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_color=BORDER_COLOR,
            bgcolor=BG_DARK,
            on_change=self.on_source_changed,
        )

        self.dd_pos = ft.Dropdown(
            value="特码",
            options=[ft.dropdown.Option(x) for x in ["特码", "平一", "平二", "平三", "平四", "平五", "平六"]],
            width=80,
            height=38,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_color=BORDER_COLOR,
            bgcolor=BG_DARK,
            on_change=self.on_filter_changed,
        )

        saved_odds = format_odds_int(LottoDatabase.get_config("global_odds", "47"))
        self.tf_odds = ft.TextField(
            value=saved_odds,
            width=52,
            height=38,
            text_size=13,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.padding.symmetric(horizontal=4, vertical=2),
            border_color="#D97706",
            bgcolor=BG_DARK,
            color=ACCENT_AMBER,
            on_submit=self.on_odds_changed,
            on_blur=self.on_odds_changed,
        )

        self.btn_sync = ft.IconButton(
            icon=ft.Icons.SYNC,
            icon_color="#FFFFFF",
            bgcolor="#12945E",
            width=36,
            height=36,
            icon_size=18,
            tooltip="同步官网最新开奖数据",
            on_click=self.trigger_sync_crawler,
        )

        btn_more = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            icon_color=TEXT_PRIMARY,
            items=[
                ft.PopupMenuItem(content=single_line_text("📋 官网原始开奖数据池", size=13, color=TEXT_PRIMARY), on_click=lambda e: self.open_raw_data_dialog()),
                ft.PopupMenuItem(content=single_line_text("🗑️ 清空当前彩种数据", size=13, color=ACCENT_RED), on_click=lambda e: self.confirm_clear_db()),
            ],
        )

        self.lbl_status = SmoothMarquee("● 系统就绪", size=11, weight=ft.FontWeight.BOLD, color=ACCENT_GREEN)
        self.lbl_schedule = single_line_text(LottoScheduleConfig.get_schedule_desc("am"), size=10, weight=ft.FontWeight.NORMAL, color=TEXT_SECONDARY)

        top_bar = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
            padding=ft.padding.only(left=10, right=4, top=6, bottom=8),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                expand=True,
                                controls=[
                                    single_line_text("⚡ LottoQuant", size=15, weight=ft.FontWeight.W_900, color=ACCENT_CYAN),
                                    ft.Container(content=self.lbl_schedule, expand=True),
                                ],
                            ),
                            ft.Row(spacing=2, controls=[self.btn_sync, btn_more]),
                        ],
                    ),
                    ft.Row(
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.dd_source,
                            self.dd_pos,
                            single_line_text("1:", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY),
                            self.tf_odds,
                            ft.Container(content=self.lbl_status, expand=True),
                        ],
                    ),
                ],
            ),
        )

        self.view_pool = self.build_tab_pool()
        self.view_plan = self.build_tab_plan()
        self.view_rec = self.build_tab_rec()
        self.view_live = self.build_tab_live()
        self.view_bt = self.build_tab_backtest()
        self.view_pnl = self.build_tab_pnl()

        self.all_views = [self.view_pool, self.view_plan, self.view_rec, self.view_live, self.view_bt, self.view_pnl]

        self.body_container = ft.Container(
            content=self.view_pool,
            expand=True,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
        )

        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=CARD_BG,
            indicator_color=ACCENT_BLUE,
            height=70,
            label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
            on_change=self.on_nav_changed,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.ANALYTICS_OUTLINED, selected_icon=ft.Icons.ANALYTICS, label="智能选号"),
                ft.NavigationBarDestination(icon=ft.Icons.TRENDING_UP_OUTLINED, selected_icon=ft.Icons.TRENDING_UP, label="追号倍投"),
                ft.NavigationBarDestination(icon=ft.Icons.DIAMOND_OUTLINED, selected_icon=ft.Icons.DIAMOND, label="多维推荐"),
                ft.NavigationBarDestination(icon=ft.Icons.SHIELD_OUTLINED, selected_icon=ft.Icons.SHIELD, label="实战看板"),
                ft.NavigationBarDestination(icon=ft.Icons.SMART_TOY_OUTLINED, selected_icon=ft.Icons.SMART_TOY, label="AI回测"),
                ft.NavigationBarDestination(icon=ft.Icons.MONETIZATION_ON_OUTLINED, selected_icon=ft.Icons.MONETIZATION_ON, label="周期盈利"),
            ],
        )

        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[top_bar, self.body_container, self.nav_bar],
                ),
            )
        )

    def on_nav_changed(self, e):
        self.switch_tab(e.control.selected_index)

    def switch_tab(self, idx):
        self.current_tab_idx = idx
        self.nav_bar.selected_index = idx
        self.body_container.content = self.all_views[idx]
        if idx == 3:
            self.render_live_battle_board()
        elif idx == 5:
            self._sync_pnl_list_controls()
            if len(self.raw_full_rows) >= 5 and not self._pnl_result_cards:
                self.trigger_background_analytics()
        self.page.update()

    def _sync_pnl_list_controls(self):
        if len(self.raw_full_rows) < 5:
            body_cards = [card_box(ft.Text("当前开奖记录不足 5 期，请先点击右上角同步按钮获取数据。", size=12, color=ACCENT_AMBER))]
        elif self._pnl_result_cards:
            body_cards = list(self._pnl_result_cards)
        else:
            body_cards = [card_box(ft.Text("正在测算各周期盈利矩阵，请稍候...", size=12, color=ACCENT_CYAN))]
        self.pnl_list_view.controls = [self._pnl_ctrl_card] + body_cards

    def build_tab_pool(self):
        self.dd_algo = ft.Dropdown(
            label="预测算法模型",
            value="智能六肖偏离量化算法 (HTML专属)",
            options=[
                ft.dropdown.Option("智能六肖偏离量化算法 (HTML专属)"),
                ft.dropdown.Option("马尔可夫转移概率 (实测前一)"),
                ft.dropdown.Option("⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)"),
                ft.dropdown.Option("🤖 多策略交叉共识模型 (低断缆推荐)"),
                ft.dropdown.Option("🏆 自适应三因子稳健融合模型 (优胜推荐)"),
            ],
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
        )

        self.dd_z_count = ft.Dropdown(
            label="选肖数",
            value="6肖",
            options=[ft.dropdown.Option(x) for x in ["3肖", "4肖", "5肖", "6肖", "8肖"]],
            width=90,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
        )

        self.tf_chase_stages = ft.TextField(
            label="追号期数",
            value="3",
            width=80,
            text_size=12,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
        )

        self.sw_lock_head = ft.Switch(label="锁定岁首5码", value=True, active_color=ACCENT_GREEN)

        self.lbl_pred_line1 = ft.Text("点击下方按钮生成预测方案", size=19, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER, text_align=ft.TextAlign.CENTER)
        self.lbl_pred_line2 = ft.Text("覆盖码数与单期理论命中概率将在此实时展示", size=12, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)

        signal_card = ft.Container(
            bgcolor=CARD_BG_ALT,
            border=ft.border.all(1, "#263349"),
            border_radius=10,
            padding=12,
            alignment=ft.alignment.center,
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, controls=[self.lbl_pred_line1, self.lbl_pred_line2]),
        )

        pred_card = card_box(
            ft.Column(
                spacing=10,
                controls=[
                    single_line_text("🎯 下期号码预测与追号联动", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                    self.dd_algo,
                    ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[self.dd_z_count, self.tf_chase_stages, self.sw_lock_head]),
                    signal_card,
                    ft.Row(
                        spacing=10,
                        controls=[
                            action_btn("✨ 生成预测", lambda e: self.exec_prediction(), bgcolor=ACCENT_BLUE, height=40, expand=True, size=13),
                            action_btn("≫ 同步追号 ➔", lambda e: self.apply_pred_to_chase_model(), bgcolor="#12945E", height=40, expand=True, size=13),
                        ],
                    ),
                ],
            )
        )

        self.omission_list = ft.Column(spacing=6)
        self.omission_mode_seg = ft.SegmentedButton(
            selected={"zodiac"},
            allow_multiple_selection=False,
            on_change=self.on_omission_mode_changed,
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=6, vertical=4)),
            segments=[
                ft.Segment(value="zodiac", label=single_line_text("生肖遗漏", size=12, color=TEXT_PRIMARY)),
                ft.Segment(value="hw", label=single_line_text("半波遗漏", size=12, color=TEXT_PRIMARY)),
                ft.Segment(value="bsoe", label=single_line_text("两面形态", size=12, color=TEXT_PRIMARY)),
            ],
        )

        omission_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    single_line_text("📊 多维遗漏实时监控", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                    ft.Row(controls=[ft.Container(content=self.omission_mode_seg, expand=True)]),
                    self.omission_list,
                ],
            )
        )

        self.history_list = ft.Column(spacing=6)
        history_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            single_line_text("🕒 近期开奖速览 (近50期)", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                            outline_btn("全量数据池 ➔", lambda e: self.open_raw_data_dialog(), height=30, size=11, color=ACCENT_CYAN, border_color="#2A374E"),
                        ],
                    ),
                    self.history_list,
                ],
            )
        )

        return smooth_listview([pred_card, omission_card, history_card])

    def on_omission_mode_changed(self, e):
        self.render_omission_section()
        self.omission_list.update()

    def render_omission_section(self):
        items = []
        if not self.filtered_rows:
            items.append(ft.Text("暂无开奖数据", color=TEXT_SECONDARY, size=12))
            self.omission_list.controls = items
            return

        pos = self.dd_pos.value or "特码"
        mode = list(self.omission_mode_seg.selected)[0] if self.omission_mode_seg.selected else "zodiac"

        if mode == "zodiac":
            for row in AnalyticsEngine.get_metrics(self.filtered_rows, pos):
                om_v = int(row["当前遗漏"])
                st = str(row["状态"])
                st_col = ACCENT_RED if "热" in st else (ACCENT_CYAN if "冷" in st else TEXT_SECONDARY)
                items.append(
                    ft.Container(
                        bgcolor=CARD_BG_ALT,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=7),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(spacing=6, controls=[
                                    ft.Text(f"{row['生肖']}", size=15, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                                    ft.Text(f"({row['包含码数']}码·出{row['出现次数']}次)", size=11, color=TEXT_SECONDARY),
                                ]),
                                ft.Row(spacing=6, controls=[
                                    ft.Text(f"遗漏{om_v}期(均{row['平均遗漏']})", size=11, color=ACCENT_AMBER if om_v == 0 else TEXT_PRIMARY),
                                    pill_badge(st, st_col),
                                ]),
                            ],
                        ),
                    )
                )
        elif mode == "hw":
            for row in AnalyticsEngine.get_half_wave_metrics(self.filtered_rows):
                items.append(
                    ft.Container(
                        bgcolor=CARD_BG_ALT,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=7),
                        content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Text(f"【{row['半波']}】", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                            ft.Text(f"出{row['开出次数']}次 | 遗漏{row['当前遗漏']}期 | 均{row['平均遗漏']}", size=11, color=TEXT_PRIMARY),
                        ]),
                    )
                )
        else:
            for row in AnalyticsEngine.get_bs_oe_metrics(self.filtered_rows):
                items.append(
                    ft.Container(
                        bgcolor=CARD_BG_ALT,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=7),
                        content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Text(f"【{row['两面形态']}】", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                            ft.Text(f"出{row['开出次数']}次 | 遗漏{row['当前遗漏']}期 | 均{row['平均遗漏']}", size=11, color=TEXT_PRIMARY),
                        ]),
                    )
                )
        self.omission_list.controls = items

    def build_tab_plan(self):
        self.lbl_active_picks = ft.Text("未同步 (默认25码)", size=13, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER)
        self.lbl_plan_be_info = ft.Text("结算赔率 1:47 | 3期盈亏平衡门槛: --", size=11, color=ACCENT_CYAN)

        self.tf_target_profit = ft.TextField(
            label="目标盈利(元)",
            value="500",
            width=115,
            text_size=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.update_chase_table(refresh_ui=True),
        )

        self.dd_plan_mode = ft.Dropdown(
            label="倍投策略模式",
            value="盈利型(恒定每期盈利)",
            options=[
                ft.dropdown.Option("盈利型(恒定每期盈利)"),
                ft.dropdown.Option("盈利型(递增每期盈利)"),
                ft.dropdown.Option("防守型(前攻后守保本)"),
                ft.dropdown.Option("平注均衡型(1:1:1无倍投)"),
            ],
            expand=True,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.update_chase_table(refresh_ui=True),
        )

        ctrl_card = card_box(
            ft.Column(
                spacing=10,
                controls=[
                    single_line_text("📈 追号与对冲倍投精算参数", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                    self.lbl_active_picks,
                    self.lbl_plan_be_info,
                    ft.Row(spacing=8, controls=[self.tf_target_profit, self.dd_plan_mode]),
                    ft.Row(controls=[action_btn("💼 确认追号计划并推送至【实战看板】➔", lambda e: self.commit_chase_plan_to_live(), bgcolor="#12945E", height=42, expand=True, size=13)]),
                ],
            )
        )

        self.plan_schedule_list = ft.Column(spacing=8)
        schedule_card = card_box(
            ft.Column(spacing=8, controls=[single_line_text("📋 分期倍投排期明细表", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN), self.plan_schedule_list])
        )

        return smooth_listview([ctrl_card, schedule_card])

    def update_chase_table(self, refresh_ui=False):
        codes = max(1, self.active_codes_count)
        stages = max(1, self.active_stages)
        try:
            target_p = max(10, int((self.tf_target_profit.value or "500").strip()))
        except Exception:
            target_p = 500
        mode = self.dd_plan_mode.value or "盈利型(恒定每期盈利)"
        odds = self.get_current_odds()
        be_3 = AnalyticsEngine.calc_breakeven_3_rate(codes, odds)

        self.lbl_plan_be_info.value = f"结算赔率 1:{odds} | 覆盖 {codes} 码 | 3期平衡门槛: {be_3:.1%}"
        step_bets = AnalyticsEngine.compute_adaptive_bets(10, codes, stages, odds, mode, target_profit=target_p)

        items = []
        cum_cost = 0
        for s in range(1, stages + 1):
            bet = step_bets[s - 1]
            cur_cost = bet * codes
            cum_cost += cur_cost
            payout = bet * odds
            pnl = payout - cum_cost
            pnl_col = ACCENT_GREEN if pnl >= 0 else ACCENT_RED

            if "平注" in mode:
                note = "零杠杆等额平注 (极端防爆仓)"
            elif "盈利型(递增" in mode:
                note = f"首期 {bet} 倍起投" if s == 1 else ("次期递增扩利" if s == 2 else "末期高倍收割")
            elif "盈利型(恒定" in mode:
                note = f"恒定净利精算 (目标+{target_p}元)"
            elif "防守型" in mode:
                note = "首期强攻主利" if s == 1 else ("次期微利压本" if s == 2 else "零溢价精确保本撤退")
            else:
                note = "动态精算"

            items.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border=ft.border.all(1, BORDER_COLOR),
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text(f"第 {s} 期 · 单码 {bet} 元/码", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                                ft.Text(f"净利 {pnl:+d} 元", size=14, weight=ft.FontWeight.BOLD, color=pnl_col),
                            ]),
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text(f"当期 {cur_cost:,} 元 | 累计 {cum_cost:,} 元", size=11, color=TEXT_SECONDARY),
                                ft.Text(f"返还 {payout:,} 元", size=11, color=ACCENT_CYAN),
                            ]),
                            ft.Text(f"💡 {note}", size=11, color=TEXT_SECONDARY),
                        ],
                    ),
                )
            )
        self.plan_schedule_list.controls = items
        if refresh_ui:
            try:
                self.plan_schedule_list.update()
            except Exception:
                self.page.update()

    def build_tab_rec(self):
        self.lbl_rec_summary = ft.Text("🧬 全量历史深度多维量化引擎：等待数据加载...", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN)
        self.top3_rec_list = ft.Column(spacing=8)

        self.dd_rec_period = ft.Dropdown(
            label="参考周期",
            value="90期",
            options=[ft.dropdown.Option(x) for x in ["30期", "60期", "90期", "120期", "180期", "240期", "300期", "全量历史"]],
            width=112,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.trigger_background_analytics(),
        )
        self.all33_rec_list = ft.Column(spacing=8)

        top_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        single_line_text("🏆 全站多维 Top-3 黄金优选", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                        ft.IconButton(icon=ft.Icons.REFRESH, icon_color=ACCENT_GREEN, width=34, height=34, on_click=lambda e: self.trigger_background_analytics()),
                    ]),
                    ft.Container(bgcolor=CARD_BG_ALT, padding=10, border_radius=8, content=self.lbl_rec_summary),
                    self.top3_rec_list,
                ],
            )
        )

        all_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        single_line_text("📊 全量 33 项多维形态全表", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                        self.dd_rec_period,
                    ]),
                    self.all33_rec_list,
                ],
            )
        )

        return smooth_listview([top_card, all_card])

    def _build_rec_item_card(self, m, src, latest_date, is_top3=False):
        target_codes = resolve_target_codes(m["raw_type"], m["raw_vals"], latest_date)
        codes_display_str = ", ".join(str(n).zfill(2) for n in target_codes)
        target_str = ", ".join(m["raw_vals"])
        is_active = LottoDatabase.is_target_active(src, m["raw_type"], target_str)
        span_val = max(1, len(self.raw_full_rows)) if is_top3 else self._get_rec_reference_span()

        return ft.Container(
            bgcolor=CARD_BG_ALT,
            border=ft.border.all(1, "#2A3954" if is_top3 else BORDER_COLOR),
            border_radius=10,
            padding=10,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        ft.Row(spacing=6, controls=[
                            pill_badge(m["dim"], ACCENT_CYAN),
                            single_line_text(f"{m['val']} ({len(target_codes)}码)", size=13, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                        ]),
                        single_line_text(f"遗漏{m['om']}", size=11, weight=ft.FontWeight.BOLD, color=ACCENT_RED),
                    ]),
                    ft.Text(f"极值: {m['max_miss']} | {m['prob']} · {m['rate']}", size=11, color=ACCENT_GREEN),
                    ft.Text(f"号码: {codes_display_str}", size=12, color=TEXT_PRIMARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(spacing=6, controls=[
                        outline_btn("🔍 穿透", lambda e, item=m, sp=span_val: self.open_multidim_detail_dialog(item, sp), height=34),
                        outline_btn("📋 复制", lambda e, cs=codes_display_str: self.copy_text(cs, "已复制推荐号码"), height=34),
                        action_btn(
                            "✔ 已跟投" if is_active else "🎯 一键投注",
                            lambda e, tt=m["raw_type"], tv=m["raw_vals"], tc=target_codes: self.open_quick_bet_dialog(tt, tv, tc),
                            bgcolor="#334155" if is_active else "#12945E",
                            height=34,
                            expand=True,
                        ),
                    ]),
                ],
            ),
        )

    def build_tab_live(self):
        self.dd_live_span = ft.Dropdown(
            value="全周期汇总",
            options=[ft.dropdown.Option(x) for x in ["近单周 (7天)", "近单月 (30天)", "近季度 (90天)", "近半年度 (180天)", "近年度 (365天)", "全周期汇总"]],
            width=136,
            height=38,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=2),
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.render_live_battle_board(),
        )

        self.lbl_bayesian_badge = single_line_text("盘口: 识别中...", size=11, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN)

        self.kpi_cost = single_line_text("0 元", size=14, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY)
        self.kpi_win = single_line_text("0 元", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER)
        self.kpi_pnl = single_line_text("+0 元", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_GREEN)
        self.kpi_roi = single_line_text("0.0%", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN)
        self.kpi_wr = single_line_text("0.0%", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN)
        self.kpi_bust = single_line_text("0 轮", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_RED)

        def kpi_mini_card(title, val_ctrl, accent):
            return ft.Container(
                bgcolor=CARD_BG_ALT,
                border=ft.border.only(left=ft.BorderSide(3, accent)),
                border_radius=8,
                padding=8,
                expand=True,
                content=ft.Column(spacing=2, controls=[single_line_text(title, size=10, weight=ft.FontWeight.NORMAL, color=TEXT_SECONDARY), val_ctrl]),
            )

        kpi_grid = ft.Column(
            spacing=6,
            controls=[
                ft.Row(spacing=6, controls=[kpi_mini_card("实盘累计投入", self.kpi_cost, TEXT_SECONDARY), kpi_mini_card("累计奖金返还", self.kpi_win, ACCENT_AMBER)]),
                ft.Row(spacing=6, controls=[kpi_mini_card("累计纯净盈亏", self.kpi_pnl, ACCENT_GREEN), kpi_mini_card("综合回报率", self.kpi_roi, ACCENT_CYAN)]),
                ft.Row(spacing=6, controls=[kpi_mini_card("计划胜出率", self.kpi_wr, ACCENT_CYAN), kpi_mini_card("断缆止损轮次", self.kpi_bust, ACCENT_RED)]),
            ],
        )

        self.lbl_next_bet_prompt = ft.Text("当前暂无进行中的追号计划。", size=12, color=ACCENT_AMBER, weight=ft.FontWeight.BOLD)

        top_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        self.dd_live_span,
                        ft.Container(bgcolor="#132238", border=ft.border.all(1, "#1E3A8A"), border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=6), expand=True, content=self.lbl_bayesian_badge),
                    ]),
                    kpi_grid,
                    ft.Row(spacing=6, controls=[
                        action_btn("📋 挂单明细", lambda e: self.open_live_pending_dialog(), bgcolor=ACCENT_BLUE, height=34, expand=True),
                        outline_btn("📜 历史档案", lambda e: self.open_live_archive_dialog(), height=34, expand=True),
                        action_btn("🔍 自动验奖", lambda e: self.auto_verify_live_bets(notify=True), bgcolor="#12945E", height=34, expand=True),
                    ]),
                    ft.Container(bgcolor=CARD_BG_ALT, border_radius=8, padding=8, content=self.lbl_next_bet_prompt),
                ],
            )
        )

        self.plan_eval_list = ft.Column(spacing=6)
        eval_card = card_box(ft.Column(spacing=6, controls=[single_line_text("🏆 所投方案综合评测分析", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN), self.plan_eval_list]))

        self.live_bets_list = ft.Column(spacing=8)
        orders_card = card_box(ft.Column(spacing=8, controls=[single_line_text("📌 实盘单据跟踪明细 (进行中任务)", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER), self.live_bets_list]))

        return smooth_listview([top_card, eval_card, orders_card])

    def build_tab_backtest(self):
        self.lbl_bt_smart_title = ft.Text("🎯 综合优选组合: 等待数据加载...", size=13, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER)
        self.lbl_bt_smart_params = ft.Text("● 置信度与可选性参数: 暂无数据", size=11, color=TEXT_SECONDARY)
        self.lbl_bt_smart_conf = single_line_text("置信度: --", size=11, weight=ft.FontWeight.BOLD, color="#34D399")

        self.btn_smart_history = outline_btn("📊 回测明细", None, height=34, disabled=True)
        self.btn_smart_copy = outline_btn("📋 复制号码", None, height=34, disabled=True)
        self.btn_smart_bet = action_btn("🎯 一键跟投", None, bgcolor="#12945E", height=34, expand=True, disabled=True)

        smart_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        single_line_text("🧠 AI 智能交叉优选", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                        ft.Container(bgcolor="#0D3B2E", border=ft.border.all(1, ACCENT_GREEN), border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=4), content=self.lbl_bt_smart_conf),
                    ]),
                    self.lbl_bt_smart_title,
                    self.lbl_bt_smart_params,
                    ft.Row(spacing=6, controls=[self.btn_smart_history, self.btn_smart_copy, self.btn_smart_bet]),
                ],
            )
        )

        self.sw_board_lock = ft.Switch(label="锁定岁首5码", value=False, active_color=ACCENT_GREEN, on_change=self.on_board_ctrl_changed)
        self.sw_board_cb = ft.Switch(label="期望差熔断", value=True, active_color=ACCENT_GREEN, on_change=self.on_board_ctrl_changed)
        self.dd_board_span = ft.Dropdown(
            value="本月 (30期)",
            options=[ft.dropdown.Option(x) for x in ["本周 (7期)", "本月 (30期)", "双月 (60期)", "本季 (90期)", "半年 (180期)", "本年 (365期)"]],
            width=122,
            height=38,
            text_size=12,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=2),
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=self.on_board_ctrl_changed,
        )
        self.algo_status_list = ft.Column(spacing=8)

        algo_board_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        single_line_text("🎯 核心算法实盘动态矩阵", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                        self.dd_board_span,
                    ]),
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[self.sw_board_lock, self.sw_board_cb]),
                    self.algo_status_list,
                ],
            )
        )

        self.dd_bt_periods = ft.Dropdown(
            label="回测周期",
            value="30期",
            options=[ft.dropdown.Option(x) for x in ["7期", "30期", "60期", "90期", "120期", "180期", "240期", "300期"]],
            width=102,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.execute_advanced_backtest(),
        )
        self.dd_bt_algo = ft.Dropdown(
            label="测试算法",
            value="智能六肖偏离量化算法 (HTML专属)",
            options=[
                ft.dropdown.Option("智能六肖偏离量化算法 (HTML专属)"),
                ft.dropdown.Option("马尔可夫转移概率 (实测前一)"),
                ft.dropdown.Option("⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)"),
                ft.dropdown.Option("🤖 多策略交叉共识模型 (低断缆推荐)"),
                ft.dropdown.Option("🏆 自适应三因子稳健融合模型 (优胜推荐)"),
            ],
            expand=True,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.execute_advanced_backtest(),
        )
        self.dd_bt_mode = ft.Dropdown(
            label="倍投策略",
            value="盈利型(恒定每期盈利)",
            options=[
                ft.dropdown.Option("盈利型(恒定每期盈利)"),
                ft.dropdown.Option("盈利型(递增每期盈利)"),
                ft.dropdown.Option("防守型(前攻后守保本)"),
                ft.dropdown.Option("平注均衡型(1:1:1无倍投)"),
            ],
            expand=True,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.execute_advanced_backtest(),
        )

        self.bt_report_summary = ft.Column(spacing=6)
        self.bt_compare_list = ft.Column(spacing=6)

        bt_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    single_line_text("📑 策略全量 Walk-Forward 回测战报", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                    ft.Row(spacing=6, controls=[self.dd_bt_periods, self.dd_bt_algo]),
                    ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                        self.dd_bt_mode,
                        action_btn("🚀 执行回测", lambda e: self.execute_advanced_backtest(), bgcolor="#12945E", height=42, size=12),
                    ]),
                    self.bt_report_summary,
                    ft.Divider(color=BORDER_COLOR),
                    single_line_text("四大倍投风控策略横向对照:", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                    self.bt_compare_list,
                ],
            )
        )

        return smooth_listview([smart_card, algo_board_card, bt_card])

    def on_board_ctrl_changed(self, e):
        self.trigger_background_analytics()
        self.execute_advanced_backtest()

    def build_tab_pnl(self):
        self.dd_pnl_algo = ft.Dropdown(
            label="测算算法",
            value="智能六肖偏离量化算法 (HTML专属)",
            options=[
                ft.dropdown.Option("智能六肖偏离量化算法 (HTML专属)"),
                ft.dropdown.Option("马尔可夫转移概率 (实测前一)"),
                ft.dropdown.Option("⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)"),
                ft.dropdown.Option("🤖 多策略交叉共识模型 (低断缆推荐)"),
                ft.dropdown.Option("🏆 自适应三因子稳健融合模型 (优胜推荐)"),
            ],
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.trigger_background_analytics(),
        )

        self.dd_pnl_plan = ft.Dropdown(
            label="倍投模式",
            value="盈利型(恒定每期盈利)",
            options=[
                ft.dropdown.Option("盈利型(恒定每期盈利)"),
                ft.dropdown.Option("盈利型(递增每期盈利)"),
                ft.dropdown.Option("防守型(前攻后守保本)"),
                ft.dropdown.Option("平注均衡型(1:1:1无倍投)"),
            ],
            expand=True,
            text_size=12,
            bgcolor=BG_DARK,
            border_color=BORDER_COLOR,
            on_change=lambda e: self.trigger_background_analytics(),
        )

        self.sw_pnl_lock = ft.Switch(label="锁定岁首5码", value=True, active_color=ACCENT_GREEN, on_change=lambda e: self.trigger_background_analytics())

        self._pnl_ctrl_card = card_box(
            ft.Column(
                spacing=8,
                controls=[
                    single_line_text("💰 多维度周期量化盈利精算看板", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                    self.dd_pnl_algo,
                    ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[self.dd_pnl_plan, self.sw_pnl_lock]),
                    ft.Row(controls=[action_btn("📊 重新测算周期盈利矩阵", lambda e: self.trigger_background_analytics(), bgcolor="#12945E", expand=True, height=40, size=13)]),
                ],
            )
        )

        self.pnl_list_view = ft.ListView(
            expand=True,
            spacing=10,
            controls=[
                self._pnl_ctrl_card,
                card_box(ft.Text("当前开奖记录不足 5 期，请先点击右上角同步按钮获取数据。", size=12, color=ACCENT_AMBER)),
            ],
        )
        return self.pnl_list_view

    def auto_scan_local_first(self):
        src = self.get_source_code()
        base_dir = get_storage_dir()
        for fname in [f"{src}.html", "playwright_dump.html"]:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        recs = RealHtmlParser.parse_html_source(f.read(), src, "2026")
                    if recs:
                        LottoDatabase.save_records(recs)
                        break
                except Exception:
                    pass

        rows = LottoDatabase.get_records(src)
        if rows:
            self.on_full_data_received(rows)
            self.lbl_status.value = f"● 已加载 {len(rows)} 期 (最新: 第 {rows[0]['期数']} 期)"
        else:
            self.render_live_battle_board()
            self._sync_pnl_list_controls()
            self.lbl_status.value = "● 本地无数据，请点右上角同步"
        self.page.update()

    def _auto_sync_loop(self):
        while True:
            pytime.sleep(30)
            try:
                src = self.get_source_code()
                if LottoScheduleConfig.is_draw_window(src) and not self.is_syncing:
                    self.trigger_sync_crawler(None, silent=True)
            except Exception:
                pass

    def trigger_sync_crawler(self, e, silent=False):
        if self.is_syncing:
            return
        self.is_syncing = True
        self.btn_sync.disabled = True
        if not silent:
            self.lbl_status.value = "● 正在同步官网最新数据..."
            self.lbl_status.color = ACCENT_AMBER
            self.btn_sync.update()

        src = self.get_source_code()

        def worker():
            try:
                rows, msg = sync_official_data(src, "2026", on_status=lambda s: self._update_status_safe(s, ACCENT_AMBER))
                self.is_syncing = False
                self.btn_sync.disabled = False
                if rows:
                    self.on_full_data_received(rows)
                self._update_status_safe(msg, ACCENT_GREEN)
            except Exception as ex:
                self.is_syncing = False
                self.btn_sync.disabled = False
                self._update_status_safe(f"同步异常: {ex}", ACCENT_RED)

        threading.Thread(target=worker, daemon=True).start()

    def _update_status_safe(self, text, color=ACCENT_GREEN):
        self.lbl_status.value = f"● {text}"
        self.lbl_status.color = color
        try:
            self.btn_sync.update()
        except Exception:
            pass

    def confirm_clear_db(self):
        src = self.get_source_code()
        cname = self.dd_source.value

        def do_clear(e):
            deleted = LottoDatabase.clear_records(src)
            self.raw_full_rows = []
            self.filtered_rows = []
            self._pnl_result_cards = []
            self.history_list.controls = []
            self.omission_list.controls = []
            self.top3_rec_list.controls = []
            self.all33_rec_list.controls = []
            self.algo_status_list.controls = []
            self._sync_pnl_list_controls()
            self.close_dialog(dlg)
            self.show_snack(f"已清空 [{cname}] 本地开奖数据共 {deleted} 期！", ACCENT_AMBER)

        dlg = ft.AlertDialog(
            title=ft.Text("二次确认", size=15),
            content=ft.Text(f"确定要彻底清空 [{cname}] 的所有本地开奖数据吗？此操作不可撤销！", size=13),
            actions=[
                outline_btn("取消", lambda e: self.close_dialog(dlg), height=36),
                action_btn("确认清空", do_clear, bgcolor="#DC2626", height=36),
            ],
        )
        self.open_dialog(dlg)

    def on_source_changed(self, e):
        src = self.get_source_code()
        self.lbl_schedule.value = LottoScheduleConfig.get_schedule_desc(src)
        rows = LottoDatabase.get_records(src)
        if rows:
            self.on_full_data_received(rows)
            self.show_snack(f"已切换至 {self.dd_source.value} (共 {len(rows)} 期)", ACCENT_CYAN)
        else:
            self.raw_full_rows = []
            self.filtered_rows = []
            self._pnl_result_cards = []
            self.history_list.controls = []
            self.omission_list.controls = []
            self.render_live_battle_board()
            self._sync_pnl_list_controls()
            self.show_snack(f"{self.dd_source.value} 本地暂无数据，请点击同步", ACCENT_AMBER)

    def on_odds_changed(self, e):
        cur_odds = self.get_current_odds()
        self.tf_odds.value = str(cur_odds)
        LottoDatabase.set_config("global_odds", str(cur_odds))
        self.update_chase_table(refresh_ui=True)
        self.trigger_background_analytics()
        if len(self.raw_full_rows) >= 5:
            self.execute_advanced_backtest()
        self.show_snack(f"全局结算赔率已保存为 1:{cur_odds}", ACCENT_AMBER)

    def on_full_data_received(self, rows):
        if not rows:
            return
        self.raw_full_rows = rows
        self.on_filter_changed(None)
        self.auto_verify_live_bets(notify=False)
        self.render_live_battle_board()
        self.trigger_background_analytics()
        if len(self.raw_full_rows) >= 5:
            self.execute_advanced_backtest()

    def on_filter_changed(self, e):
        if not self.raw_full_rows:
            return
        pos = self.dd_pos.value or "特码"
        self.filtered_rows = list(self.raw_full_rows)
        z_col = "特码生肖" if pos == "特码" else f"{pos}肖"

        hist_items = []
        for row in self.filtered_rows[:50]:
            num_val = int(row.get(pos, 0))
            draw_date = str(row.get("开奖时间", "") or "")
            raw_z = str(row.get(z_col, "") or "").strip()
            z_val = raw_z if raw_z in ZodiacCalendarEngine.ZODIAC_ORDER else num_to_zodiac(num_val, draw_date)
            color_str = LottoAttrClassifier.get_color(num_val)
            wuxing_str = LottoAttrClassifier.get_wuxing(num_val, draw_date)
            hw_str = LottoAttrClassifier.get_half_wave(num_val)
            bsoe_str = LottoAttrClassifier.get_bs_oe(num_val)

            hist_items.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=6, controls=[
                                ft.Text(f"{row.get('期数显示', '')}", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                                ball_chip(num_val, size=26),
                                ft.Text(f"{z_val}·{wuxing_str}", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                            ]),
                            single_line_text(f"{color_str}|{hw_str}|{bsoe_str}", size=10, weight=ft.FontWeight.NORMAL, color=TEXT_SECONDARY),
                        ],
                    ),
                )
            )
        self.history_list.controls = hist_items
        self.render_omission_section()
        try:
            self.history_list.update()
            self.omission_list.update()
        except Exception:
            self.page.update()

    def _get_rec_reference_span(self):
        total_n = len(self.raw_full_rows) if self.raw_full_rows else 90
        txt = self.dd_rec_period.value or "90期"
        m = re.search(r'\d+', txt)
        if m:
            return min(int(m.group(0)), max(1, total_n))
        return max(1, total_n)

    def trigger_background_analytics(self):
        if len(self.raw_full_rows) < 5:
            self._sync_pnl_list_controls()
            try:
                self.page.update()
            except Exception:
                pass
            return

        rows_snap = list(self.raw_full_rows)
        odds = self.get_current_odds()
        rec_span = self._get_rec_reference_span()
        board_lock = bool(self.sw_board_lock.value)
        span_map = {"本周 (7期)": 7, "本月 (30期)": 30, "双月 (60期)": 60, "本季 (90期)": 90, "半年 (180期)": 180, "本年 (365期)": 365}
        board_span = span_map.get(self.dd_board_span.value, 30)
        board_cb = bool(self.sw_board_cb.value)

        algo_list = [
            "智能六肖偏离量化算法 (HTML专属)",
            "马尔可夫转移概率 (实测前一)",
            "⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)",
            "🤖 多策略交叉共识模型 (低断缆推荐)",
            "🏆 自适应三因子稳健融合模型 (优胜推荐)",
        ]
        pnl_algo_idx = (algo_list.index(self.dd_pnl_algo.value) + 1) if self.dd_pnl_algo.value in algo_list else 1
        pnl_plan = self.dd_pnl_plan.value or "盈利型(恒定每期盈利)"
        pnl_lock = bool(self.sw_pnl_lock.value)

        def worker():
            try:
                rec_all33 = AnalyticsEngine.get_all_multi_dim_metrics(rows_snap, rec_span)
                rec_top3 = AnalyticsEngine.get_multi_dim_metrics(rows_snap, rec_span, precomputed_all33=rec_all33)

                algo_statuses = []
                for idx in [1, 2, 3, 4, 5]:
                    st = AnalyticsEngine.get_algo_live_status(
                        rows_snap, idx, lock_head=board_lock, span_limit=board_span, use_circuit_breaker=board_cb, odds=odds
                    )
                    algo_statuses.append((idx, st))

                pnl_rows = []
                total_avail = len(rows_snap)
                for label, span in [("单周周期 (7天)", 7), ("单月周期 (30天)", 30), ("季度周期 (90天)", 90), ("半年度周期 (180天)", 180), ("年度周期 (365天)", 365)]:
                    actual_span = min(span, total_avail)
                    if actual_span < 5:
                        continue
                    res = AnalyticsEngine.simulate_walk_forward_backtest(
                        rows_snap, actual_span, pnl_algo_idx, pnl_plan, pnl_lock, board_cb, odds=odds
                    )
                    pnl_rows.append((label, actual_span, res))

                self._render_analytics_results(rec_top3, rec_all33, algo_statuses, pnl_rows)
            except Exception as ex:
                self._update_status_safe(f"后台运算异常: {ex}", ACCENT_RED)

        threading.Thread(target=worker, daemon=True).start()

    def _render_analytics_results(self, rec_top3, rec_all33, algo_statuses, pnl_rows):
        src = self.get_source_code()
        latest_date = self.raw_full_rows[0].get("开奖时间", "") if self.raw_full_rows else ""
        full_n = len(self.raw_full_rows)

        self.current_rec_metrics = rec_top3
        self.current_all_rec_metrics = rec_all33
        if rec_top3:
            summary_parts = [f"TOP{idx+1} {m['dim']}:{m['val']} ({m['rate'].split(' ')[0]})" for idx, m in enumerate(rec_top3)]
            self.lbl_rec_summary.value = f"🎯 全量 {full_n} 期 Top-3 黄金优选 ➔ " + " | ".join(summary_parts)

        self.top3_rec_list.controls = [self._build_rec_item_card(m, src, latest_date, is_top3=True) for m in rec_top3]
        self.all33_rec_list.controls = [self._build_rec_item_card(m, src, latest_date, is_top3=False) for m in rec_all33]

        head_z = ZodiacCalendarEngine.get_zodiac_by_date(latest_date)
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        short_tags = AnalyticsEngine.ALGO_SHORT_TAGS
        target_names = AnalyticsEngine.ALGO_NAMES

        algo_candidates = []
        for idx, st in algo_statuses:
            picks = st["picks"]
            target_codes = sorted(list(set(num for z in picks for num in z_to_nums.get(z, []))))
            codes_display_str = ", ".join(str(n).zfill(2) for n in target_codes)
            p_single = len(target_codes) / 49.0 if target_codes else 0.0
            p_three = 1.0 - ((1.0 - p_single) ** 3)
            algo_candidates.append({
                "algo_idx": idx,
                "name": target_names.get(idx, f"算法 {idx}"),
                "short_tag": short_tags.get(idx, f"模型{idx}"),
                "picks": picks,
                "picks_str": "-".join(picks) if picks else "-",
                "norm_target": normalize_target_key(", ".join(picks)),
                "target_codes": target_codes,
                "codes_display_str": codes_display_str,
                "total_codes": len(target_codes),
                "step": st["step"],
                "dist_bust": st["dist_bust"],
                "dist_bust_color": st.get("dist_bust_color", ACCENT_CYAN),
                "period_rate": st["period_rate"],
                "p_single": p_single,
                "p_three": p_three,
            })

        z_freq = {}
        for cand in algo_candidates:
            for z in cand["picks"]:
                z_freq[z] = z_freq.get(z, 0) + 1
        high_consensus_z = [z for z, cnt in sorted(z_freq.items(), key=lambda x: x[1], reverse=True) if cnt >= 3]

        best_cand, best_score = None, -1.0
        for cand in algo_candidates:
            rate_match = re.search(r'([\d.]+)%', cand["period_rate"])
            win_rate_val = float(rate_match.group(1)) if rate_match else 50.0
            step_bonus = 10.0 if cand["step"] == 2 else (15.0 if cand["step"] == 3 else 5.0)
            if "警惕" in cand["dist_bust"]:
                step_bonus -= 10.0
            avg_cons = sum(z_freq.get(z, 1) for z in cand["picks"]) / max(1, len(cand["picks"]))
            conf_score = min(98.5, max(50.0, win_rate_val * 0.55 + (avg_cons / 5.0) * 30.0 + step_bonus))
            cand["conf_score"] = conf_score
            if conf_score > best_score:
                best_score = conf_score
                best_cand = cand

        active_orders = LottoDatabase.get_active_live_orders(src, "生肖")
        active_algo_idxs = set()
        known_tags = list(short_tags.values())
        for _, t_name, _, t_vals in active_orders:
            t_name_s = str(t_name or "")
            norm_tv = normalize_target_key(t_vals)
            matched_tag = next((tg for tg in known_tags if f"[{tg}]" in t_name_s), None)
            if matched_tag:
                for cand in algo_candidates:
                    if cand["short_tag"] == matched_tag and cand["norm_target"] == norm_tv:
                        active_algo_idxs.add(cand["algo_idx"])

        algo_items = []
        for cand in algo_candidates:
            idx = cand["algo_idx"]
            is_act = idx in active_algo_idxs
            step_col = ACCENT_GREEN if cand["step"] == 1 else (ACCENT_AMBER if cand["step"] == 2 else ACCENT_RED)
            algo_items.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border=ft.border.all(1, BORDER_COLOR),
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                                ft.Container(content=single_line_text(cand["name"], size=13, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY), expand=True),
                                pill_badge(f"第 {cand['step']}/3 期", step_col),
                            ]),
                            ft.Text(f"推荐: {cand['picks_str']} (共{cand['total_codes']}码)", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                            ft.Text(f"胜率: {cand['period_rate']} | 3期概率: {cand['p_three']*100:.1f}% | {cand['dist_bust']}", size=11, color=cand["dist_bust_color"]),
                            ft.Row(spacing=6, controls=[
                                outline_btn("📊 回测", lambda e, ai=idx, an=cand["name"]: self.open_algo_backtest_dialog(ai, an, is_ai_smart=False), height=34),
                                outline_btn("📋 复制", lambda e, cs=cand["codes_display_str"]: self.copy_text(cs, "已复制算法号码"), height=34),
                                action_btn(
                                    "✔ 已跟投" if is_act else "🎯 一键跟投",
                                    lambda e, tv=cand["picks"], tc=cand["target_codes"], stg=cand["short_tag"]: self.open_quick_bet_dialog("生肖", tv, tc, stg),
                                    bgcolor="#334155" if is_act else "#12945E",
                                    height=34,
                                    expand=True,
                                ),
                            ]),
                        ],
                    ),
                )
            )
        self.algo_status_list.controls = algo_items

        if best_cand:
            cons_str = "、".join(high_consensus_z[:4]) if high_consensus_z else "均衡分散"
            self.lbl_bt_smart_title.value = f"🎯 优选: {best_cand['picks_str']} ({best_cand['total_codes']}码) · {best_cand['short_tag']}"
            self.lbl_bt_smart_params.value = f"周期胜率 {best_cand['period_rate']} | 3期概率 {best_cand['p_three']*100:.1f}% | 高共识: [{cons_str}]"
            self.lbl_bt_smart_conf.value = f"置信度 {best_cand['conf_score']:.1f}%"

            self.btn_smart_history.disabled = False
            self.btn_smart_history.on_click = lambda e, ai=best_cand["algo_idx"]: self.open_algo_backtest_dialog(ai, "AI 智能交叉优选", is_ai_smart=True)

            self.btn_smart_copy.disabled = False
            self.btn_smart_copy.on_click = lambda e, cs=best_cand["codes_display_str"]: self.copy_text(cs, "已复制AI优选号码")

            is_smart_act = best_cand["algo_idx"] in active_algo_idxs
            self.btn_smart_bet.disabled = False
            self.btn_smart_bet.content = single_line_text("✔ 已跟投" if is_smart_act else "🎯 一键跟投", size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF")
            self.btn_smart_bet.bgcolor = "#334155" if is_smart_act else "#12945E"
            self.btn_smart_bet.on_click = lambda e, tv=best_cand["picks"], tc=best_cand["target_codes"], stg=best_cand["short_tag"]: self.open_quick_bet_dialog("生肖", tv, tc, stg)

        if algo_statuses:
            first_st = algo_statuses[0][1]
            self.lbl_bayesian_badge.value = f"盘口: {first_st.get('regime_desc', '平稳')}"
            self.lbl_bayesian_badge.color = ACCENT_RED if first_st.get("regime") == "MOMENTUM_ATTACK" else ACCENT_CYAN

        pnl_cards = []
        if not pnl_rows:
            pnl_cards.append(
                card_box(ft.Text("暂无可测算的周期盈利数据（请确认开奖期数不少于 5 期）。", size=12, color=TEXT_SECONDARY))
            )
        else:
            for label, actual_span, res in pnl_rows:
                pnl_sum = to_int(res["pnl"])
                cost_sum = to_int(res["turnover"])
                pnl_col = ACCENT_GREEN if pnl_sum >= 0 else ACCENT_RED
                wr = (res["win_rounds"] / res["rounds"] * 100.0) if res["rounds"] > 0 else 0.0
                pnl_cards.append(
                    card_box(
                        ft.Column(spacing=4, controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                single_line_text(f"{label} · 实测 {actual_span} 期", size=13, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                                single_line_text(f"{pnl_sum:+,} 元", size=15, weight=ft.FontWeight.BOLD, color=pnl_col),
                            ]),
                            ft.Text(f"执行 {res['rounds']} 轮 | 胜 {res['win_rounds']} 轮 ({wr:.1f}%) | 断缆 {res['loss_rounds']} 轮 | 流水 {cost_sum:,} 元", size=11, color=TEXT_SECONDARY),
                        ])
                    )
                )
        self._pnl_result_cards = pnl_cards
        self._sync_pnl_list_controls()

        try:
            self.page.update()
        except Exception:
            pass

    def exec_prediction(self):
        if not self.filtered_rows:
            self.show_snack("数据库无数据，请先同步开奖数据！", ACCENT_AMBER)
            return

        algo_list = [
            "智能六肖偏离量化算法 (HTML专属)",
            "马尔可夫转移概率 (实测前一)",
            "⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)",
            "🤖 多策略交叉共识模型 (低断缆推荐)",
            "🏆 自适应三因子稳健融合模型 (优胜推荐)",
        ]
        algo_idx = (algo_list.index(self.dd_algo.value) + 1) if self.dd_algo.value in algo_list else 1
        cnt = int((self.dd_z_count.value or "6肖").replace("肖", ""))
        lock = bool(self.sw_lock_head.value)
        pos = self.dd_pos.value or "特码"

        latest_date = str(self.filtered_rows[0].get("开奖时间", "") or "")
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(latest_date)
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)

        picks = AnalyticsEngine.run_prediction(self.filtered_rows, algo_idx, cnt, lock, pos)
        if not picks:
            return
        total_codes = sum(len(z_to_nums[z]) for z in picks)
        win_rate = round(total_codes / 49 * 100, 1)

        self.current_picks = picks
        self.lbl_pred_line1.value = f"🎯 {' · '.join(picks)}"
        self.lbl_pred_line2.value = f"📦 总覆盖: {total_codes} 码  |  📈 单期理论命中率: {win_rate}%"
        self.lbl_pred_line2.color = ACCENT_CYAN
        self.lbl_pred_line1.update()
        self.lbl_pred_line2.update()

    def apply_pred_to_chase_model(self):
        if not self.filtered_rows:
            self.show_snack("数据库无数据，请先同步开奖数据！", ACCENT_AMBER)
            return
        self.exec_prediction()
        if not self.current_picks:
            return
        try:
            stage_cnt = max(1, min(50, int((self.tf_chase_stages.value or "3").strip())))
        except Exception:
            stage_cnt = 3

        latest_date = str(self.filtered_rows[0].get("开奖时间", "") or "")
        head_z = ZodiacCalendarEngine.get_zodiac_by_date(latest_date)
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)

        picks_str = "-".join(self.current_picks)
        total_codes = sum(len(z_to_nums[z]) for z in self.current_picks)
        self.lbl_active_picks.value = f"方案: {picks_str} (共{total_codes}码 · 追{stage_cnt}期)"
        self.active_codes_count = total_codes
        self.active_stages = stage_cnt

        self.update_chase_table(refresh_ui=False)
        self.switch_tab(1)

    def commit_chase_plan_to_live(self):
        if not self.current_picks:
            self.show_snack("请先在【智能选号】生成预测方案！", ACCENT_AMBER)
            return
        if not self.raw_full_rows:
            self.show_snack("当前无开奖数据，无法确定期号！", ACCENT_RED)
            return

        src = self.get_source_code()
        next_p = int(self.raw_full_rows[0]["期数"]) + 1
        latest_date = str(self.raw_full_rows[0].get("开奖时间", "") or "")
        start_year = clean_year_str(self.raw_full_rows[0].get("年份", ""), latest_date)

        head_z = ZodiacCalendarEngine.get_zodiac_by_date(latest_date)
        _, z_to_nums = ZodiacCalendarEngine.build_zodiac_mapping(head_z)
        target_codes = sorted(list(set(num for z in self.current_picks for num in z_to_nums.get(z, []))))

        mode = self.dd_plan_mode.value or "盈利型(恒定每期盈利)"
        stages = max(1, self.active_stages)
        try:
            target_p = max(10, int((self.tf_target_profit.value or "500").strip()))
        except Exception:
            target_p = 500
        cur_odds = self.get_current_odds()
        step_bets = AnalyticsEngine.compute_adaptive_bets(10, len(target_codes), stages, cur_odds, mode, target_profit=target_p)

        algo_list = [
            "智能六肖偏离量化算法 (HTML专属)",
            "马尔可夫转移概率 (实测前一)",
            "⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)",
            "🤖 多策略交叉共识模型 (低断缆推荐)",
            "🏆 自适应三因子稳健融合模型 (优胜推荐)",
        ]
        algo_idx = (algo_list.index(self.dd_algo.value) + 1) if self.dd_algo.value in algo_list else 1
        short_tag = AnalyticsEngine.ALGO_SHORT_TAGS.get(algo_idx, "")
        tag_prefix = f"[{short_tag}] " if short_tag else ""

        LottoDatabase.add_live_bet({
            "lottery_type": src,
            "task_name": f"{tag_prefix}生肖追号: {'-'.join(self.current_picks)}",
            "start_period": next_p,
            "start_year": start_year,
            "target_type": "生肖",
            "target_values": ", ".join(self.current_picks),
            "target_codes": target_codes,
            "stages": stages,
            "base_bet": step_bets[0],
            "plan_mode": mode,
            "step_bets": step_bets,
        })
        self.trigger_background_analytics()
        self.switch_tab(3)
        self.show_snack("计划已加入【实战看板】！请点击确认跟投。", ACCENT_GREEN)

    def auto_verify_live_bets(self, notify=False):
        src = self.get_source_code()
        if not self.raw_full_rows:
            return
        live_rows = LottoDatabase.get_live_bets(src, only_active=True)
        if not live_rows:
            if notify:
                self.show_snack("当前暂无进行中的实盘挂单", ACCENT_CYAN)
            return

        cur_odds = self.get_current_odds()
        chrono_rows = AnalyticsEngine.ensure_chrono(self.raw_full_rows)
        chrono_records = []
        for r in chrono_rows:
            p_num = int(r["期数"])
            rec_year = clean_year_str(r.get("年份", ""), str(r.get("开奖时间", "") or ""))
            sp_code = int(r["特码"])
            d_date = str(r.get("开奖时间", "") or "")
            raw_z = str(r.get("特码生肖", "") or "").strip()
            sp_z = raw_z if raw_z in ZodiacCalendarEngine.ZODIAC_ORDER else num_to_zodiac(sp_code, d_date)
            chrono_records.append({
                "year": rec_year, "period": p_num, "date": d_date, "sp": sp_code, "zodiac": sp_z,
                "oe": "单" if sp_code % 2 != 0 else "双",
                "bs": "大" if sp_code >= 25 else "小",
                "bsoe": LottoAttrClassifier.get_bs_oe(sp_code),
            })

        for task in live_rows:
            task_id = task["id"]
            status = str(task["status"])
            start_p = int(task["start_period"])
            start_year = str(task.get("start_year", "") or "").strip()
            stages = max(1, int(task["stages"]))
            cur_s = max(1, int(task["current_step"]))
            accum_cost = to_int(task["accum_cost"])
            t_type = str(task["target_type"])
            t_vals = [v.strip() for v in re.split(r'[,，\-]+', str(task["target_values"])) if v.strip()]
            codes = json.loads(task["target_codes"]) if task["target_codes"] else []
            step_bets = [to_int(x, 1) for x in json.loads(task["step_bets"])] if task["step_bets"] else [10]
            create_date = str(task.get("create_time", "") or "")[:10]

            if any(k in status for k in ["已中奖", "胜出", "断缆", "和局", "结束"]) or "待确认" in status:
                continue

            start_idx = None
            if start_year:
                for idx in range(len(chrono_records) - 1, -1, -1):
                    if chrono_records[idx]["year"] == start_year and chrono_records[idx]["period"] == start_p:
                        start_idx = idx
                        break
            if start_idx is None:
                for idx in range(len(chrono_records) - 1, -1, -1):
                    rec_d = chrono_records[idx]["date"]
                    if chrono_records[idx]["period"] == start_p and (not rec_d or not create_date or rec_d >= create_date):
                        start_idx = idx
                        break
            if start_idx is None:
                continue

            while cur_s <= stages:
                if "待确认" in status:
                    break
                target_idx = start_idx + (cur_s - 1)
                if target_idx >= len(chrono_records):
                    break

                rec = chrono_records[target_idx]
                eval_p, sp_code = rec["period"], rec["sp"]
                is_hit, is_tie = False, False

                if t_type == "生肖":
                    is_hit = (rec["zodiac"] in t_vals) or (sp_code in codes)
                elif t_type in ["单双", "大小", "盘面组合"]:
                    if sp_code == 49:
                        is_tie = True
                    else:
                        attr_val = rec["oe"] if t_type == "单双" else (rec["bs"] if t_type == "大小" else rec["bsoe"])
                        is_hit = attr_val in t_vals
                else:
                    is_hit = sp_code in codes

                bet = step_bets[min(cur_s - 1, len(step_bets) - 1)]
                step_cost = bet * len(codes)
                if "已确认下注" not in status:
                    accum_cost += step_cost

                if is_tie:
                    LottoDatabase.update_live_bet(task_id, {
                        "current_step": cur_s, "status": f"⏸ 和局退本 (第 {cur_s} 期开49)",
                        "accum_cost": accum_cost, "total_payout": step_cost, "net_pnl": step_cost - accum_cost, "hit_period": eval_p,
                    })
                    break
                elif is_hit:
                    payout = bet * cur_odds
                    LottoDatabase.update_live_bet(task_id, {
                        "current_step": cur_s, "status": f"🎯 已中奖 (第 {cur_s} 期命中)",
                        "accum_cost": accum_cost, "total_payout": payout, "net_pnl": payout - accum_cost, "hit_period": eval_p,
                    })
                    break
                else:
                    if cur_s >= stages:
                        LottoDatabase.update_live_bet(task_id, {
                            "current_step": stages, "status": f"❌ 计划断缆 (满 {stages} 期未中)",
                            "accum_cost": accum_cost, "total_payout": 0, "net_pnl": -accum_cost, "hit_period": eval_p,
                        })
                        break
                    else:
                        cur_s += 1
                        status = f"待确认第 {cur_s} 期下注"
                        LottoDatabase.update_live_bet(task_id, {
                            "current_step": cur_s, "status": status, "accum_cost": accum_cost, "total_payout": 0, "net_pnl": -accum_cost,
                        })
                        break

        self.render_live_battle_board()
        if notify:
            self.show_snack("已完成实盘单据开奖对账验奖！", ACCENT_GREEN)

    def _derive_strategy_eval_key(self, task_row):
        ctype = str(task_row.get("target_type", "生肖") or "生肖")
        t_name = str(task_row.get("task_name", "") or "")
        t_vals = normalize_target_key(task_row.get("target_values", ""))
        known_tags = list(AnalyticsEngine.ALGO_SHORT_TAGS.values())
        matched_tag = next((tg for tg in known_tags if f"[{tg}]" in t_name), None)
        if matched_tag:
            return f"【{ctype} · {matched_tag}】"
        m_bracket = re.search(r'\[([^\[\]]+)\]', t_name)
        if m_bracket:
            return f"【{ctype} · {m_bracket.group(1).strip()}】"
        if ctype == "生肖":
            return "【生肖 · 常规推荐】"
        return f"【{ctype} · {t_vals}】" if t_vals else f"【{ctype}】"

    def render_live_battle_board(self):
        src = self.get_source_code()
        all_history = LottoDatabase.get_live_bets(src, only_active=False)
        eval_items = []
        order_items = []

        if not all_history:
            self.kpi_cost.value = "0 元"
            self.kpi_win.value = "0 元"
            self.kpi_pnl.value = "+0 元"
            self.kpi_pnl.color = ACCENT_GREEN
            self.kpi_roi.value = "0.0%"
            self.kpi_roi.color = ACCENT_CYAN
            self.kpi_wr.value = "0.0% (0/0轮)"
            self.kpi_bust.value = "0 轮"
            self.lbl_next_bet_prompt.value = "当前暂无进行中的追号计划。"
            self.plan_eval_list.controls = []
            self.live_bets_list.controls = []
            self.page.update()
            return

        span_mode = self.dd_live_span.value or "全周期汇总"
        span_days_map = {
            "近单周 (7天)": 7,
            "近单月 (30天)": 30,
            "近季度 (90天)": 90,
            "近半年度 (180天)": 180,
            "近年度 (365天)": 365,
        }
        now_dt = datetime.now()
        report_rows = []
        for task in all_history:
            if span_mode in span_days_map:
                try:
                    c_dt = datetime.strptime(str(task["create_time"])[:19], "%Y-%m-%d %H:%M:%S")
                    if (now_dt - c_dt).days <= span_days_map[span_mode]:
                        report_rows.append(task)
                except Exception:
                    report_rows.append(task)
            else:
                report_rows.append(task)

        total_cost = 0
        total_payout = 0
        win_tasks = 0
        bust_tasks = 0
        tie_tasks = 0
        active_invested_tasks = 0

        for t in report_rows:
            st = str(t.get("status", ""))
            c = to_int(t.get("accum_cost", 0))
            p = to_int(t.get("total_payout", 0))
            total_cost += c
            total_payout += p

            is_win = ("已中奖" in st) or ("胜出" in st)
            is_bust = ("断缆" in st)
            is_tie = ("和局" in st) or ("结束" in st)

            if is_win:
                win_tasks += 1
                active_invested_tasks += 1
            elif is_bust:
                bust_tasks += 1
                active_invested_tasks += 1
            elif is_tie:
                tie_tasks += 1
            else:
                if c > 0:
                    active_invested_tasks += 1

        self.kpi_cost.value = f"{total_cost:,} 元"
        self.kpi_win.value = f"{total_payout:,} 元"

        net_pnl = total_payout - total_cost
        self.kpi_pnl.value = f"{net_pnl:+,} 元"
        self.kpi_pnl.color = ACCENT_GREEN if net_pnl >= 0 else ACCENT_RED

        if total_cost > 0:
            roi_val = (net_pnl / total_cost) * 100.0
            self.kpi_roi.value = f"{roi_val:+.1f}%"
            self.kpi_roi.color = ACCENT_GREEN if roi_val >= 0 else ACCENT_RED
        else:
            self.kpi_roi.value = "0.0%"
            self.kpi_roi.color = ACCENT_CYAN

        if active_invested_tasks > 0:
            win_rate = (win_tasks / active_invested_tasks) * 100.0
            self.kpi_wr.value = f"{win_rate:.1f}% ({win_tasks}/{active_invested_tasks}轮)"
        elif tie_tasks > 0:
            self.kpi_wr.value = "⏸ 仅和局"
        else:
            self.kpi_wr.value = "0.0% (0/0轮)"

        self.kpi_bust.value = f"{bust_tasks} 轮"

        if report_rows:
            category_stats = {}
            for t in report_rows:
                s_key = self._derive_strategy_eval_key(t)
                if s_key not in category_stats:
                    category_stats[s_key] = {
                        "total": 0,
                        "invested_rounds": 0,
                        "win": 0,
                        "loss": 0,
                        "cost": 0,
                        "payout": 0,
                    }
                st = str(t.get("status", ""))
                c = to_int(t.get("accum_cost", 0))
                p = to_int(t.get("total_payout", 0))
                category_stats[s_key]["total"] += 1
                category_stats[s_key]["cost"] += c
                category_stats[s_key]["payout"] += p

                if "已中奖" in st or "胜出" in st:
                    category_stats[s_key]["invested_rounds"] += 1
                    category_stats[s_key]["win"] += 1
                elif "断缆" in st:
                    category_stats[s_key]["invested_rounds"] += 1
                    category_stats[s_key]["loss"] += 1
                elif "和局" not in st and "结束" not in st and c > 0:
                    category_stats[s_key]["invested_rounds"] += 1

            for s_key, cd in category_stats.items():
                c_pnl = cd["payout"] - cd["cost"]
                denom_r = cd["invested_rounds"]
                c_wr = (cd["win"] / denom_r * 100.0) if denom_r > 0 else 0.0
                p_col = ACCENT_GREEN if c_pnl >= 0 else ACCENT_RED
                eval_items.append(
                    ft.Container(
                        bgcolor=CARD_BG_ALT,
                        border_radius=8,
                        padding=8,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        single_line_text(s_key, size=13, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                                        ft.Text(
                                            f"共 {cd['total']} 轮 | 胜率 {c_wr:.1f}% ({cd['win']}/{denom_r}) | 投入 {cd['cost']:,}元 | 返还 {cd['payout']:,}元",
                                            size=11,
                                            color=TEXT_SECONDARY,
                                        ),
                                    ],
                                ),
                                single_line_text(f"{c_pnl:+,} 元", size=14, weight=ft.FontWeight.BOLD, color=p_col),
                            ],
                        ),
                    )
                )

        active_live_rows = LottoDatabase.get_live_bets(src, only_active=True)
        pending_prompts = []
        for task in active_live_rows:
            task_id = int(task["id"])
            status = str(task["status"])
            cost = to_int(task["accum_cost"])
            payout = to_int(task["total_payout"])
            start_p = int(task["start_period"])
            cur_s = max(1, int(task["current_step"]))
            stages = int(task["stages"])
            cur_eval_period = start_p + (cur_s - 1)
            codes_list = json.loads(task["target_codes"]) if task["target_codes"] else []
            step_bets = [to_int(x, 1) for x in json.loads(task["step_bets"])] if task["step_bets"] else [10]
            c_bet = step_bets[min(cur_s, len(step_bets)) - 1]
            st_color = ACCENT_GREEN if ("胜出" in status or "已中奖" in status) else (ACCENT_RED if "断缆" in status else ACCENT_AMBER)

            action_btns = []
            if "已中奖" in status or "胜出" in status:
                action_btns.append(action_btn("✔ 中奖归档", lambda e, tid=task_id: self.archive_live_task(tid), bgcolor="#12945E", height=34, expand=True))
            elif "断缆" in status or "结束" in status:
                action_btns.append(action_btn("❌ 确认关闭", lambda e, tid=task_id: self.archive_live_task(tid), bgcolor="#DC2626", height=34, expand=True))
            elif "和局" in status:
                action_btns.append(action_btn("⏸ 和局归档", lambda e, tid=task_id: self.archive_live_task(tid), bgcolor="#334155", height=34, expand=True))
            elif "待确认" in status:
                action_btns.append(
                    action_btn(
                        f"确认第{cur_s}期({c_bet*len(codes_list)}元)",
                        lambda e, tid=task_id, tr=dict(task): self.confirm_single_step_live(tid, tr),
                        bgcolor="#12945E",
                        height=34,
                        expand=True,
                    )
                )
                pending_prompts.append(f"#{task_id} [{task['task_name']}] 第{cur_s}期(目标第{cur_eval_period}期): {c_bet}元/码")

            action_btns.append(
                outline_btn(
                    "🗑️ 删除",
                    lambda e, tid=task_id, tname=str(task["task_name"]): self.confirm_delete_live_task(tid, tname),
                    color=ACCENT_RED,
                    border_color="#7F1D1D",
                    height=34,
                )
            )

            order_items.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border=ft.border.all(1, BORDER_COLOR),
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(content=single_line_text(f"#{task_id} · {task['task_name']} ({len(codes_list)}码)", size=13, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER), expand=True),
                                    pill_badge(f"第 {cur_s}/{stages} 期", ACCENT_CYAN),
                                ],
                            ),
                            ft.Text(f"目标期号: 第 {cur_eval_period} 期 | 单码 {c_bet}元 | 已投 {cost}元 | 返还 {payout}元", size=11, color=TEXT_SECONDARY),
                            ft.Text(f"状态: {status}", size=12, weight=ft.FontWeight.BOLD, color=st_color),
                            ft.Row(spacing=6, controls=action_btns),
                        ],
                    ),
                )
            )

        self.plan_eval_list.controls = eval_items
        self.live_bets_list.controls = order_items
        self.lbl_next_bet_prompt.value = ("🔔 【待确认指令】:\n" + "\n".join(pending_prompts)) if pending_prompts else "当前暂无待确认的追号计划。"
        self.page.update()

    def confirm_single_step_live(self, task_id, task_data):
        step_bets = [to_int(x, 1) for x in json.loads(task_data["step_bets"])] if task_data["step_bets"] else [10]
        codes = json.loads(task_data["target_codes"]) if task_data["target_codes"] else []
        cur_s = max(1, int(task_data["current_step"]))
        bet = step_bets[min(cur_s - 1, len(step_bets) - 1)]
        cost = bet * len(codes)
        accum_cost = to_int(task_data["accum_cost"]) + cost

        LottoDatabase.update_live_bet(task_id, {"accum_cost": accum_cost, "status": f"第 {cur_s} 期已确认下注 (等待开奖)"})
        self.auto_verify_live_bets(notify=False)
        self.show_snack(f"已确认单号 #{task_id} 第 {cur_s} 期下注 ({cost}元)！", ACCENT_GREEN)

    def archive_live_task(self, task_id):
        LottoDatabase.archive_live_bet(task_id)
        self.render_live_battle_board()
        self.trigger_background_analytics()
        self.show_snack(f"单号 #{task_id} 已归档结算！", ACCENT_GREEN)

    def confirm_delete_live_task(self, task_id, task_name):
        def do_delete(e):
            self.close_dialog(dlg)
            self.delete_live_task(task_id)

        dlg = ft.AlertDialog(
            title=ft.Text("删除确认", size=15),
            content=ft.Text(f"确定要删除实战计划单据 #{task_id} 【{task_name}】 吗？\n删除后不可恢复！", size=13),
            actions=[
                outline_btn("取消", lambda e: self.close_dialog(dlg), height=36),
                action_btn("确认删除", do_delete, bgcolor="#DC2626", height=36),
            ],
        )
        self.open_dialog(dlg)

    def delete_live_task(self, task_id):
        LottoDatabase.delete_live_bet(task_id)
        self.render_live_battle_board()
        self.trigger_background_analytics()
        self.show_snack(f"单号 #{task_id} 已删除", ACCENT_AMBER)

    def execute_advanced_backtest(self):
        if len(self.raw_full_rows) < 5:
            return
        rows_snap = list(self.raw_full_rows)
        period_limit = int(re.search(r'\d+', self.dd_bt_periods.value or "30期").group(0))
        algo_list = [
            "智能六肖偏离量化算法 (HTML专属)",
            "马尔可夫转移概率 (实测前一)",
            "⚡ 贝叶斯-HMM隐状态转移引擎 (高胜率)",
            "🤖 多策略交叉共识模型 (低断缆推荐)",
            "🏆 自适应三因子稳健融合模型 (优胜推荐)",
        ]
        algo_idx = (algo_list.index(self.dd_bt_algo.value) + 1) if self.dd_bt_algo.value in algo_list else 1
        mode_text = self.dd_bt_mode.value or "盈利型(恒定每期盈利)"
        lock_head = bool(self.sw_board_lock.value)
        use_cb = bool(self.sw_board_cb.value)
        cur_odds = self.get_current_odds()

        def worker():
            main_res = AnalyticsEngine.simulate_walk_forward_backtest(rows_snap, period_limit, algo_idx, mode_text, lock_head, use_cb, odds=cur_odds)
            all_modes = ["盈利型(恒定每期盈利)", "盈利型(递增每期盈利)", "防守型(前攻后守保本)", "平注均衡型(1:1:1无倍投)"]
            compare_results = {
                m_name: (main_res if m_name == mode_text else AnalyticsEngine.simulate_walk_forward_backtest(rows_snap, period_limit, algo_idx, m_name, lock_head, use_cb, odds=cur_odds))
                for m_name in all_modes
            }
            self._render_backtest_ui(main_res, compare_results, period_limit, mode_text, cur_odds)

        threading.Thread(target=worker, daemon=True).start()

    def _render_backtest_ui(self, res, compare_results, period_limit, mode_text, cur_odds):
        tot_r, win_r, loss_r = res["rounds"], res["win_rounds"], res["loss_rounds"]
        pnl, turnover = to_int(res["pnl"]), to_int(res["turnover"])
        rate = (win_r / tot_r * 100.0) if tot_r > 0 else 0.0
        bets = [to_int(b) for b in res["bets"]]
        codes_cnt = res["codes_in_round"]
        stakes = [b * codes_cnt for b in bets]
        be_3_pct = res.get("be_3_rate", AnalyticsEngine.calc_breakeven_3_rate(codes_cnt, cur_odds)) * 100.0
        pnl_col = ACCENT_GREEN if pnl >= 0 else ACCENT_RED

        self.bt_report_summary.controls = [
            ft.Container(
                bgcolor=CARD_BG_ALT,
                border_radius=8,
                padding=10,
                content=ft.Column(spacing=4, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        single_line_text(f"近 {period_limit} 期战绩 ({win_r}胜/{loss_r}断)", size=13, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        single_line_text(f"净纯利 {pnl:+,} 元", size=14, weight=ft.FontWeight.BOLD, color=pnl_col),
                    ]),
                    ft.Text(f"实测胜率: {rate:.1f}% (平衡门槛 {be_3_pct:.1f}%) | 流水: {turnover:,} 元", size=11, color=ACCENT_CYAN),
                    ft.Text(f"末轮单码: {bets[0]}/{bets[1]}/{bets[2]}元 | 各期注额: {stakes[0]:,}/{stakes[1]:,}/{stakes[2]:,}元", size=11, color=TEXT_SECONDARY),
                ]),
            )
        ]

        comp_items = []
        for m_name, m_res in compare_results.items():
            m_tot, m_win, m_loss = m_res["rounds"], m_res["win_rounds"], m_res["loss_rounds"]
            m_rate = (m_win / m_tot * 100.0) if m_tot > 0 else 0.0
            m_pnl = to_int(m_res["pnl"])
            m_bets = [to_int(b) for b in m_res["bets"]]
            m_col = ACCENT_GREEN if m_pnl >= 0 else ACCENT_RED
            is_cur = m_name == mode_text
            comp_items.append(
                ft.Container(
                    bgcolor="#1B263B" if is_cur else CARD_BG_ALT,
                    border=ft.border.all(1, ACCENT_BLUE if is_cur else BORDER_COLOR),
                    border_radius=8,
                    padding=8,
                    content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Column(spacing=2, expand=True, controls=[
                            single_line_text(f"{m_name}{' [当前]' if is_cur else ''}", size=12, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                            ft.Text(f"胜率 {m_rate:.1f}%({m_win}/{m_tot}) | 断 {m_loss}轮 | 倍率 {'/'.join(str(x) for x in m_bets)}", size=11, color=TEXT_SECONDARY),
                        ]),
                        single_line_text(f"{m_pnl:+,} 元", size=13, weight=ft.FontWeight.BOLD, color=m_col),
                    ]),
                )
            )
        self.bt_compare_list.controls = comp_items
        self.page.update()

    def open_quick_bet_dialog(self, t_type, t_vals, t_cds, source_tag=""):
        if not t_cds:
            self.show_snack("未能匹配到对应号码！", ACCENT_RED)
            return
        src = self.get_source_code()
        next_p = int(self.raw_full_rows[0]["期数"]) + 1 if self.raw_full_rows else 1
        latest_date = str(self.raw_full_rows[0].get("开奖时间", "") or "") if self.raw_full_rows else ""
        start_year = clean_year_str(self.raw_full_rows[0].get("年份", "") if self.raw_full_rows else "", latest_date)
        cur_odds = self.get_current_odds()

        tf_profit = ft.TextField(label="目标盈利(元)", value="500", expand=True, text_size=12, keyboard_type=ft.KeyboardType.NUMBER, bgcolor=BG_DARK)
        tf_stages = ft.TextField(label="追号期数", value="3", width=88, text_size=12, keyboard_type=ft.KeyboardType.NUMBER, bgcolor=BG_DARK)
        dd_mode = ft.Dropdown(
            label="倍投模式",
            value="盈利型(恒定每期盈利)",
            options=[ft.dropdown.Option(x) for x in ["盈利型(恒定每期盈利)", "盈利型(递增每期盈利)", "防守型(前攻后守保本)", "平注均衡型(1:1:1无倍投)"]],
            text_size=12,
            bgcolor=BG_DARK,
        )
        preview_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=170)

        def calc_bets():
            try:
                tp = max(10, int((tf_profit.value or "500").strip()))
            except Exception:
                tp = 500
            try:
                st = max(1, min(50, int((tf_stages.value or "3").strip())))
            except Exception:
                st = 3
            return AnalyticsEngine.compute_adaptive_bets(10, len(t_cds), st, cur_odds, dd_mode.value, target_profit=tp)

        def refresh_preview(e=None):
            step_bets = calc_bets()
            lines = []
            cum = 0
            for idx, b in enumerate(step_bets, start=1):
                c = b * len(t_cds)
                cum += c
                net = b * cur_odds - cum
                lines.append(ft.Text(f"第{idx}期: 单码{b}元 | 当期{c:,}元 | 累计{cum:,}元 | 净利{net:+,}元", size=12, color=ACCENT_GREEN if net >= 0 else ACCENT_RED))
            preview_col.controls = lines
            self.page.update()

        tf_profit.on_change = refresh_preview
        tf_stages.on_change = refresh_preview
        dd_mode.on_change = refresh_preview
        refresh_preview()

        def confirm_bet(e):
            step_bets = calc_bets()
            task_prefix = f"[{source_tag}] " if source_tag else ""
            LottoDatabase.add_live_bet({
                "lottery_type": src,
                "task_name": f"{task_prefix}{t_type}推荐: {', '.join(t_vals)}",
                "start_period": next_p,
                "start_year": start_year,
                "target_type": t_type,
                "target_values": ", ".join(t_vals),
                "target_codes": t_cds,
                "stages": len(step_bets),
                "base_bet": step_bets[0],
                "plan_mode": dd_mode.value,
                "step_bets": step_bets,
            })
            self.close_dialog(dlg)
            self.trigger_background_analytics()
            self.switch_tab(3)
            self.show_snack("计划已加入【实战看板】！", ACCENT_GREEN)

        dlg = ft.AlertDialog(
            title=ft.Text("🎯 确认投注并生成追号计划", size=15),
            content=ft.Column(tight=True, spacing=8, controls=[
                ft.Text(f"标的: {', '.join(t_vals)} (共{len(t_cds)}码 · 1:{cur_odds})", size=13, color=ACCENT_AMBER, weight=ft.FontWeight.BOLD),
                ft.Row(spacing=8, controls=[tf_profit, tf_stages]),
                dd_mode,
                ft.Divider(color=BORDER_COLOR),
                preview_col,
            ]),
            actions=[
                outline_btn("取消", lambda e: self.close_dialog(dlg), height=36),
                action_btn("✔ 确认加入实战", confirm_bet, bgcolor="#12945E", height=36),
            ],
        )
        self.open_dialog(dlg)

    def open_multidim_detail_dialog(self, item_data, span_limit):
        sub_rows = self.raw_full_rows[:span_limit] if self.raw_full_rows else []
        target_vals = item_data.get("raw_vals", [])
        raw_type = item_data.get("raw_type", "")
        rows_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=340)

        consec_miss, consec_hit = 0, 0
        for row in sub_rows:
            sp = int(row["特码"])
            p_display = str(row.get("期数显示", ""))
            d_date = str(row.get("开奖时间", "") or "")
            if raw_type == "五行":
                cur_attr = LottoAttrClassifier.get_wuxing(sp, d_date)
            elif raw_type == "半波":
                cur_attr = LottoAttrClassifier.get_half_wave(sp)
            elif raw_type == "大小":
                cur_attr = "大" if sp >= 25 else ("小" if sp != 49 else "和局(49)")
            elif raw_type == "单双":
                cur_attr = "单" if sp % 2 != 0 else ("双" if sp != 49 else "和局(49)")
            elif raw_type == "生肖区":
                cur_z = num_to_zodiac(sp, d_date)
                cur_attr = "一区(鼠牛虎)" if cur_z in ["鼠", "牛", "虎"] else ("二区(兔龙蛇)" if cur_z in ["兔", "龙", "蛇"] else ("三区(马羊猴)" if cur_z in ["马", "羊", "猴"] else "四区(鸡狗猪)"))
            elif raw_type == "波色":
                cur_attr = LottoAttrClassifier.get_color(sp)
            elif raw_type == "家禽野兽":
                cur_attr = LottoAttrClassifier.get_poultry_beast(num_to_zodiac(sp, d_date))
            elif raw_type == "头数":
                cur_attr = LottoAttrClassifier.get_head_group(sp)
            elif raw_type == "尾数大小":
                cur_attr = LottoAttrClassifier.get_tail_size(sp)
            elif raw_type == "合数单双":
                cur_attr = LottoAttrClassifier.get_sum_oe(sp)
            else:
                cur_attr = "未知"

            if sp == 49 and raw_type in ["大小", "单双"]:
                st_txt, st_col = "⏸ 和局", TEXT_SECONDARY
            elif cur_attr in target_vals:
                consec_hit += 1; consec_miss = 0
                st_txt, st_col = f"✔ 连中{consec_hit}", ACCENT_GREEN
            else:
                consec_miss += 1; consec_hit = 0
                st_txt, st_col = f"✘ 连挂{consec_miss}", ACCENT_RED

            rows_col.controls.append(ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text(f"{p_display} · 特码 {str(sp).zfill(2)} ({cur_attr})", size=12, color=TEXT_PRIMARY),
                ft.Text(st_txt, size=12, weight=ft.FontWeight.BOLD, color=st_col),
            ]))

        dlg = ft.AlertDialog(
            title=ft.Text(f"🔍 穿透明细: {item_data.get('val', '')} (近{span_limit}期)", size=14),
            content=rows_col,
            actions=[outline_btn("关闭", lambda e: self.close_dialog(dlg), height=36)],
        )
        self.open_dialog(dlg)

    def open_algo_backtest_dialog(self, algo_idx, algo_name, is_ai_smart=False):
        if len(self.raw_full_rows) < 5:
            return
        span_map = {"本周 (7期)": 7, "本月 (30期)": 30, "双月 (60期)": 60, "本季 (90期)": 90, "半年 (180期)": 180, "本年 (365期)": 365}
        cur_span = span_map.get(self.dd_board_span.value, 30)
        cur_lock = bool(self.sw_board_lock.value)
        cur_cb = bool(self.sw_board_cb.value)
        cur_mode = self.dd_bt_mode.value or "盈利型(恒定每期盈利)"
        cur_odds = self.get_current_odds()

        if is_ai_smart:
            res = AnalyticsEngine.simulate_ai_smart_walk_forward_backtest(self.raw_full_rows, cur_span, cur_mode, cur_lock, cur_cb, odds=cur_odds)
        else:
            res = AnalyticsEngine.simulate_walk_forward_backtest(self.raw_full_rows, cur_span, algo_idx, cur_mode, cur_lock, cur_cb, odds=cur_odds)

        details_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=340)
        for d in reversed(res.get("details", [])):
            p_int = to_int(d["pnl"])
            col = ACCENT_GREEN if d["won"] else ACCENT_RED
            details_col.controls.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border_radius=8,
                    padding=8,
                    content=ft.Column(spacing=2, controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Text(f"{d['round_title']} · {d['period_display']} ({d['status_txt']})", size=12, weight=ft.FontWeight.BOLD, color=col),
                            ft.Text(f"{p_int:+d} 元", size=12, weight=ft.FontWeight.BOLD, color=col),
                        ]),
                        ft.Text(f"方案: {d['picks_str']} | 开出: {str(d['hit_code']).zfill(2)}({d['hit_z']})", size=11, color=TEXT_SECONDARY),
                    ]),
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text(f"📊 {algo_name} (近{cur_span}期明细)", size=14),
            content=details_col,
            actions=[outline_btn("关闭", lambda e: self.close_dialog(dlg), height=36)],
        )
        self.open_dialog(dlg)

    def open_live_pending_dialog(self):
        src = self.get_source_code()
        live_rows = LottoDatabase.get_live_bets(src, only_active=True)
        items_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=340)
        copy_lines = [f"=== 📋【实战在投挂单清单 ({self.dd_source.value})】==="]

        for task in live_rows:
            status = str(task.get("status", ""))
            if any(k in status for k in ["已中奖", "胜出", "断缆", "和局", "结束"]):
                continue
            tid = task["id"]
            tname = str(task["task_name"])
            start_p = int(task["start_period"])
            cur_s = max(1, int(task["current_step"]))
            stages = int(task["stages"])
            cur_target_p = start_p + (cur_s - 1)
            codes = json.loads(task["target_codes"])
            step_bets = [to_int(x, 1) for x in json.loads(task["step_bets"])]
            c_bet = step_bets[min(cur_s, len(step_bets)) - 1]
            c_str = ", ".join(str(n).zfill(2) for n in sorted(codes))

            copy_lines.append(f"【#{tid}】{tname} | 第{cur_s}/{stages}期(第{cur_target_p}期) | {c_bet}元/码 | 号码({len(codes)}码): {c_str}")
            items_col.controls.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border_radius=8,
                    padding=8,
                    content=ft.Column(spacing=4, controls=[
                        ft.Text(f"#{tid} {tname} · 第{cur_s}/{stages}期 (第{cur_target_p}期)", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER),
                        ft.Text(f"号码({len(codes)}码): {c_str}", size=11, color=TEXT_PRIMARY),
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Text(f"{c_bet}元/码 · 当期{c_bet*len(codes)}元", size=11, color=ACCENT_GREEN),
                            outline_btn("📋 复制号码", lambda e, cs=c_str: self.copy_text(cs, "已复制挂单号码"), height=30, size=11),
                        ]),
                    ]),
                )
            )

        if len(copy_lines) == 1:
            items_col.controls.append(ft.Text("当前暂无进行中的在投挂单。", color=TEXT_SECONDARY))

        dlg = ft.AlertDialog(
            title=ft.Text("📋 正在跟投挂单全息明细", size=14),
            content=items_col,
            actions=[
                outline_btn("📋 复制全部", lambda e: self.copy_text("\n".join(copy_lines), "已复制全部清单"), height=36),
                outline_btn("关闭", lambda e: self.close_dialog(dlg), height=36),
            ],
        )
        self.open_dialog(dlg)

    def open_live_archive_dialog(self):
        src = self.get_source_code()
        arch_rows = LottoDatabase.get_live_bets(src, only_active=False)
        arch_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=340)

        for r in arch_rows:
            net = to_int(r["net_pnl"])
            col = ACCENT_GREEN if net > 0 else (ACCENT_RED if net < 0 else TEXT_SECONDARY)
            arch_col.controls.append(
                ft.Container(
                    bgcolor=CARD_BG_ALT,
                    border_radius=8,
                    padding=8,
                    content=ft.Column(spacing=2, controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Container(content=single_line_text(f"#{r['id']} · {r['task_name']}", size=12, weight=ft.FontWeight.BOLD, color=ACCENT_AMBER), expand=True),
                            single_line_text(f"{net:+d} 元", size=13, weight=ft.FontWeight.BOLD, color=col),
                        ]),
                        ft.Text(f"{str(r['create_time'])[:16]} | 投入 {to_int(r['accum_cost'])}元 | {r['status']}", size=11, color=TEXT_SECONDARY),
                    ]),
                )
            )

        def clear_all(e):
            LottoDatabase.clear_live_bets(src)
            self.close_dialog(dlg)
            self.render_live_battle_board()
            self.show_snack("已清空所有实盘历史档案！", ACCENT_AMBER)

        dlg = ft.AlertDialog(
            title=ft.Text("📜 实盘历史档案库", size=14),
            content=arch_col,
            actions=[
                outline_btn("🗑️ 清空档案", clear_all, color=ACCENT_RED, border_color="#7F1D1D", height=36),
                outline_btn("关闭", lambda e: self.close_dialog(dlg), height=36),
            ],
        )
        self.open_dialog(dlg)

    def open_raw_data_dialog(self):
        raw_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=380)
        if not self.raw_full_rows:
            raw_col.controls.append(ft.Text("暂无开奖数据", color=TEXT_SECONDARY))
        else:
            for row in self.raw_full_rows[:100]:
                d_date = str(row.get("开奖时间", "") or "")
                balls = []
                for cn in ["一", "二", "三", "四", "五", "六"]:
                    v = int(row.get(f"平{cn}", 0))
                    z = row.get(f"平{cn}肖", "") or num_to_zodiac(v, d_date)
                    balls.append(ball_chip(v, z, size=26))
                sp = int(row["特码"])
                sp_z = row.get("特码生肖", "") or num_to_zodiac(sp, d_date)
                balls.append(ft.Text("+", size=14, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY))
                balls.append(ball_chip(sp, sp_z, size=28))

                raw_col.controls.append(
                    ft.Container(
                        bgcolor=CARD_BG_ALT,
                        border_radius=8,
                        padding=8,
                        content=ft.Column(spacing=4, controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text(f"{row.get('期数显示', '')}", size=13, weight=ft.FontWeight.BOLD, color=ACCENT_CYAN),
                                ft.Text(d_date, size=11, color=TEXT_SECONDARY),
                            ]),
                            ft.Row(spacing=4, wrap=True, controls=balls),
                        ]),
                    )
                )

        dlg = ft.AlertDialog(
            title=ft.Text("📋 官网原始开奖数据池 (近100期)", size=14),
            content=raw_col,
            actions=[outline_btn("关闭", lambda e: self.close_dialog(dlg), height=36)],
        )
        self.open_dialog(dlg)


def main(page: ft.Page):
    try:
        LottoQuantMobileApp(page)
    except Exception as exc:
        err_detail = traceback.format_exc()
        page.bgcolor = "#1A0B0E"
        page.controls.clear()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    padding=16,
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Text("⚠️ 启动异常详情（请截图发给开发者）", size=16, weight=ft.FontWeight.BOLD, color="#F87171"),
                            ft.Text(str(exc), size=13, color="#FBBF24", weight=ft.FontWeight.BOLD),
                            ft.Divider(color="#7F1D1D"),
                            ft.Text(err_detail, size=11, color="#E2E8F0"),
                        ],
                    ),
                ),
            )
        )
        page.update()


if __name__ == "__main__":
    ft.app(target=main)
