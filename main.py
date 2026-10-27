import asyncio
import base64
from datetime import date
import json
from pathlib import Path
import secrets
import string
import threading
from urllib.parse import quote
from uuid import uuid4

import flet as ft


DATA_FILE = Path.home() / ".food_familiarity_game.json"
GREEN = "#315C49"
GREEN_LIGHT = "#E8F0E7"
PAPER = "#F5F4ED"
INK = "#26332B"
MUTED = "#7B827A"
ORANGE = "#EAA65B"
STEPS = [
    "写真を撮る",
    "近くで見てみる",
    "においを感じてみる",
    "触れてみる",
    "味を確かめてみる（任意）",
]
PRACTICE_OPTIONS = [
    "写真を見てみる",
    "食べものを食卓に置いてみる",
    "近くで見てみる",
    "においを感じてみる",
    "触れてみる",
    "舌で触れてみる（任意）",
    "ごく小さく味見する（任意）",
    "自分で決めた量を食べる（任意）",
    "今日は見るだけ・休む",
]
MATCHES = {}
MATCHES_LOCK = threading.Lock()


def load_foods():
    try:
        foods = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(foods, list):
        return []
    valid_foods = [
        food
        for food in foods
        if isinstance(food, dict)
        and isinstance(food.get("id"), str)
        and isinstance(food.get("name"), str)
        and isinstance(food.get("photo"), str)
        and isinstance(food.get("step"), int)
        and not isinstance(food.get("step"), bool)
        and 1 <= food["step"] <= len(STEPS)
    ]
    for food in valid_foods:
        log = food.get("practice_log")
        if not isinstance(log, list):
            food["practice_log"] = []
            continue
        food["practice_log"] = [
            entry
            for entry in log[-100:]
            if isinstance(entry, dict)
            and isinstance(entry.get("date"), str)
            and isinstance(entry.get("practice"), str)
            and entry["practice"] in PRACTICE_OPTIONS
        ]
    return valid_foods


