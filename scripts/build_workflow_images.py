from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "docs" / "images"
WIDTH = 1600
INK = "#20211e"
MUTED = "#666860"
PAPER = "#f7f7f4"
LINE = "#e5e6e0"
WHITE = "#ffffff"
GREEN = "#36724f"
GREEN_PALE = "#edf4ee"
RED = "#a94135"
RED_PALE = "#fff1ee"
GOLD = "#a77a22"
GOLD_PALE = "#fbf4e6"
BLUE = "#476986"
BLUE_PALE = "#edf3f8"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = ["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str,
                face: ImageFont.ImageFont, color: str, gap: int = 8) -> None:
    left, top, right, bottom = box
    lines = text.split("\n")
    heights = [draw.textbbox((0, 0), line, font=face)[3] for line in lines]
    total = sum(heights) + gap * (len(lines) - 1)
    y = top + (bottom - top - total) / 2
    for line, height in zip(lines, heights):
        bounds = draw.textbbox((0, 0), line, font=face)
        x = left + (right - left - (bounds[2] - bounds[0])) / 2
        draw.text((x, y), line, font=face, fill=color)
        y += height + gap


def card(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str,
         detail: str, fill: str = WHITE, accent: str = INK,
         title_size: int = 27, detail_size: int = 21, radius: int = 22) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=LINE, width=2)
    left, top, right, bottom = xy
    draw.rounded_rectangle((left, top, left + 10, bottom), radius=5, fill=accent)
    title_font = font(title_size, True)
    detail_font = font(detail_size)
    draw.text((left + 28, top + 25), title, font=title_font, fill=INK)
    lines = detail.split("\n")
    y = top + 73
    for line in lines:
        draw.text((left + 28, y), line, font=detail_font, fill=MUTED)
        y += detail_size + 12


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int],
          color: str = MUTED, width: int = 5) -> None:
    draw.line((start, end), fill=color, width=width)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 17
    a1 = angle + math.pi * 0.82
    a2 = angle - math.pi * 0.82
    p1 = (end[0] + length * math.cos(a1), end[1] + length * math.sin(a1))
    p2 = (end[0] + length * math.cos(a2), end[1] + length * math.sin(a2))
    draw.polygon((end, p1, p2), fill=color)


def build_feedback_workflow() -> Path:
    image = Image.new("RGB", (WIDTH, 1080), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), "CHAI HOUSE  /  FEEDBACK FLOW", font=font(23, True), fill=GREEN)
    draw.text((70, 92), "From customer submission to owner follow-up", font=font(43, True), fill=INK)
    draw.text((70, 154), "Local prototype path. The tunnel is temporary; a hosted backend replaces it later.",
              font=font(23), fill=MUTED)

    boxes = [
        (55, 270, 315, 455, "Customer", "Scans QR\nand submits feedback", BLUE_PALE, BLUE),
        (365, 270, 625, 455, "Google Form", "Ratings, comment\nand optional photo", WHITE, INK),
        (675, 270, 935, 455, "Apps Script", "On-submit trigger\nforwards the response", WHITE, INK),
        (985, 270, 1245, 455, "HTTPS tunnel", "Temporary public route\nto your computer", GOLD_PALE, GOLD),
        (1295, 270, 1545, 455, "FastAPI + LangGraph", "Intake API :8001\ntriage and route reports", GREEN_PALE, GREEN),
    ]
    for x1, y1, x2, y2, title, detail, fill, accent in boxes:
        card(draw, (x1, y1, x2, y2), title, detail, fill, accent,
             title_size=21 if title == "FastAPI + LangGraph" else 24, detail_size=19)
    for i in range(4):
        arrow(draw, (boxes[i][2] + 8, 362), (boxes[i + 1][0] - 10, 362))

    draw.text((70, 500), "LANGGRAPH ROUTES EACH SUBMISSION", font=font(21, True), fill=MUTED)
    routes = [
        (110, 590, 540, 780, "Possible urgent report", "Optional photo review;\nowner SMS if Twilio is ready", RED_PALE, RED),
        (585, 590, 1015, 780, "Needs attention", "Food, waiting-time, staff\nor ambience follow-up", GOLD_PALE, GOLD),
        (1060, 590, 1490, 780, "Routine feedback", "Stored for the overall\nfeedback picture", BLUE_PALE, BLUE),
    ]
    for x1, y1, x2, y2, title, detail, fill, accent in routes:
        card(draw, (x1, y1, x2, y2), title, detail, fill, accent, title_size=26, detail_size=20)
    # Route connectors from the LangGraph service to the three bounded outcomes.
    draw.line((1420, 455, 1420, 540), fill=MUTED, width=5)
    draw.line((325, 540, 1275, 540), fill=MUTED, width=5)
    for cx in (325, 800, 1275):
        arrow(draw, (cx, 540), (cx, 580))

    card(draw, (405, 880, 785, 1030), "SQLite database", "Stores reports and routing results", WHITE, GREEN,
         title_size=26, detail_size=19)
    card(draw, (930, 880, 1360, 1030), "Owner dashboard", "Port :8000 reads reports and shows queues", WHITE, INK,
         title_size=26, detail_size=19)
    for cx in (325, 800, 1275):
        draw.line((cx, 780, cx, 830), fill=LINE, width=4)
    draw.line((325, 830, 1275, 830), fill=LINE, width=4)
    arrow(draw, (800, 830), (800, 870), color=GREEN)
    arrow(draw, (785, 955), (920, 955), color=GREEN)

    path = IMAGE_DIR / "feedback-workflow.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return path


