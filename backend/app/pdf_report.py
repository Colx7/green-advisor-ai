from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def build_pdf_report(project, assessment) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{project.company_name}绿色转型与出海准备度诊断报告",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "CJKBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=10, leading=17, wordWrap="CJK"
    )
    title = ParagraphStyle(
        "CJKTitle", parent=body, fontSize=24, leading=36, alignment=TA_CENTER, textColor=colors.HexColor("#173F33")
    )
    heading = ParagraphStyle(
        "CJKHeading", parent=body, fontSize=15, leading=24, spaceBefore=12, spaceAfter=8, textColor=colors.HexColor("#245B49")
    )
    small = ParagraphStyle("CJKSmall", parent=body, fontSize=8, leading=13, textColor=colors.HexColor("#71847D"))

    story = [
        Spacer(1, 38 * mm),
        Paragraph(project.company_name, title),
        Spacer(1, 8 * mm),
        Paragraph("绿色转型与出海准备度诊断报告", title),
        Spacer(1, 72 * mm),
        Paragraph(f"行业：{project.industry}　目标市场：{project.target_market or '待确认'}", body),
        PageBreak(),
        Paragraph("一、诊断摘要", heading),
        Paragraph(
            f"绿色成熟度得分：{assessment.total_score}/100；资料完整度：{assessment.completeness}%。"
            f"当前仍有 {len(assessment.missing_fields)} 项资料待确认。",
            body,
        ),
        Paragraph("二、五维诊断", heading),
    ]

    dimension_rows = [["维度", "得分", "待确认项"]]
    for item in assessment.dimensions:
        dimension_rows.append(
            [
                Paragraph(item["name"], body),
                f'{item["score"]}/{item["max_score"]}',
                Paragraph("、".join(item["pending"]) or "无", small),
            ]
        )
    dimension_table = Table(dimension_rows, colWidths=[45 * mm, 28 * mm, 82 * mm], repeatRows=1)
    dimension_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3E6")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D7CF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(dimension_table)
    story.append(Paragraph("三、优先风险与建议", heading))
    for index, risk in enumerate(assessment.risks, 1):
        story.extend(
            [
                Paragraph(f"{index}. [{risk['level']}] {risk['title']}", body),
                Paragraph(f"依据：{risk['basis']}", small),
                Paragraph(f"建议：{risk['recommendation']}", small),
            ]
        )
        citations = risk.get("citations", [])
        if citations:
            for citation in citations:
                source_url = escape(citation["source_url"], quote=True)
                source_text = escape(f"来源：{citation['authority']}｜{citation['title']}")
                story.append(
                    Paragraph(
                        f'{source_text}｜<link href="{source_url}" color="#2F775D"><u>打开官方来源</u></link>',
                        small,
                    )
                )
        else:
            story.append(Paragraph("来源：知识库依据不足，需人工确认。", small))
        story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("四、90天行动计划", heading))
    for item in assessment.action_plan:
        story.append(
            Paragraph(
                f"{item['phase']}｜{item['task']}｜责任角色：{item['owner']}｜交付物：{item['deliverable']}", body
            )
        )
    story.extend(
        [
            Spacer(1, 12 * mm),
            Paragraph(
                "免责声明：本报告为AI辅助分析演示，不构成法律、审计、认证或投资意见，最终结论需由专业顾问复核。",
                small,
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()
