from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image as PdfImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from build_workflow_images import build_images

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "chai-house-feedback-architecture.pdf"
INK = colors.HexColor("#20211e")
MUTED = colors.HexColor("#666860")
PAPER = colors.HexColor("#f7f7f4")
LINE = colors.HexColor("#e5e6e0")
RED = colors.HexColor("#a94135")
GREEN = colors.HexColor("#36724f")


def build_pdf() -> None:
    workflow_image, dashboard_image = build_images()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter, rightMargin=0.68 * inch, leftMargin=0.68 * inch,
        topMargin=0.7 * inch, bottomMargin=0.65 * inch, title="Chai House Feedback Studio - Architecture & Guardrails",
        author="Chai House Feedback Studio",
    )
    base = getSampleStyleSheet()
    styles = {
        "kicker": ParagraphStyle("Kicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=MUTED, spaceAfter=8, tracking=1.3),
        "title": ParagraphStyle("Title2", parent=base["Title"], fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK, alignment=TA_CENTER, spaceAfter=9),
        "subtitle": ParagraphStyle("Subtitle2", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=15),
        "h1": ParagraphStyle("H1x", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, spaceBefore=6, spaceAfter=11),
        "h2": ParagraphStyle("H2x", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=5),
        "body": ParagraphStyle("Bodyx", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=14, textColor=INK, spaceAfter=6),
        "small": ParagraphStyle("Smallx", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, spaceAfter=4),
        "code": ParagraphStyle("Codex", parent=base["Code"], fontName="Courier", fontSize=7, leading=10, textColor=INK, backColor=PAPER, borderPadding=7, spaceBefore=5, spaceAfter=7),
        "center": ParagraphStyle("Centerx", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=12, textColor=INK, alignment=TA_CENTER),
    }
    story = []
    story += [Spacer(1, 0.32 * inch), Paragraph("CHAI HOUSE · BOMMANAHALLI · BENGALURU", styles["kicker"]),
              Paragraph("Feedback Studio", styles["title"]),
              Paragraph("Prototype architecture, LangGraph building blocks, Jev decision routing, agent roles, and operating guardrails.", styles["subtitle"]),
              HRFlowable(width="100%", thickness=1, color=LINE, spaceBefore=7, spaceAfter=18)]

    story += [Paragraph("01 · Product workflow", styles["h1"]),
              Paragraph("Customers scan a QR code, rate food taste, waiting time, ambience, and staff service, then optionally write a comment and attach a photo. The owner dashboard separates possible emergencies from service improvements and shows an analysis of all feedback.", styles["body"])]
    flow = [
        [Paragraph("CUSTOMER", styles["center"]), Paragraph("INTAKE", styles["center"]), Paragraph("ROUTING", styles["center"]), Paragraph("OWNER", styles["center"])],
        [Paragraph("QR feedback form<br/>ratings · comment · optional photo", styles["center"]),
         Paragraph("FastAPI<br/>validate · persist · identify submission", styles["center"]),
         Paragraph("LangGraph + Jev<br/>emergency · improvement · routine", styles["center"]),
         Paragraph("Phone alert for possible emergency<br/>dashboard for every response", styles["center"])],
    ]
    flow_table = Table(flow, colWidths=[1.7 * inch] * 4, rowHeights=[0.3 * inch, 0.75 * inch])
    flow_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PAPER), ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [flow_table, Spacer(1, 10), Paragraph("Possible emergency reports include a pest or foreign object in food, suspected contamination, allergen exposure, illness reportedly linked to food, or another plausible immediate safety risk. Poor taste, long waits, ambience, and staff-service concerns go to the improvement list without interrupting the owner by phone.", styles["body"])]

    story += [Paragraph("02 · Architecture and tech stack", styles["h1"])]
    rows = [
        ["Layer", "Prototype choice", "Responsibility"],
        ["Customer form", "Google Form / built-in QR form", "Ratings, free text, optional image"],
        ["Ingestion", "Apps Script + FastAPI", "Submit event, validation, webhook auth"],
        ["Orchestration", "LangGraph StateGraph", "Typed shared state, conditional routes, node boundaries"],
        ["Decision model", "Ollama Jev / TypeSafe", "Fast typed urgency and route decision"],
        ["Vision review", "Ollama vision model (optional)", "Classify photo relevance; never gate text safety alerts"],
        ["Persistence", "SQLite", "Feedback, workflow result, notification outbox"],
        ["Owner UI", "FastAPI + Jinja + CSS", "Read-only dashboard, emergency and improvement views"],
        ["Phone alert", "Twilio SMS adapter (optional)", "Send only possible emergency notifications"],
    ]
    t = Table([[Paragraph(str(cell), styles["small"]) for cell in row] for row in rows], colWidths=[1.0*inch, 2.0*inch, 3.8*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 8), Paragraph("Google Apps Script runs outside the local machine. It cannot reach localhost; use a temporary HTTPS tunnel for a connected local demo or deploy the API to a secure HTTPS host. Google Forms file-upload questions require respondents to sign in to a Google Account.", styles["small"])]

    image_width = 6.85 * inch
    image_height = 4.62 * inch
    story += [PageBreak(), Paragraph("Workflow visual · Feedback intake", styles["h1"]),
              Paragraph("This diagram shows how a customer response reaches the local FastAPI backend, passes through LangGraph routing, and becomes visible to the owner.", styles["body"]),
              PdfImage(str(workflow_image), width=image_width, height=image_height),
              Paragraph("The temporary HTTPS tunnel is for the local prototype. A hosted backend would replace that tunnel.", styles["small"]),
              PageBreak(), Paragraph("Dashboard guide · Owner view", styles["h1"]),
              Paragraph("The owner sees response totals and rating averages, urgent reports, improvement items, recurring themes, and a practical follow-up cue. Reports are labeled as customer-reported and require human review.", styles["body"]),
              PdfImage(str(dashboard_image), width=image_width, height=image_height),
              PageBreak(), Paragraph("03 · LangGraph building blocks", styles["h1"]),
              Paragraph("LangGraph keeps the workflow explicit and reviewable. The prototype uses bounded nodes and conditional edges, not open-ended model-driven tool loops.", styles["body"])]
    graph_rows = [
        ["Building block", "Use in Chai House"],
        ["State", "One typed FeedbackState carries the feedback ID, ratings, comment, image path, urgency, category, summary, and notification status."],
        ["Node", "A named function performs one bounded job: Jev triage, image review, emergency alert preparation, improvement routing, persistence, or analysis."],
        ["Conditional edge", "Routes emergency text to the emergency agent; sends reports with a photo through optional image review first; sends non-emergency feedback to improvement or routine handling."],
        ["Persistence", "SQLite records both the response and notification outbox so processing status and alert outcome are visible."],
        ["Fallback", "If Ollama is unavailable, deterministic hazard terms and ratings classify the report; failures are saved for owner review."],
    ]
    gt = Table([[Paragraph(str(cell), styles["small"]) for cell in row] for row in graph_rows], colWidths=[1.35*inch, 5.45*inch], repeatRows=1)
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [gt, Paragraph("Graph outline", styles["h2"]),
              Paragraph("START -> Jev triage -> { emergency + photo: image review -> emergency agent; emergency + no photo: emergency agent; improvement: improvement agent; routine: routine node } -> persist result -> END", styles["code"]),
              Paragraph("Dashboard analysis uses a separate LangGraph StateGraph and a bounded analyst node. SQL computes counts and average ratings first; the narrative model receives only those precomputed metrics and must not invent numbers.", styles["body"])]

    story += [Paragraph("04 · Three agent roles", styles["h1"])]
    roles = [
        ["01", "Emergency review", "Uses Jev triage plus optional image relevance review. Produces a concise owner alert. Credible text reports trigger the alert even when no photo is attached."],
        ["02", "Improvement feedback", "Groups taste, wait, staff, and ambience feedback and gives a practical review action. Does not send owner phone alerts."],
        ["03", "Dashboard analysis", "Summarizes supplied metrics, supported positive themes, recurring improvement areas, and next actions. Counts are calculated by code."],
    ]
    for num, title, desc in roles:
        card = Table([[Paragraph(f"<b>{num}</b>", styles["center"]), Paragraph(f"<b>{title}</b><br/>{desc}", styles["body"])]], colWidths=[0.48*inch, 6.32*inch])
        card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [card, Spacer(1, 6)]

    story += [PageBreak(), Paragraph("05 · Guardrails and safety policy", styles["h1"]),
              Paragraph("The model classifies customer reports; it does not verify incidents or make food-safety determinations. Alert rules belong to application code and should be reviewed with the cafe owner before live operation.", styles["body"])]
    guardrails = [
        ("No photo gate", "A plausible immediate safety report triggers an owner alert whether or not a photo is supplied. Image processing can fail or be inconclusive without blocking the alert."),
        ("Images are evidence to review", "A photo may support or conflict with a report, but cannot prove when or where it was taken. A photo alone without a relevant report does not create an emergency."),
        ("Unverified wording", "Use ‘customer reported’ and ‘possible’. Never phrase an allegation as a confirmed event."),
        ("Hard policy override", "Explicit hazard terms are protected by a deterministic rule; Jev cannot downgrade them. Model uncertainty is saved for owner review."),
        ("Separation of outcomes", "Possible immediate risk -> phone alert; service/quality concerns -> dashboard improvement queue; all reports -> analysis."),
        ("No invented analytics", "SQL calculates counts and averages. The analysis agent may describe only supplied metrics and should say ‘not enough data’ for weak patterns."),
        ("Data minimization", "Avoid collecting names, phone numbers, or email unless a later operational need is approved. Keep photos optional and limit their size and type."),
        ("Notification deduplication", "Use a unique feedback ID and one outbox entry per report to reduce duplicate SMS alerts."),
        ("Human review", "The dashboard labels reports as customer-reported. The owner remains responsible for deciding what operational response to take."),
    ]
    for title, body in guardrails:
        story += [KeepTogether([Paragraph(f"<font color='{RED.hexval()}'><b>•</b></font>  <b>{title}</b> — {body}", styles["body"])])]

    story += [Paragraph("06 · Jev decision contract", styles["h1"]),
              Paragraph("Jev is the routing decision step and the main efficiency factor: one request can answer typed questions such as urgency and route. It is not the image model, the notification provider, or the source of computed dashboard statistics.", styles["body"]),
              Paragraph("Input: feedback text and four 1-5 ratings. Output urgency: emergency | improvement | routine. The workflow validates the label, applies hard safety overrides, then follows a known LangGraph edge. The local Jev-style endpoint requires Ollama 0.35+ and a decision model such as nimble. Older versions or unavailable models use a deterministic fallback.", styles["code"]),
              Paragraph("Suggested production review", styles["h2"]),
              Paragraph("Before relying on live alerts, review examples with the owner, especially multilingual and misspelled reports; measure missed emergencies and false alarms; confirm who receives SMS and at what hours; and secure the dashboard behind owner authentication before public deployment.", styles["body"])]

    story += [Paragraph("07 · Prototype boundaries", styles["h1"]),
              Paragraph("The prototype includes a mobile form, SQLite persistence, a LangGraph workflow, Jev and Ollama adapters, optional Twilio SMS, dashboard filters, a generated feedback QR, and this architecture PDF. Live Jev, vision, Google Forms, and SMS behavior require local model availability and credentials/configuration. Without those settings, the app remains runnable using deterministic fallback and demo-logged alerts.", styles["body"]),
              Paragraph("Local demo URL: http://127.0.0.1:8000 · Health: /health · QR: /static/qr-feedback.png · API: /api/dashboard", styles["code"]),
              Spacer(1, 8), HRFlowable(width="100%", thickness=1, color=LINE), Spacer(1, 8),
              Paragraph("CHAI HOUSE FEEDBACK STUDIO · IMPLEMENTATION NOTE · PROTOTYPE", styles["kicker"])]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(0.68 * inch, 0.48 * inch, 7.82 * inch, 0.48 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.68 * inch, 0.31 * inch, "Chai House Feedback Studio · Internal prototype guide")
        canvas.drawRightString(7.82 * inch, 0.31 * inch, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