def build_dashboard_overview() -> Path:
    image = Image.new("RGB", (WIDTH, 1080), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), "CHAI HOUSE  /  OWNER VIEW", font=font(23, True), fill=GREEN)
    draw.text((70, 92), "What the dashboard shows and tells the owner", font=font(41, True), fill=INK)
    draw.text((70, 154), "Counts and themes come from submitted feedback; urgent reports stay visible for human review.",
              font=font(22), fill=MUTED)

    # Compact sidebar makes this read like a dashboard screenshot, not a technical flowchart.
    draw.rounded_rectangle((55, 225, 330, 1010), radius=24, fill=WHITE, outline=LINE, width=2)
    draw.rounded_rectangle((82, 255, 140, 313), radius=15, fill=INK)
    center_text(draw, (82, 255, 140, 313), "CH", font(23, True), WHITE)
    draw.text((158, 260), "chai house", font=font(24, True), fill=INK)
    draw.text((158, 291), "GUEST EXPERIENCE", font=font(13, True), fill=MUTED)
    draw.text((84, 360), "BOMMANAHALLI", font=font(16, True), fill=GREEN)
    draw.line((82, 395, 300, 395), fill=LINE, width=2)
    draw.text((84, 430), "WORKSPACE", font=font(14, True), fill=MUTED)
    nav_items = ["Overview", "Urgent reports", "Needs attention", "Feedback analysis"]
    y = 480
    for i, label in enumerate(nav_items):
        fill = PAPER if i == 0 else WHITE
        draw.rounded_rectangle((75, y - 8, 310, y + 45), radius=13, fill=fill)
        draw.ellipse((92, y + 10, 104, y + 22), fill=RED if i == 1 else GREEN if i == 0 else MUTED)
        draw.text((120, y), label, font=font(18, i == 0), fill=INK)
        y += 72
    draw.rounded_rectangle((78, 810, 306, 965), radius=18, fill=PAPER, outline=LINE, width=1)
    draw.text((98, 835), "FEEDBACK AGENT", font=font(14, True), fill=MUTED)
    draw.text((98, 870), "Listening in the background", font=font(17, True), fill=INK)
    draw.text((98, 910), "Triage  ·  photo review  ·  analysis", font=font(14), fill=MUTED)

    x0 = 365
    draw.text((x0, 232), "Your guests, in focus.", font=font(39, True), fill=INK)
    draw.text((x0, 284), "A quick view of what is working and what needs attention.", font=font(20), fill=MUTED)

    metrics = [
        (x0, "Guest responses", "Total saved feedback"),
        (x0 + 300, "Food experience", "Average food rating"),
        (x0 + 600, "Waiting experience", "Average wait rating"),
        (x0 + 900, "Needs attention", "Improvement reports"),
    ]
    for x, title, sub in metrics:
        draw.rounded_rectangle((x, 335, x + 270, 465), radius=19, fill=WHITE, outline=LINE, width=2)
        draw.text((x + 20, 356), title, font=font(17, True), fill=MUTED)
        draw.text((x + 20, 391), "From feedback", font=font(20, True), fill=INK)
        draw.text((x + 20, 429), sub, font=font(14), fill=MUTED)

    draw.rounded_rectangle((x0, 490, 1455, 570), radius=18, fill=RED_PALE, outline="#f1d0ca", width=2)
    draw.ellipse((x0 + 22, 513, x0 + 56, 547), fill="#f4d5cf")
    center_text(draw, (x0 + 22, 513, x0 + 56, 547), "!", font(20, True), RED)
    draw.text((x0 + 75, 505), "Possible safety report", font=font(20, True), fill=RED)
    draw.text((x0 + 75, 535), "Customer-reported; owner should review promptly.", font=font(16), fill=MUTED)

    # Inbox panel
    draw.rounded_rectangle((x0, 595, 1005, 1005), radius=20, fill=WHITE, outline=LINE, width=2)
    draw.text((x0 + 28, 620), "FEEDBACK INBOX", font=font(14, True), fill=MUTED)
    draw.text((x0 + 28, 650), "Reports to review", font=font(25, True), fill=INK)
    draw.text((x0 + 28, 700), "URGENT", font=font(14, True), fill=RED)
    draw.text((x0 + 155, 700), "Possible food-safety concern", font=font(18, True), fill=INK)
    draw.text((x0 + 155, 730), "Report text, photo-review status, and alert status", font=font(15), fill=MUTED)
    draw.line((x0 + 25, 768, 975, 768), fill=LINE, width=2)
    draw.text((x0 + 28, 790), "IMPROVEMENT", font=font(14, True), fill=GOLD)
    draw.text((x0 + 155, 790), "Waiting time / food / staff / ambience", font=font(18, True), fill=INK)
    draw.text((x0 + 155, 820), "Customer comment, ratings, and suggested follow-up", font=font(15), fill=MUTED)
    draw.line((x0 + 25, 858, 975, 858), fill=LINE, width=2)
    draw.text((x0 + 28, 880), "ROUTINE", font=font(14, True), fill=BLUE)
    draw.text((x0 + 155, 880), "Other feedback", font=font(18, True), fill=INK)
    draw.text((x0 + 155, 910), "Kept in the dashboard and included in analysis", font=font(15), fill=MUTED)
    draw.text((x0 + 28, 966), "All reports are customer statements, not verified findings.", font=font(14), fill=MUTED)

    # Analysis panel
    panel_x = 1025
    draw.rounded_rectangle((panel_x, 595, 1455, 825), radius=20, fill=WHITE, outline=LINE, width=2)
    draw.text((panel_x + 25, 620), "FEEDBACK ANALYSIS", font=font(14, True), fill=MUTED)
    draw.text((panel_x + 25, 650), "Repeated themes", font=font(24, True), fill=INK)
    for idx, theme in enumerate(("Waiting time", "Food quality", "Staff service")):
        yy = 704 + idx * 37
        draw.ellipse((panel_x + 28, yy + 5, panel_x + 40, yy + 17), fill=GREEN)
        draw.text((panel_x + 54, yy), theme, font=font(17), fill=INK)
    draw.rounded_rectangle((panel_x + 20, 835, 1430, 985), radius=18, fill=GREEN_PALE)
    draw.text((panel_x + 42, 857), "SUGGESTED NEXT STEP", font=font(14, True), fill=GREEN)
    draw.text((panel_x + 42, 888), "Review the most repeated concern", font=font(18, True), fill=INK)
    draw.text((panel_x + 42, 921), "with the team and choose one practical change.", font=font(15), fill=MUTED)

    path = IMAGE_DIR / "dashboard-overview.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return path


def build_images() -> tuple[Path, Path]:
    return build_feedback_workflow(), build_dashboard_overview()


if __name__ == "__main__":
    for output in build_images():
        print(output)
