import asyncio
import base64
import binascii
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
MEALS_FILE = Path.home() / ".food_familiarity_game_meals.json"
STREAK_FILE = Path.home() / ".food_familiarity_game_streak.json"
MEAL_TYPES = ("朝食", "昼食", "夕食")
CHARACTER_STAGES = (
    (0, "🫘", "たねっこ", "食事の記録で少しずつ育つよ"),
    (3, "🌱", "めばえっこ", "かわいい芽が出てきたよ"),
    (8, "🍃", "はっぱちゃん", "葉っぱが元気に育っているよ"),
    (15, "🌼", "おはなちゃん", "きれいなお花が咲いたよ"),
    (30, "🌻", "にこにこガーデン", "すくすく育って大きくなったよ"),
)
CHARACTER_DESIGNS = {
    "かわいい": (
        ("🫘", "たねっこ", "食事の記録で少しずつ育つよ"),
        ("🌱", "めばえっこ", "かわいい芽が出てきたよ"),
        ("🍃", "はっぱちゃん", "葉っぱが元気に育っているよ"),
        ("🌼", "おはなちゃん", "きれいなお花が咲いたよ"),
        ("🌻", "にこにこガーデン", "すくすく育って大きくなったよ"),
    ),
    "かっこいい": (
        ("⚫", "タネ・ゼロ", "静かに力をためている"),
        ("🌱", "リーフ・ルーキー", "新しい力が芽生えた"),
        ("🌲", "グリーンナイト", "大地を守る葉の騎士"),
        ("🌳", "ブルームガード", "花を守る森の守護者"),
        ("🌲", "フォレストキング", "深い森を守る伝説の王"),
    ),
    "面白い": (
        ("🫘", "まめまめ", "まめ知識をためてるよ"),
        ("🪱", "にょき太", "にょきっと登場！"),
        ("🥦", "もしゃもしゃ", "もしゃもしゃ成長中"),
        ("🍄", "ぽんぽこフラワー", "ぽんっと咲いたよ"),
        ("🌵", "もりもり親分", "森の元気な親分だぞ"),
    ),
    "真面目": (
        ("🌰", "種子", "記録をもとに成長しています"),
        ("🌱", "発芽体", "発芽段階に到達しました"),
        ("🌿", "葉の研究員", "葉が順調に成長しています"),
        ("🌾", "開花体", "開花段階に到達しました"),
        ("🌳", "樹木守護者", "長期的な成長を達成しました"),
    ),
}
CHARACTER_ICON_OPTIONS = ("⚔️", "🛡️", "🐉", "🦊", "🐺", "🐻", "🐼", "🐸", "🐱", "🐶", "🐰", "🍓", "🍙", "🌟", "🦖", "👑")
LEVEL_STEP_POINTS = 5
LEVEL_TITLES = (
    "ちいさな一歩さん",
    "たべもの見つけ隊",
    "にこにこ探検家",
    "食卓の冒険家",
    "発見の名人",
    "たべもの博士",
    "わくわくマスター",
    "食卓の大スター",
)
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


