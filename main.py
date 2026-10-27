import base64
import json
from pathlib import Path
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


def load_foods():
    try:
        foods = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(foods, list):
        return []
    return [
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

    def remove_food(food_id):
        foods[:] = [food for food in foods if food["id"] != food_id]
        if persist():
            render_foods()
            notify("記録を削除しました。")

    def advance_food(food_id):
        for food in foods:
            if food["id"] == food_id and food["step"] < len(STEPS):
                food["step"] += 1
                break
        if persist():
            render_foods()
            notify("⭐ 1ポイント！小さな一歩を記録しました！")

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
        notify("記録できました！写真を撮れたことが、最初の一歩です。")

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
            cards.append(
                ft.Container(
                    content=ft.Row(
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
            "味見はしなくてもOK。無理せず、アレルギーや安全に気をつけてね。",
            size=11,
            color=MUTED,
            text_align=ft.TextAlign.CENTER,
        ),
        padding=12,
        bgcolor="#F0EEE5",
        border_radius=12,
    )
    content = ft.Column(
        [header, add_card, records, safety_note],
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


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