def save_foods(foods):
    DATA_FILE.write_text(
        json.dumps(foods, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(page: ft.Page):
    page.title = "たべものカメラ | ちいさな一歩"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    foods = load_foods()
    selected_photo = None
    active_match = None
    player_id = None
    polling_task = None

    food_name = ft.TextField(
        hint_text="食べものの名前（例：トマト）",
        border_radius=12,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        bgcolor="#FFFFFF",
        text_size=14,
        expand=True,
    )
    photo_preview = ft.Container(
        content=ft.Column(
            [
                ft.Text("📷", size=30),
                ft.Text("写真を撮る・選ぶ", size=13, color=MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        width=180,
        height=140,
        bgcolor="#F4F2E9",
        border_radius=14,
        alignment=ft.Alignment.CENTER,
    )
    message = ft.Text("", size=12, color=GREEN)
    food_list = ft.Column(spacing=12)
    progress_summary = ft.Text(color=MUTED, size=12)
    player_name = ft.TextField(
        hint_text="プレイヤー名",
        max_length=20,
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        expand=True,
    )
    room_code_input = ft.TextField(
        hint_text="部屋コード",
        max_length=6,
        capitalization=ft.TextCapitalization.CHARACTERS,
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        expand=True,
    )
    match_message = ft.Text("", size=12, color=GREEN)
    match_panel = ft.Column(spacing=8)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def notify(text, color=GREEN):
        message.value = text
        message.color = color
        page.update()

    async def choose_photo(event):
        nonlocal selected_photo
        files = await file_picker.pick_files(
            dialog_title="食べものの写真を撮る・選ぶ",
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=False,
            with_data=True,
            compression_quality=70,
        )
        if not files:
            return
        photo = files[0].bytes
        if not photo:
            notify("写真を読み込めませんでした。もう一度選んでください。", "#B24B3F")
            return
        if len(photo) > 5 * 1024 * 1024:
            notify("写真のサイズが大きすぎます。5MB以下の写真を選んでください。", "#B24B3F")
            return
        selected_photo = "data:image/jpeg;base64," + base64.b64encode(photo).decode("ascii")
        photo_preview.content = ft.Image(
            src=selected_photo,
            width=180,
            height=140,
            fit=ft.BoxFit.COVER,
            border_radius=14,
        )
        notify("写真をセットしました。")

    def persist():
        try:
            save_foods(foods)
            return True
        except OSError:
            notify("保存できませんでした。保存先の空き容量をご確認ください。", "#B24B3F")
            return False

    def match_snapshot():
        if active_match is None:
            return None
        with MATCHES_LOCK:
            match = MATCHES.get(active_match)
            if match is None:
                return None
            return {
                "code": active_match,
                "finished": match["finished"],
                "players": [
                    {
                        "id": player["id"],
                        "name": player["name"],
                        "score": player["score"],
                    }
                    for player in match["players"]
                ],
            }

    def update_match_score(points):
        if active_match is None or player_id is None:
            return
        with MATCHES_LOCK:
            match = MATCHES.get(active_match)
            if match is None or match["finished"]:
                return
            for player in match["players"]:
                if player["id"] == player_id:
                    player["score"] += points
                    break

    def start_polling():
        nonlocal polling_task
        if polling_task is None or polling_task.done():
            polling_task = page.run_task(poll_match)

    async def poll_match():
        while active_match is not None:
            await asyncio.sleep(1.5)
            render_match()

    def create_match(event):
        nonlocal active_match, player_id
        name = (player_name.value or "").strip()
        if not name:
            match_message.value = "プレイヤー名を入力してください。"
            page.update()
            return
        alphabet = string.ascii_uppercase + "23456789"
        with MATCHES_LOCK:
            while True:
                code = "".join(secrets.choice(alphabet) for _ in range(6))
                if code not in MATCHES:
                    break
            player_id = str(uuid4())
            MATCHES[code] = {
                "players": [{"id": player_id, "name": name, "score": 0}],
                "finished": False,
            }
            active_match = code
        match_message.value = ""
        render_match()
        start_polling()

    def join_match(event):
        nonlocal active_match, player_id
        name = (player_name.value or "").strip()
        code = (room_code_input.value or "").strip().upper()
        if not name:
            match_message.value = "プレイヤー名を入力してください。"
            page.update()
            return
        if len(code) != 6:
            match_message.value = "6文字の部屋コードを入力してください。"
            page.update()
            return
        with MATCHES_LOCK:
            match = MATCHES.get(code)
            if match is None:
                match_message.value = "部屋が見つかりません。コードを確認してください。"
                page.update()
                return
            if match["finished"]:
                match_message.value = "この対戦は終了しています。"
                page.update()
                return
            if len(match["players"]) >= 2:
                match_message.value = "この部屋は満員です。"
                page.update()
                return
            player_id = str(uuid4())
            match["players"].append(
                {"id": player_id, "name": name, "score": 0}
            )
            active_match = code
        match_message.value = ""
        render_match()
        start_polling()

    def finish_match(event):
        if active_match is None:
            return
        with MATCHES_LOCK:
            match = MATCHES.get(active_match)
            if match is not None:
                match["finished"] = True
        render_match()

    def leave_match(event):
        nonlocal active_match, player_id
        if active_match is not None and player_id is not None:
            with MATCHES_LOCK:
                match = MATCHES.get(active_match)
                if match is not None and not match["finished"]:
                    match["players"] = [
                        player
                        for player in match["players"]
                        if player["id"] != player_id
                    ]
                    if not match["players"]:
                        del MATCHES[active_match]
        active_match = None
        player_id = None
        match_message.value = ""
        render_match()

    def render_match():
        snapshot = match_snapshot()
        if snapshot is None:
            match_panel.controls = [
                ft.Text("オンラインで友だちとポイント対戦", size=17, color=INK, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "部屋を作ってコードを共有。対戦中に進めたステップで競います。",
                    size=12,
                    color=MUTED,
                ),
                player_name,
                ft.Row(
                    [
                        ft.Button(
                            "部屋を作る",
                            icon=ft.Icons.ADD,
                            on_click=create_match,
                            bgcolor=GREEN,
                            color="#FFFFFF",
                        ),
                    ],
                    spacing=8,
                ),
                ft.Row(
                    [
                        room_code_input,
                        ft.Button(
                            "参加する",
                            icon=ft.Icons.GROUP_ADD,
                            on_click=join_match,
                            bgcolor=GREEN_LIGHT,
                            color=GREEN,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                match_message,
                ft.Text(
                    "写真や食べものの記録は共有されません。部屋はアプリ稼働中のみ有効です。",
                    size=10,
                    color=MUTED,
                ),
            ]
        else:
            players = snapshot["players"]
            player_rows = [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(
                                "⭐",
                                size=18,
                            ),
                            ft.Text(
                                f"{player['name']}{'（あなた）' if player['id'] == player_id else ''}",
                                size=13,
                                color=INK,
                                expand=True,
                            ),
                            ft.Text(
                                f"{player['score']} pt",
                                size=14,
                                color=GREEN,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=10,
                    bgcolor=GREEN_LIGHT if player["id"] == player_id else "#F4F2E9",
                    border_radius=10,
                )
                for player in players
            ]
            if len(players) == 1:
                player_rows.append(
                    ft.Text("対戦相手の参加を待っています…", size=12, color=MUTED)
                )

            if snapshot["finished"]:
                if len(players) < 2:
                    result = "対戦相手がいないため、結果を決められませんでした。"
                elif players[0]["score"] == players[1]["score"]:
                    result = "引き分け！いっしょに一歩進めました。"
                else:
                    winner = max(players, key=lambda player: player["score"])
                    result = f"🏆 {winner['name']} の勝ち！"
                status = ft.Text(result, size=14, color=GREEN, weight=ft.FontWeight.BOLD)
                actions = ft.Button(
                    "部屋を退出",
                    on_click=leave_match,
                    bgcolor=GREEN_LIGHT,
                    color=GREEN,
                )
            else:
                status = ft.Text(
                    "ステップを進めると1ポイント！味見は任意です。",
                    size=12,
                    color=MUTED,
                )
                actions = ft.Row(
                    [
                        ft.Button(
                            "対戦を終了して結果を見る",
                            on_click=finish_match,
                            bgcolor=GREEN,
                            color="#FFFFFF",
                        ),
                        ft.TextButton("退出", on_click=leave_match),
                    ],
                    spacing=8,
                )
            match_panel.controls = [
                ft.Row(
                    [
                        ft.Text("🏁 オンライン対戦", size=17, color=INK, weight=ft.FontWeight.BOLD),
                        ft.Text(f"部屋コード：{snapshot['code']}", size=13, color=GREEN, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                *player_rows,
                status,
                actions,
            ]
        page.update()

    def remove_food(food_id):
        foods[:] = [food for food in foods if food["id"] != food_id]
        if persist():
            render_foods()
            notify("記録を削除しました。")

    def save_food_note(food_id, note_field):
        food = next((item for item in foods if item["id"] == food_id), None)
        if food is None:
            return
        previous_note = food.get("note", "")
        food["note"] = (note_field.value or "").strip()
        if persist():
            render_foods()
            notify(f"「{food['name']}」の記録を保存しました。")
        else:
            food["note"] = previous_note

    def log_practice(food_id, practice_dropdown):
        practice = practice_dropdown.value
        if practice not in PRACTICE_OPTIONS:
            notify("今日の一歩を選んでください。", "#B24B3F")
            return
        food = next((item for item in foods if item["id"] == food_id), None)
        if food is None:
            return
        previous_log = food.get("practice_log", [])
        food["practice_log"] = [
            *previous_log,
            {"date": date.today().isoformat(), "practice": practice},
        ][-100:]
        if persist():
            render_foods()
            notify("今日の一歩を記録しました。できたことを大切にしよう。")
        else:
            food["practice_log"] = previous_log

    def advance_food(food_id):
        advanced = False
        for food in foods:
            if food["id"] == food_id and food["step"] < len(STEPS):
                food["step"] += 1
                advanced = True
                break
        if persist():
            if advanced:
                update_match_score(1)
            render_foods()
            notify(
                "⭐ 1ポイント！小さな一歩を記録しました！"
                if active_match is not None
                else "小さな一歩を記録しました！"
            )

    def add_food(event):
        nonlocal selected_photo
        name = food_name.value.strip()
        if not name:
            notify("食べものの名前を入力してください。", "#B24B3F")
            return
        if not selected_photo:
            notify("先に食べものの写真を撮るか選んでください。", "#B24B3F")
            return
        foods.insert(
            0,
            {
                "id": str(uuid4()),
                "name": name,
                "photo": selected_photo,
                "step": 1,
            },
        )
        if not persist():
            foods.pop(0)
            return
        update_match_score(1)
        food_name.value = ""
        selected_photo = None
        photo_preview.content = ft.Column(
            [
                ft.Text("📷", size=30),
                ft.Text("写真を撮る・選ぶ", size=13, color=MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        )
        render_foods()
        notify(
            "⭐ 1ポイント！写真を撮れたことが、最初の一歩です。"
            if active_match is not None
            else "記録できました！写真を撮れたことが、最初の一歩です。"
        )

    def render_foods():
        progress_summary.value = (
            f"⭐ {sum(food['step'] for food in foods)} ポイント ・ {len(foods)} 種類"
            if foods
            else "写真を撮って、最初の一歩を記録しよう"
        )
        cards = []
        for food in foods:
            step = food["step"]
            completed = step >= len(STEPS)
            next_step = STEPS[step] if not completed else None
            note_field = ft.TextField(
                label="きょうの気づき・感想",
                hint_text="見た目やにおいなど、気づいたことを書こう",
                value=food.get("note", ""),
                multiline=True,
                min_lines=2,
                max_lines=4,
                max_length=500,
                border_radius=10,
                border_color="#D8DED3",
                focused_border_color=GREEN,
                text_size=13,
            )
            practice_dropdown = ft.Dropdown(
                label="今日できそうな一歩",
                value=PRACTICE_OPTIONS[0],
                options=[
                    ft.DropdownOption(key=practice, text=practice)
                    for practice in PRACTICE_OPTIONS
                ],
                border_radius=10,
                border_color="#D8DED3",
                focused_border_color=GREEN,
                text_size=13,
            )
            practice_log = food.get("practice_log", [])
            recent_practices = [
                ft.Text(
                    f"{entry['date']}  ・  {entry['practice']}",
                    size=11,
                    color=MUTED,
                )
                for entry in reversed(practice_log[-3:])
            ]
            cards.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        src=food["photo"],
                                        width=86,
                                        height=86,
                                        fit=ft.BoxFit.COVER,
                                        border_radius=12,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                food["name"],
                                                size=16,
                                                color=INK,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"ステップ {step} / {len(STEPS)}",
                                                size=11,
                                                color=MUTED,
                                            ),
                                            ft.ProgressBar(
                                                value=step / len(STEPS),
                                                color=GREEN,
                                                bgcolor="#E5E8DF",
                                                bar_height=6,
                                                border_radius=4,
                                            ),
                                            ft.Text(
                                                "いいペース！ここまでで十分です"
                                                if completed
                                                else f"次の一歩：{next_step}",
                                                size=11,
                                                color=GREEN,
                                            ),
                                            ft.Button(
                                                "今日はここまで" if completed else "できた！",
                                                icon=(
                                                    ft.Icons.CHECK_CIRCLE_OUTLINE
                                                    if completed
                                                    else ft.Icons.ARROW_FORWARD
                                                ),
                                                disabled=completed,
                                                on_click=lambda event, item_id=food["id"]: advance_food(
                                                    item_id
                                                ),
                                                bgcolor=GREEN_LIGHT,
                                                color=GREEN,
                                                style=ft.ButtonStyle(
                                                    shape=ft.RoundedRectangleBorder(radius=10)
                                                ),
                                            ),
                                        ],
                                        spacing=6,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=MUTED,
                                        tooltip=f"「{food['name']}」の記録を削除",
                                        on_click=lambda event, item_id=food["id"]: remove_food(
                                            item_id
                                        ),
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                            ),
                            note_field,
                            ft.Button(
                                "気づきを保存",
                                icon=ft.Icons.SAVE_OUTLINED,
                                on_click=lambda event, item_id=food["id"], field=note_field: save_food_note(
                                    item_id, field
                                ),
                                bgcolor=GREEN_LIGHT,
                                color=GREEN,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10)
                                ),
                            ),
                            ft.Divider(height=1, color="#E4E5DC"),
                            ft.Text(
                                "食べる練習：できそうな一歩を自分で選ぼう",
                                size=14,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "順番どおりでなくて大丈夫。今日は休む・見るだけでもOK。",
                                size=11,
                                color=MUTED,
                            ),
                            practice_dropdown,
                            ft.Button(
                                "今日の一歩を記録",
                                icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                on_click=lambda event, item_id=food["id"], choice=practice_dropdown: log_practice(
                                    item_id, choice
                                ),
                                bgcolor=GREEN_LIGHT,
                                color=GREEN,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10)
                                ),
                            ),
                            ft.Column(recent_practices, spacing=4),
                            ft.Button(
                                "ほかのレシピを探す",
                                icon=ft.Icons.SEARCH,
                                url=(
                                    "https://www.google.com/search?q="
                                    + quote(f"{food['name']} レシピ アレンジ")
                                ),
                                bgcolor="#FFF2DF",
                                color=INK,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10)
                                ),
                            ),
                            ft.Button(
                                "栄養成分を見る（文部科学省）",
                                icon=ft.Icons.INFO_OUTLINE,
                                url="https://fooddb.mext.go.jp/",
                                bgcolor="#EAF0F5",
                                color=INK,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10)
                                ),
                            ),
                            ft.Text(
                                "料理名や材料で食品成分を確認できます。写真だけでは栄養やアレルギーは判定できません。",
                                size=10,
                                color=MUTED,
                            ),
                        ],
                        spacing=12,
                    ),
                    padding=14,
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#E4E5DC"),
                    border_radius=16,
                )
            )
        if not cards:
            cards.append(
                ft.Container(
                    content=ft.Text(
                        "まだ記録はありません。\n気になる食べものを写真に撮ってみよう。",
                        size=13,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    bgcolor="#FFFFFF",
                    border_radius=16,
                )
            )
        food_list.controls = cards
        page.update()

    header = ft.Column(
        [
            ft.Container(
                content=ft.Text("📸  たべものカメラ", size=14, color=GREEN, weight=ft.FontWeight.BOLD),
                padding=ft.Padding.symmetric(horizontal=14, vertical=9),
                bgcolor=GREEN_LIGHT,
                border_radius=20,
            ),
            ft.Text(
                "苦手な食べものに、\nちいさな一歩。",
                size=34,
                color=INK,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                "写真を撮って、少しずつ知ってみよう。\n自分のペースで大丈夫。",
                size=14,
                color=MUTED,
            ),
        ],
        spacing=12,
    )
    match_card = ft.Container(
    content=match_panel,
    padding=18,
    bgcolor="#FFFFFF",
    border=ft.Border.all(1, "#E4E5DC"),
    border_radius=18,
    )
    add_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("新しい食べものを記録", size=17, color=INK, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        photo_preview,
                        ft.Column(
                            [
                                food_name,
                                ft.Button(
                                    "📷  写真を撮る・選ぶ",
                                    on_click=choose_photo,
                                    bgcolor=GREEN_LIGHT,
                                    color=GREEN,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=12)
                                    ),
                                ),
                            ],
                            spacing=10,
                            expand=True,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Button(
                    "この食べものを記録する",
                    icon=ft.Icons.ADD,
                    on_click=add_food,
                    bgcolor=GREEN,
                    color="#FFFFFF",
                    width=220,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                ),
                message,
            ],
            spacing=14,
        ),
        padding=18,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E4E5DC"),
        border_radius=18,
    )
    records = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("きょうの冒険", size=20, color=INK, weight=ft.FontWeight.BOLD),
                    progress_summary,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            food_list,
        ],
        spacing=12,
    )
    safety_note = ft.Container(
        content=ft.Text(
            "味見は任意です。無理をせず、アレルギーや安全に気をつけてね。困ったときは家族や専門家に相談しよう。",
            size=11,
            color=MUTED,
            text_align=ft.TextAlign.CENTER,
        ),
        padding=12,
        bgcolor="#F0EEE5",
        border_radius=12,
    )
    content = ft.Column(
        [header, match_card, add_card, records, safety_note],
        width=680,
        spacing=22,
    )
    app_container = ft.Container(content=content, width=680, padding=ft.Padding.only(top=12, bottom=28))

    def resize_page(event):
        viewport_width = page.width or 720
        page.padding = 12 if viewport_width < 520 else 20
        content_width = min(680, max(280, viewport_width - page.padding * 2))
        app_container.width = content_width
        content.width = content_width
        page.update()

    page.on_resize = resize_page
    page.add(app_container)
    render_foods()
    render_match()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