def load_meals():
    try:
        meals = json.loads(MEALS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(meals, list):
        return []
    valid_meals = []
    for meal in meals:
        if (
            not isinstance(meal, dict)
            or not isinstance(meal.get("id"), str)
            or not isinstance(meal.get("name"), str)
            or not meal["name"].strip()
            or not isinstance(meal.get("date"), str)
            or meal.get("meal") not in MEAL_TYPES
        ):
            continue
        try:
            date.fromisoformat(meal["date"])
        except ValueError:
            continue
        valid_meals.append(meal)
    return valid_meals[-1000:]


def save_meals(meals, character_exp=None, character_design=None, character_icon=None):
    saved_meals = list(meals[-1000:])
    if character_exp is not None:
        saved_meals.append({"_character_exp": character_exp})
    if character_design is not None:
        saved_meals.append({"_character_design": character_design})
    if character_icon is not None:
        saved_meals.append({"_character_icon": character_icon})
    MEALS_FILE.write_text(
        json.dumps(saved_meals, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_character_exp(meals):
    try:
        saved_meals = json.loads(MEALS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return len(meals)
    if isinstance(saved_meals, list):
        for entry in saved_meals:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("_character_exp"), int)
                and not isinstance(entry["_character_exp"], bool)
                and entry["_character_exp"] >= 0
            ):
                return max(len(meals), entry["_character_exp"])
    return len(meals)


def load_character_design():
    try:
        saved_meals = json.loads(MEALS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "かわいい"
    if isinstance(saved_meals, list):
        for entry in saved_meals:
            if (
                isinstance(entry, dict)
                and entry.get("_character_design") in CHARACTER_DESIGNS
            ):
                return entry["_character_design"]
    return "かわいい"


def is_character_icon(value):
    if value in CHARACTER_ICON_OPTIONS:
        return True
    if not isinstance(value, str) or len(value) > 7_000_000:
        return False
    try:
        mime_type, encoded = value.split(";base64,", 1)
        if mime_type not in {
            "data:image/jpeg",
            "data:image/png",
            "data:image/webp",
            "data:image/gif",
        }:
            return False
        base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return False
    return True


def load_character_icon(character_design, character_exp):
    try:
        saved_meals = json.loads(MEALS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        saved_meals = []
    if isinstance(saved_meals, list):
        for entry in saved_meals:
            if isinstance(entry, dict) and is_character_icon(entry.get("_character_icon")):
                return entry["_character_icon"]
    stage_index, _ = get_character_stage(character_exp)
    return CHARACTER_DESIGNS[character_design][stage_index][0]


def get_character_stage(experience):
    stage_index = 0
    for index, (threshold, _, _, _) in enumerate(CHARACTER_STAGES):
        if experience < threshold:
            break
        stage_index = index
    return stage_index, CHARACTER_STAGES[stage_index]


def get_level(points):
    return max(1, points // LEVEL_STEP_POINTS + 1)


def get_level_title(level):
    if level <= len(LEVEL_TITLES):
        return LEVEL_TITLES[level - 1]
    return f"{LEVEL_TITLES[-1]} Lv.{level}"


def parse_activity_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed_date if parsed_date.isoformat() == value else None


def load_streak_dates():
    try:
        saved_dates = json.loads(STREAK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(saved_dates, list):
        return set()
    return {
        parsed_date
        for value in saved_dates
        if (parsed_date := parse_activity_date(value)) is not None
    }


def get_streak_counts(activity_dates, today=None):
    today = today or date.today()
    days = sorted(set(activity_dates))
    if not days:
        return 0, 0

    longest = current_run = 1
    for previous_day, current_day in zip(days, days[1:]):
        if (current_day - previous_day).days == 1:
            current_run += 1
        else:
            current_run = 1
        longest = max(longest, current_run)

    active_day = today if today in days else date.fromordinal(today.toordinal() - 1)
    streak_days = set(days)
    current = 0
    while active_day in streak_days:
        current += 1
        active_day = date.fromordinal(active_day.toordinal() - 1)
    return current, longest


def main(page: ft.Page):
    page.title = "たべものカメラ | ちいさな一歩"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    foods = load_foods()
    meals = load_meals()
    character_exp = load_character_exp(meals)
    character_design = load_character_design()
    character_icon = load_character_icon(character_design, character_exp)
    streak_dates = load_streak_dates()
    for meal in meals:
        meal_date = parse_activity_date(meal.get("date"))
        if meal_date is not None:
            streak_dates.add(meal_date)
    for food in foods:
        created_date = parse_activity_date(food.get("created_at"))
        if created_date is not None:
            streak_dates.add(created_date)
        activity_dates = food.get("activity_dates", [])
        if isinstance(activity_dates, list):
            streak_dates.update(
                parsed_date
                for value in activity_dates
                if (parsed_date := parse_activity_date(value)) is not None
            )
        for entry in food.get("practice_log", []):
            practice_date = parse_activity_date(entry.get("date"))
            if practice_date is not None:
                streak_dates.add(practice_date)
    selected_meal_date = date.today()
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
    level_label = ft.Text(color=INK, size=14, weight=ft.FontWeight.BOLD)
    streak_summary = ft.Text(color=INK, size=13, weight=ft.FontWeight.BOLD)
    streak_record = ft.Text(color=MUTED, size=11)
    level_progress = ft.ProgressBar(
        value=0,
        color=GREEN,
        bgcolor="#E5E8DF",
        bar_height=8,
        border_radius=4,
    )
    meal_name_input = ft.TextField(
        hint_text="食べたもの（例：ごはん、みそ汁）",
        max_length=100,
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        expand=True,
    )
    meal_type_input = ft.Dropdown(
        value=MEAL_TYPES[0],
        options=[
            ft.DropdownOption(key=meal_type, text=meal_type)
            for meal_type in MEAL_TYPES
        ],
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        width=110,
    )
    meal_date_label = ft.Text(color=INK, size=14, weight=ft.FontWeight.BOLD)
    meal_summary = ft.Column(spacing=8)
    character_avatar = ft.Container(
        width=68,
        height=68,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FFF8E8",
        border_radius=34,
    )
    character_icon_status = ft.Text(color=MUTED, size=10)
    character_icon_picker = ft.Dropdown(
        value=character_icon if character_icon in CHARACTER_ICON_OPTIONS else None,
        label="絵文字アイコン",
        options=[
            ft.DropdownOption(key=icon, text=icon)
            for icon in CHARACTER_ICON_OPTIONS
        ],
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        text_size=12,
        width=150,
    )
    character_name = ft.Text(color=INK, size=15, weight=ft.FontWeight.BOLD)
    character_description = ft.Text(color=MUTED, size=11)
    character_design_picker = ft.Dropdown(
        value=character_design,
        label="デザイン",
        options=[
            ft.DropdownOption(key=design, text=design)
            for design in CHARACTER_DESIGNS
        ],
        border_radius=10,
        border_color="#D8DED3",
        focused_border_color=GREEN,
        text_size=12,
        width=125,
    )
    character_progress = ft.ProgressBar(
        value=0,
        color=GREEN,
        bgcolor="#E5E8DF",
        bar_height=7,
        border_radius=4,
    )
    character_next = ft.Text(color=MUTED, size=10)
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

    async def choose_character_icon(event):
        nonlocal character_icon
        files = await file_picker.pick_files(
            dialog_title="キャラクターのアイコン画像を選ぶ",
            file_type=ft.FilePickerFileType.IMAGE,
            allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"],
            allow_multiple=False,
            with_data=True,
        )
        if not files:
            return
        image_file = files[0]
        image_bytes = image_file.bytes
        if not image_bytes:
            notify("画像を読み込めませんでした。もう一度選んでください。", "#B24B3F")
            return
        if len(image_bytes) > 5 * 1024 * 1024:
            notify("画像のサイズが大きすぎます。5MB以下の画像を選んでください。", "#B24B3F")
            return
        extension = Path(image_file.name).suffix.lower().lstrip(".")
        mime_type = {
            "jpg": "jpeg",
            "jpeg": "jpeg",
            "png": "png",
            "webp": "webp",
            "gif": "gif",
        }.get(extension)
        if mime_type is None:
            notify("JPG・PNG・WEBP・GIF形式の画像を選んでください。", "#B24B3F")
            return
        previous_icon = character_icon
        character_icon = (
            f"data:image/{mime_type};base64,"
            + base64.b64encode(image_bytes).decode("ascii")
        )
        try:
            save_meals(meals, character_exp, character_design, character_icon)
        except OSError:
            character_icon = previous_icon
            notify("アイコンを保存できませんでした。保存先をご確認ください。", "#B24B3F")
            return
        character_icon_picker.value = None
        render_character()
        notify("キャラクターのアイコンを変更しました。")

    def persist():
        try:
            save_foods(foods)
            return True
        except OSError:
            notify("保存できませんでした。保存先の空き容量をご確認ください。", "#B24B3F")
            return False

    def persist_meals():
        try:
            save_meals(meals, character_exp, character_design, character_icon)
            return True
        except OSError:
            notify("食事を保存できませんでした。保存先をご確認ください。", "#B24B3F")
            return False

    def record_streak_day(activity_date):
        is_new_day = activity_date not in streak_dates
        streak_dates.add(activity_date)
        try:
            STREAK_FILE.write_text(
                json.dumps(
                    [day.isoformat() for day in sorted(streak_dates)],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            if is_new_day:
                streak_dates.remove(activity_date)
            render_streak()
            notify(
                "記録は保存されましたが、連続記録を更新できませんでした。",
                "#B24B3F",
            )
            return False
        render_streak()
        return True

    def render_streak():
        current, longest = get_streak_counts(streak_dates)
        streak_summary.value = f"🔥 {current}日連続記録"
        streak_record.value = f"最高記録 {longest}日"

    def render_character():
        stage_index, _ = get_character_stage(character_exp)
        threshold = CHARACTER_STAGES[stage_index][0]
        _, name, description = CHARACTER_DESIGNS[character_design][stage_index]
        if character_icon.startswith("data:image/"):
            character_avatar.content = ft.Image(
                src=character_icon,
                width=68,
                height=68,
                fit=ft.BoxFit.COVER,
                border_radius=34,
            )
            character_icon_status.value = "自分の画像"
        else:
            character_avatar.content = ft.Text(character_icon, size=38)
            character_icon_status.value = "絵文字アイコン"
        character_name.value = f"{name}　・　記録 {character_exp}回"
        character_description.value = description
        if stage_index + 1 < len(CHARACTER_STAGES):
            next_threshold = CHARACTER_STAGES[stage_index + 1][0]
            character_progress.value = (character_exp - threshold) / (
                next_threshold - threshold
            )
            character_next.value = f"次の成長まで あと {next_threshold - character_exp} 回"
        else:
            character_progress.value = 1
            character_next.value = "これからも一緒に育っていこう！"

    def change_character_design(event):
        nonlocal character_design
        new_design = character_design_picker.value
        if new_design not in CHARACTER_DESIGNS:
            character_design_picker.value = character_design
            notify("キャラクターデザインを選び直してください。", "#B24B3F")
            return
        previous_design = character_design
        character_design = new_design
        try:
            save_meals(meals, character_exp, character_design, character_icon)
        except OSError:
            character_design = previous_design
            character_design_picker.value = previous_design
            render_character()
            notify("デザインを保存できませんでした。保存先をご確認ください。", "#B24B3F")
            return
        render_character()
        notify(f"「{character_design}」デザインに変更しました。")

    character_design_picker.on_change = change_character_design

    def change_character_icon(event):
        nonlocal character_icon
        new_icon = character_icon_picker.value
        if new_icon not in CHARACTER_ICON_OPTIONS:
            character_icon_picker.value = (
                character_icon
                if character_icon in CHARACTER_ICON_OPTIONS
                else None
            )
            return
        previous_icon = character_icon
        character_icon = new_icon
        try:
            save_meals(meals, character_exp, character_design, character_icon)
        except OSError:
            character_icon = previous_icon
            character_icon_picker.value = (
                previous_icon if previous_icon in CHARACTER_ICON_OPTIONS else None
            )
            render_character()
            notify("アイコンを保存できませんでした。保存先をご確認ください。", "#B24B3F")
            return
        render_character()
        notify("キャラクターのアイコンを変更しました。")

    character_icon_picker.on_change = change_character_icon

    def render_meal_summary():
        meal_date_label.value = selected_meal_date.isoformat()
        meal_summary.controls = []
        for meal_type in MEAL_TYPES:
            entries = [
                meal for meal in meals
                if meal["date"] == selected_meal_date.isoformat()
                and meal["meal"] == meal_type
            ]
            entry_rows = [
                ft.Row(
                    [
                        ft.Text(meal["name"], color=INK, size=13, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=MUTED,
                            tooltip=f"「{meal['name']}」を削除",
                            on_click=lambda event, item_id=meal["id"]: remove_meal(item_id),
                        ),
                    ],
                    spacing=4,
                )
                for meal in entries
            ]
            if not entry_rows:
                entry_rows.append(ft.Text("まだ記録はありません", size=12, color=MUTED))
            meal_summary.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(meal_type, size=14, color=GREEN, weight=ft.FontWeight.BOLD),
                            *entry_rows,
                        ],
                        spacing=4,
                    ),
                    padding=12,
                    bgcolor="#F8F8F3",
                    border_radius=12,
                )
            )
        page.update()

    def add_meal(event):
        nonlocal character_exp
        name = (meal_name_input.value or "").strip()
        meal_type = meal_type_input.value
        if not name:
            notify("食べたものを入力してください。", "#B24B3F")
            return
        if meal_type not in MEAL_TYPES:
            notify("朝食・昼食・夕食から選んでください。", "#B24B3F")
            return
        meals.append(
            {
                "id": str(uuid4()),
                "date": selected_meal_date.isoformat(),
                "meal": meal_type,
                "name": name,
            }
        )
        character_exp += 1
        if not persist_meals():
            character_exp -= 1
            meals.pop()
            return
        meal_name_input.value = ""
        previous_stage, _ = get_character_stage(character_exp - 1)
        current_stage, _ = get_character_stage(character_exp)
        render_character()
        streak_saved = record_streak_day(selected_meal_date)
        render_meal_summary()
        if streak_saved:
            if current_stage > previous_stage:
                notify(f"キャラクターが成長！「{CHARACTER_STAGES[current_stage][2]}」になったよ！")
            else:
                notify(f"{meal_type}に「{name}」を記録しました。")

    def remove_meal(meal_id):
        index = next(
            (index for index, meal in enumerate(meals) if meal["id"] == meal_id),
            None,
        )
        if index is None:
            return
        removed = meals.pop(index)
        if persist_meals():
            render_meal_summary()
            notify("食事の記録を削除しました。")
        else:
            meals.insert(index, removed)

    def shift_meal_date(days):
        nonlocal selected_meal_date
        new_date = date.fromordinal(selected_meal_date.toordinal() + days)
        if new_date > date.today():
            return
        selected_meal_date = new_date
        render_meal_summary()

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
            streak_saved = record_streak_day(date.today())
            render_foods()
            if streak_saved:
                notify("今日の一歩を記録しました。できたことを大切にしよう。")
        else:
            food["practice_log"] = previous_log

    def advance_food(food_id):
        advanced = False
        updated_food = None
        previous_level = get_level(sum(food["step"] for food in foods))
        previous_activity_dates = None
        for food in foods:
            if food["id"] == food_id and food["step"] < len(STEPS):
                food["step"] += 1
                updated_food = food
                existing_activity_dates = food.get("activity_dates", [])
                if not isinstance(existing_activity_dates, list):
                    existing_activity_dates = []
                previous_activity_dates = existing_activity_dates.copy()
                activity_dates = existing_activity_dates.copy()
                today = date.today().isoformat()
                if today not in activity_dates:
                    activity_dates.append(today)
                food["activity_dates"] = activity_dates
                advanced = True
                break
        if persist():
            if advanced:
                update_match_score(1)
                streak_saved = record_streak_day(date.today())
            else:
                streak_saved = True
            render_foods()
            if not streak_saved:
                return
            new_level = get_level(sum(food["step"] for food in foods))
            if advanced and new_level > previous_level:
                notify(
                    f"レベルアップ！ Lv.{new_level}「{get_level_title(new_level)}」の称号を獲得！"
                )
                return
            notify(
                "⭐ 1ポイント！小さな一歩を記録しました！"
                if active_match is not None
                else "小さな一歩を記録しました！"
            )
        elif updated_food is not None:
            updated_food["step"] -= 1
            updated_food["activity_dates"] = previous_activity_dates

    def add_food(event):
        nonlocal selected_photo
        name = food_name.value.strip()
        if not name:
            notify("食べものの名前を入力してください。", "#B24B3F")
            return
        if not selected_photo:
            notify("先に食べものの写真を撮るか選んでください。", "#B24B3F")
            return
        previous_level = get_level(sum(food["step"] for food in foods))
        previous_level = get_level(sum(food["step"] for food in foods))
        foods.insert(
            0,
            {
                "id": str(uuid4()),
                "name": name,
                "photo": selected_photo,
                "step": 1,
                "created_at": date.today().isoformat(),
            },
        )
        if not persist():
            foods.pop(0)
            return
        update_match_score(1)
        streak_saved = record_streak_day(date.today())
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
        if not streak_saved:
            return
        new_level = get_level(sum(food["step"] for food in foods))
        if new_level > previous_level:
            notify(
                f"レベルアップ！ Lv.{new_level}「{get_level_title(new_level)}」の称号を獲得！"
            )
            return
        notify(
            "⭐ 1ポイント！写真を撮れたことが、最初の一歩です。"
            if active_match is not None
            else "記録できました！写真を撮れたことが、最初の一歩です。"
        )

    def render_foods():
        points = sum(food["step"] for food in foods)
        level = get_level(points)
        level_label.value = f"Lv.{level}　🏅 {get_level_title(level)}"
        level_progress.value = (points % LEVEL_STEP_POINTS) / LEVEL_STEP_POINTS
        render_streak()
        progress_summary.value = (
            f"{points} pt ・ {len(foods)} 種類"
            if foods
            else "0 pt ・ 0 種類"
        )
        cards = []
        for food in foods:
            step = food["step"]
            completed = step >= len(STEPS)
            next_step = STEPS[step] if not completed else None
            note_field = ft.TextField(
                label="ひとことメモ",
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
                    f"•  {entry['date']}　{entry['practice']}",
                    size=12,
                    color=INK,
                )
                for entry in reversed(practice_log[-3:])
            ]
            if not recent_practices:
                recent_practices.append(
                    ft.Text("まだ記録はありません", size=12, color=MUTED)
                )
            cards.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        src=food["photo"],
                                        width=96,
                                        height=96,
                                        fit=ft.BoxFit.COVER,
                                        border_radius=16,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                food["name"],
                                                size=21,
                                                color=INK,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"ステップ {step} / {len(STEPS)}　・　⭐ {step} pt",
                                                size=12,
                                                color=MUTED,
                                            ),
                                            ft.ProgressBar(
                                                value=step / len(STEPS),
                                                color=GREEN,
                                                bgcolor="#E5E8DF",
                                                bar_height=8,
                                                border_radius=4,
                                            ),
                                            ft.Text(
                                                "いいペース！ここまでで十分です"
                                                if completed
                                                else f"次の一歩：{next_step}",
                                                size=12,
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
                                                height=42,
                                                style=ft.ButtonStyle(
                                                    shape=ft.RoundedRectangleBorder(radius=12)
                                                ),
                                            ),
                                        ],
                                        spacing=8,
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
                                spacing=14,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "今日の気づき",
                                            size=16,
                                            color=INK,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            "見た目やにおいなど、気づいたことを書こう",
                                            size=12,
                                            color=MUTED,
                                        ),
                                        note_field,
                                        ft.Button(
                                            "気づきを保存",
                                            icon=ft.Icons.SAVE_OUTLINED,
                                            on_click=lambda event, item_id=food["id"], field=note_field: save_food_note(
                                                item_id, field
                                            ),
                                            bgcolor="#FFFFFF",
                                            color=GREEN,
                                            height=42,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=12)
                                            ),
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                padding=16,
                                bgcolor="#F8F8F3",
                                border_radius=16,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text("🌱", size=20),
                                                ft.Text(
                                                    "今日のちいさな一歩",
                                                    size=16,
                                                    color=INK,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text(
                                            "できそうなことを選ぼう。見るだけ・休むのもOK。",
                                            size=12,
                                            color=MUTED,
                                        ),
                                        practice_dropdown,
                                        ft.Button(
                                            "この一歩を記録する",
                                            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                            on_click=lambda event, item_id=food["id"], choice=practice_dropdown: log_practice(
                                                item_id, choice
                                            ),
                                            bgcolor=GREEN,
                                            color="#FFFFFF",
                                            height=46,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=12)
                                            ),
                                        ),
                                        ft.Divider(height=1, color="#D8E3D8"),
                                        ft.Text(
                                            "これまでの記録",
                                            size=13,
                                            color=INK,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Column(recent_practices, spacing=6),
                                    ],
                                    spacing=10,
                                ),
                                padding=16,
                                bgcolor="#EDF4EB",
                                border=ft.Border.all(1, "#DDE8DA"),
                                border_radius=16,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "もっと知る",
                                            size=15,
                                            color=INK,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Button(
                                            "ほかのレシピを探す",
                                            icon=ft.Icons.SEARCH,
                                            url=(
                                                "https://www.google.com/search?q="
                                                + quote(f"{food['name']} レシピ アレンジ")
                                            ),
                                            bgcolor="#FFF2DF",
                                            color=INK,
                                            height=42,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=12)
                                            ),
                                        ),
                                        ft.Button(
                                            "栄養成分を見る（文部科学省）",
                                            icon=ft.Icons.INFO_OUTLINE,
                                            url="https://fooddb.mext.go.jp/",
                                            bgcolor="#EAF0F5",
                                            color=INK,
                                            height=42,
                                            style=ft.ButtonStyle(
                                                shape=ft.RoundedRectangleBorder(radius=12)
                                            ),
                                        ),
                                        ft.Text(
                                            "写真だけでは栄養やアレルギーは判定できません。",
                                            size=11,
                                            color=MUTED,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                padding=16,
                                bgcolor="#F4F6F8",
                                border_radius=16,
                            ),
                        ],
                        spacing=16,
                    ),
                    padding=18,
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#E4E5DC"),
                    border_radius=20,
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
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text("🍀 たべものカメラ", size=13, color=GREEN, weight=ft.FontWeight.BOLD),
                        padding=ft.Padding.symmetric(horizontal=13, vertical=8),
                        bgcolor=GREEN_LIGHT,
                        border_radius=20,
                    ),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("⭐", size=13),
                                progress_summary,
                            ],
                            spacing=4,
                        ),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        bgcolor="#FFFFFF",
                        border_radius=18,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            "きょうも、",
                                            size=16,
                                            color=GREEN,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            "ちいさな一歩♪",
                                            size=27,
                                            color=INK,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            "食事も練習も、\n自分のペースで大丈夫。",
                                            size=13,
                                            color=MUTED,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text("🍓", size=46),
                                    width=82,
                                    height=82,
                                    alignment=ft.Alignment.CENTER,
                                    bgcolor="#FFFFFF",
                                    border_radius=41,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    level_label,
                                    level_progress,
                                    ft.Text(
                                        f"{LEVEL_STEP_POINTS}ポイントごとにレベルアップ！",
                                        size=11,
                                        color=MUTED,
                                    ),
                                ],
                                spacing=5,
                            ),
                            padding=12,
                            bgcolor="#FFFFFF",
                            border_radius=14,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Text("🔥", size=22),
                                    ft.Column(
                                        [streak_summary, streak_record],
                                        spacing=2,
                                        expand=True,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=12,
                            bgcolor="#FFFFFF",
                            border_radius=14,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Container(
                                        content=character_avatar,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Text("いっしょに育てよう", size=11, color=GREEN),
                                                    character_name,
                                                ],
                                                spacing=8,
                                                wrap=True,
                                            ),
                                            character_description,
                                            ft.Row(
                                                [
                                                    character_design_picker,
                                                    character_icon_picker,
                                                    ft.Button(
                                                        "画像を選ぶ",
                                                        icon=ft.Icons.IMAGE_OUTLINED,
                                                        on_click=choose_character_icon,
                                                        bgcolor=GREEN_LIGHT,
                                                        color=GREEN,
                                                    ),
                                                ],
                                                spacing=6,
                                                wrap=True,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                            character_icon_status,
                                            character_progress,
                                            character_next,
                                        ],
                                        spacing=4,
                                        expand=True,
                                    ),
                                ],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=12,
                            bgcolor="#FFFFFF",
                            border_radius=16,
                        ),
                        ft.Row(
                            [
                                ft.Text("🍙", size=24),
                                ft.Text("🥕", size=24),
                                ft.Text("🍅", size=24),
                                ft.Text("🌼", size=21),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                        ),
                        ft.Button(
                            "今日のごはんを記録",
                            icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                            on_click=lambda event: select_section("meals"),
                            bgcolor=GREEN,
                            color="#FFFFFF",
                            width=220,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=14)
                            ),
                        ),
                    ],
                    spacing=14,
                ),
                padding=18,
                bgcolor="#FFF1D8",
                border=ft.Border.all(1, "#F3E4C8"),
                border_radius=24,
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
    meal_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("一日の食事まとめ", size=17, color=INK, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.CHEVRON_LEFT,
                            tooltip="前の日",
                            on_click=lambda event: shift_meal_date(-1),
                        ),
                        meal_date_label,
                        ft.IconButton(
                            icon=ft.Icons.CHEVRON_RIGHT,
                            tooltip="次の日",
                            on_click=lambda event: shift_meal_date(1),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                meal_summary,
                ft.Row(
                    [meal_type_input, meal_name_input],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Button(
                    "食事を追加",
                    icon=ft.Icons.ADD,
                    on_click=add_meal,
                    bgcolor=GREEN,
                    color="#FFFFFF",
                ),
                ft.Text(
                    "入力した内容だけを記録します。栄養成分や量の推定は行いません。",
                    size=11,
                    color=MUTED,
                ),
            ],
            spacing=10,
        ),
        padding=18,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E4E5DC"),
        border_radius=18,
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
    practice_section = ft.Column(
        [add_card, records, safety_note],
        spacing=16,
    )
    sections = {
        "meals": meal_card,
        "practice": practice_section,
        "match": match_card,
    }
    section_view = ft.Container(content=meal_card)
    section_buttons = {}

    def select_section(section):
        section_view.content = sections[section]
        for key, button in section_buttons.items():
            selected = key == section
            button.bgcolor = GREEN if selected else GREEN_LIGHT
            button.color = "#FFFFFF" if selected else GREEN
        page.update()

    section_buttons.update(
        {
            key: ft.Button(
                label,
                icon=icon,
                expand=True,
                height=46,
                tooltip=label,
                on_click=lambda event, selected=key: select_section(selected),
                bgcolor=GREEN if key == "meals" else GREEN_LIGHT,
                color="#FFFFFF" if key == "meals" else GREEN,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12)
                ),
            )
            for key, label, icon in [
                ("meals", "食事", ft.Icons.RESTAURANT),
                ("practice", "練習", ft.Icons.PHOTO_CAMERA_OUTLINED),
                ("match", "対戦", ft.Icons.GROUPS_OUTLINED),
            ]
        }
    )
    section_navigation = ft.Row(
        list(section_buttons.values()),
        spacing=8,
    )
    content = ft.Column(
        [header, section_navigation, section_view],
        width=680,
        spacing=16,
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
    render_character()
    render_meal_summary()
    render_match()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
