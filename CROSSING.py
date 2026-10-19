import streamlit as st
import sqlite3
import datetime
import io
import urllib.parse
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line
from reportlab.graphics.barcode import qr, code128

# Page Configuration
st.set_page_config(page_title="Courier Solution", page_icon="📦", layout="centered")

# ----------------- WHATSAPP LINK GENERATOR FUNCTION -----------------
def create_whatsapp_link(phone_num, msg_text):
    clean_phone = ''.join(filter(str.isdigit, str(phone_num)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_text = urllib.parse.quote(msg_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

# ----------------- ડેટાબેઝ સેટઅપ -----------------
def init_db():
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cons_no TEXT UNIQUE,
            date TEXT,
            courier_co TEXT,
            mode TEXT,
            origin TEXT,
            dest TEXT,
            sender_name TEXT,
            sender_address TEXT,
            sender_city TEXT,
            rec_name TEXT,
            rec_address TEXT,
            rec_city TEXT,
            weight TEXT,
            pcs TEXT,
            amount TEXT,
            booking_type TEXT,
            bill_no TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE receipts ADD COLUMN bill_no TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT UNIQUE,
            party_address TEXT,
            party_city TEXT,
            mobile TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE parties ADD COLUMN mobile TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS party_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT,
            bill_no TEXT,
            date TEXT,
            amount TEXT,
            pay_mode TEXT,
            note TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no TEXT UNIQUE,
            party_name TEXT,
            bill_date TEXT,
            period TEXT,
            total_amount TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ----------------- 100% PERFECT A4 PORTRAIT RECEIPT PDF GENERATOR -----------------
def generate_hd_receipt_pdf(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=25, 
        leftMargin=25, 
        topMargin=20, 
        bottomMargin=20
    )
    story = []

    styles = getSampleStyleSheet()

    f_header_title = ParagraphStyle('HTitle', fontName='Helvetica-Bold', fontSize=26, leading=30, textColor=colors.HexColor('#002147'))
    f_header_sub = ParagraphStyle('HSub', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#333333'))
    f_label_sm = ParagraphStyle('LblSm', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.black)
    f_val_lg = ParagraphStyle('ValLg', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.black)
    f_val_huge = ParagraphStyle('ValHuge', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.black)
    f_val_blue = ParagraphStyle('ValBlue', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.blue)
    f_val_green = ParagraphStyle('ValGreen', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#008000'))
    f_footer = ParagraphStyle('Foot', fontName='Helvetica', fontSize=9, leading=11, textColor=colors.HexColor('#444444'))

    barcode_obj = code128.Code128(cons_no, barHeight=35, barWidth=1.5)
    
    header_data = [
        [
            Paragraph("📦 <b>COURIER SOLUTION</b>", f_header_title),
            Paragraph("Consignment Number", f_label_sm)
        ],
        [
            Paragraph("<b>EXPRESS CARGO & LOGISTICS SERVICES</b>", f_header_sub),
            barcode_obj
        ],
        [
            "",
            Paragraph(f"<b>{cons_no}</b>", f_val_lg)
        ]
    ]

    t_header = Table(header_data, colWidths=[335, 210])
    t_header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('LINEBEFORE', (1,0), (1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    row2_data = [
        [
            Paragraph(f"<b>Origin:</b> <font size=13 color='#002147'>{origin.upper()}</font><br/><b>Courier:</b> <font color='blue'>{courier_co.upper()}</font>", f_val_lg),
            Paragraph(f"<b>Destination:</b><br/><font size=16>{dest.upper()}</font>", f_val_huge),
            Paragraph(f"<b>Date:</b> {date}<br/><b>Booking:</b> {booking_type}", f_val_lg)
        ]
    ]
    t_row2 = Table(row2_data, colWidths=[175, 200, 170])
    t_row2.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))

    row3_data = [
        [
            Paragraph("CONSIGNOR (FROM)", f_val_lg),
            Paragraph("CONSIGNEE (TO)", f_val_lg)
        ],
        [
            Paragraph(f"<font size=14 color='#002147'><b>{sender_name.upper()}</b></font><br/><br/><b>Address:</b> {sender_address}<br/><br/><b>City/Pin:</b> {sender_city}", f_val_lg),
            Paragraph(f"<font size=14 color='#002147'><b>{rec_name.upper()}</b></font><br/><br/><b>Address:</b> {rec_address}<br/><br/><b>City/Pin:</b> {rec_city}", f_val_lg)
        ]
    ]
    t_row3 = Table(row3_data, colWidths=[272.5, 272.5])
    t_row3.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#E6ECF2')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#E6ECF2')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))

    row4_data = [
        [
            Paragraph("Pieces (Pcs)", f_label_sm),
            Paragraph("Weight (Kg)", f_label_sm),
            Paragraph("Total Amount (RS)", f_label_sm),
            Paragraph("Payment Status", f_label_sm)
        ],
        [
            Paragraph(f"<b>{pcs} Pcs</b>", f_val_huge),
            Paragraph(f"<b>{weight} Kg</b>", f_val_huge),
            Paragraph(f"<b>RS {amount}/-</b>", f_val_green),
            Paragraph(f"<b>{booking_type}</b>", f_val_blue if booking_type == 'Cash' else f_val_lg)
        ]
    ]
    t_row4 = Table(row4_data, colWidths=[120, 120, 165, 140])
    t_row4.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F0F4F8')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))

    foot_data = [
        [
            Paragraph("<b>Shipment Remarks:</b> Booking Generated via Courier Solution Management System.<br/><i>* Risk Charge Included in Gross Amt, if any. Subject to terms & conditions.</i>", f_footer),
            Paragraph("____________________________<br/><b>Authorized Signatory</b><br/>(Courier Solution)", f_val_lg)
        ]
    ]
    t_foot = Table(foot_data, colWidths=[335, 210])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    story.append(t_header)
    story.append(Spacer(1, 6))
    story.append(t_row2)
    story.append(Spacer(1, 6))
    story.append(t_row3)
    story.append(Spacer(1, 6))
    story.append(t_row4)
    story.append(Spacer(1, 15))
    story.append(t_foot)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- BILL PDF INVOICE GENERATOR WITH UPI -----------------
def generate_pdf_invoice(bill_no, party_name, start_str, end_str, bill_date, items, total_amount):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    logo_style = ParagraphStyle('LogoStyle', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    invoice_head_style = ParagraphStyle('InvHead', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#d9534f'), alignment=1, spaceAfter=15)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, leading=13)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, fontName='Helvetica-Bold', leading=13)

    story.append(Paragraph("📦", logo_style))
    story.append(Paragraph("COURIER SOLUTION", title_style))
    story.append(Paragraph("Express Cargo & Logistics Services", sub_title_style))
    story.append(Paragraph("TAX INVOICE / MONTHLY BILL", invoice_head_style))

    details_data = [
        [
            Paragraph(f"<b>Invoice To:</b><br/><font size=11 color='#002147'><b>{party_name}</b></font><br/>Billing Period: {start_str} to {end_str}", normal_style),
            Paragraph(f"<b>Invoice No:</b> <font color='red'><b>{bill_no}</b></font><br/><b>Date:</b> {bill_date}<br/><b>Status:</b> UNPAID", normal_style)
        ]
    ]
    t_details = Table(details_data, colWidths=[310, 230])
    t_details.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_details)
    story.append(Spacer(1, 15))

    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Consignment No</b>', bold_style), Paragraph('<b>Date</b>', bold_style), Paragraph('<b>Courier Co</b>', bold_style), Paragraph('<b>Destination</b>', bold_style), Paragraph('<b>Recipient</b>', bold_style), Paragraph('<b>Wt(kg)</b>', bold_style), Paragraph('<b>Amount(RS)</b>', bold_style)]
    data = [headers]

    for idx, r in enumerate(items, 1):
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(str(r[1]), normal_style),
            Paragraph(str(r[2]), normal_style),
            Paragraph(str(r[3]), bold_style),
            Paragraph(str(r[4]), normal_style),
            Paragraph(str(r[5]), normal_style),
            Paragraph(str(r[6]), normal_style),
            Paragraph(f"RS {float(r[7]):,.2f}", normal_style)
        ])

    t_items = Table(data, colWidths=[25, 95, 65, 75, 85, 100, 35, 60])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 15))

    total_data = [
        [
            Paragraph("<b>TOTAL PAYABLE AMOUNT:</b>", ParagraphStyle('TotLbl', parent=styles['Normal'], fontSize=11, alignment=2)),
            Paragraph(f"<b>RS {total_amount:,.2f}/-</b>", ParagraphStyle('TotVal', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#008000'), alignment=2))
        ]
    ]
    t_total = Table(total_data, colWidths=[380, 160])
    t_total.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#008000')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_total)
    story.append(Spacer(1, 15))

    upi_id = "7043721851@yapl"
    qr_code_widget = qr.QrCodeWidget(f"upi://pay?pa={upi_id}&pn=Courier%20Solution&am={total_amount}&cu=INR")
    bounds = qr_code_widget.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]
    
    d = Drawing(85, 85)
    d.add(qr_code_widget)
    d.scale(85.0 / qr_width, 85.0 / qr_height)

    qr_text = Paragraph(
        "<b>📱 Scan & Pay via UPI / Google Pay / PhonePe:</b><br/>"
        "<font size=11 color='#002147'><b>Google Pay Number: 7043721851</b></font><br/>"
        f"<font size=10 color='#d9534f'><b>UPI ID: {upi_id}</b></font>",
        normal_style
    )

    qr_table = Table([[d, qr_text]], colWidths=[95, 445])
    qr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f4f8')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(qr_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<i>* Subject to Terms & Conditions. Payment due within 7 days.</i>", ParagraphStyle('Foot', parent=styles['Normal'], fontSize=8, textColor=colors.gray)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- PAYMENT RECEIPT PDF GENERATOR -----------------
def generate_payment_pdf_receipt(rec_id, party_name, bill_no, pay_date, pay_amount, pay_mode, pay_note):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    rec_head_style = ParagraphStyle('RecHead', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#008000'), alignment=1, spaceAfter=20)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=11, textColor=colors.black, leading=16)

    story.append(Paragraph("COURIER SOLUTION", title_style))
    story.append(Paragraph("Express Cargo & Logistics Services", sub_title_style))
    story.append(Paragraph("PAYMENT RECEIPT (ચુકવણી જમા રસીદ)", rec_head_style))

    data = [
        [Paragraph("<b>Receipt No:</b>", normal_style), Paragraph(f"PAY-REC-{rec_id:04d}", normal_style)],
        [Paragraph("<b>Payment Date:</b>", normal_style), Paragraph(f"{pay_date}", normal_style)],
        [Paragraph("<b>Received From (Party Name):</b>", normal_style), Paragraph(f"<font size=12 color='#002147'><b>{party_name}</b></font>", normal_style)],
        [Paragraph("<b>Against Bill No:</b>", normal_style), Paragraph(f"<font color='red'><b>{bill_no}</b></font>", normal_style)],
        [Paragraph("<b>Payment Mode:</b>", normal_style), Paragraph(f"<b>{pay_mode}</b>", normal_style)],
        [Paragraph("<b>Amount Received:</b>", normal_style), Paragraph(f"<font size=13 color='green'><b>₹ {float(pay_amount):,.2f}/-</b></font>", normal_style)],
        [Paragraph("<b>Note / Reference:</b>", normal_style), Paragraph(f"{pay_note if pay_note else 'N/A'}", normal_style)]
    ]

    t = Table(data, colWidths=[200, 320])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#008000')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e0e0e0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 40))

    footer_data = [
        [Paragraph("<b>Customer Signature</b>", normal_style), Paragraph("<b>Authorized Signatory</b><br/>(Courier Solution)", ParagraphStyle('RAlign', parent=normal_style, alignment=2))]
    ]
    t_foot = Table(footer_data, colWidths=[260, 260])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))
    story.append(t_foot)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- BILLS SUMMARY PDF REPORT -----------------
def generate_bills_summary_pdf(all_bills, period_str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black)

    story.append(Paragraph("📦 COURIER SOLUTION", title_style))
    story.append(Paragraph(f"<b>GENERATED MONTHLY BILLS SUMMARY REPORT</b><br/>Period: {period_str}", sub_style))

    headers = [
        Paragraph('<b>Sr</b>', bold_style), 
        Paragraph('<b>Bill No</b>', bold_style), 
        Paragraph('<b>Party Name</b>', bold_style), 
        Paragraph('<b>Bill Date</b>', bold_style), 
        Paragraph('<b>Period</b>', bold_style), 
        Paragraph('<b>Amount (RS)</b>', bold_style)
    ]
    data = [headers]

    tot_amt = 0.0
    for idx, b in enumerate(all_bills, 1):
        amt_val = float(b[5]) if b[5] else 0.0
        tot_amt += amt_val
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(f"<b>{b[1]}</b>", normal_style),
            Paragraph(str(b[2]), normal_style),
            Paragraph(str(b[3]), normal_style),
            Paragraph(str(b[4]), normal_style),
            Paragraph(f"RS {amt_val:,.2f}", normal_style)
        ])

    data.append([
        Paragraph("<b>TOTAL</b>", bold_style),
        "", "", "", "",
        Paragraph(f"<b>RS {tot_amt:,.2f}/-</b>", ParagraphStyle('GTotal', parent=bold_style, textColor=colors.HexColor('#008000')))
    ])

    t = Table(data, colWidths=[30, 90, 180, 75, 100, 75])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('SPAN', (0, -1), (4, -1)),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- PAYMENT RECEIVED SUMMARY PDF REPORT -----------------
def generate_payments_summary_pdf(pay_rows, period_str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#008000'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black)

    story.append(Paragraph("💳 COURIER SOLUTION", title_style))
    story.append(Paragraph(f"<b>PAYMENT RECEIVED SUMMARY REPORT</b><br/>Period: {period_str}", sub_style))

    headers = [
        Paragraph('<b>Sr</b>', bold_style), 
        Paragraph('<b>Party Name</b>', bold_style), 
        Paragraph('<b>Bill No</b>', bold_style), 
        Paragraph('<b>Date</b>', bold_style), 
        Paragraph('<b>Mode</b>', bold_style), 
        Paragraph('<b>Note / Ref</b>', bold_style),
        Paragraph('<b>Amount (RS)</b>', bold_style)
    ]
    data = [headers]

    tot_amt = 0.0
    for idx, r in enumerate(pay_rows, 1):
        amt_val = float(r[4]) if r[4] else 0.0
        tot_amt += amt_val
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(f"<b>{r[1]}</b>", normal_style),
            Paragraph(str(r[2]), normal_style),
            Paragraph(str(r[3]), normal_style),
            Paragraph(str(r[5]), normal_style),
            Paragraph(str(r[6]) if r[6] else "-", normal_style),
            Paragraph(f"RS {amt_val:,.2f}", normal_style)
        ])

    data.append([
        Paragraph("<b>TOTAL RECEIVED</b>", bold_style),
        "", "", "", "", "",
        Paragraph(f"<b>RS {tot_amt:,.2f}/-</b>", ParagraphStyle('GTotal', parent=bold_style, textColor=colors.HexColor('#008000')))
    ])

    t = Table(data, colWidths=[25, 140, 80, 65, 75, 90, 75])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#008000')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('SPAN', (0, -1), (5, -1)),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- DASHBOARD UI -----------------
st.title("📦 COURIER SOLUTION")
st.caption("Express Cargo & Logistics Management System")
st.markdown("---")

# SIDEBAR NAVIGATION
st.sidebar.header("⚙️ નેવિગેશન & ફિલ્ટર")
menu = st.sidebar.radio("મેનુ પસંદ કરો (Menu)", [
    "➕ Add Account Party (પાર્ટી ઉમેરો)",
    "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)",
    "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)",
    "📊 Party Monthly Billing (ડિજિટલ PDF બિલ)",
    "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)"
])

st.sidebar.markdown("---")
st.sidebar.subheader("📅 તારીખ ફિલ્ટર (Date Filter)")
today = datetime.date.today()
first_day_curr_month = today.replace(day=1)

start_date = st.sidebar.date_input("શરૂઆતની તારીખ (From Date):", value=first_day_curr_month)
end_date = st.sidebar.date_input("છેલ્લી તારીખ (To Date):", value=today)

start_str = start_date.strftime("%d/%m/%Y")
end_str = end_date.strftime("%d/%m/%Y")

# ----------------- ૧. ADD PARTY MASTER -----------------
if menu == "➕ Add Account Party (પાર્ટી ઉમેરો)":
    st.subheader("➕ Add Monthly Account Party Master")
    with st.form("party_form", clear_on_submit=True):
        p_name = st.text_input("Party Name (પાર્ટીનું નામ):")
        p_addr = st.text_input("Address (સરનામું):")
        p_city = st.text_input("City / Pin Code (શહેર / પીનકોડ):")
        p_mob = st.text_input("WhatsApp Mobile No (મોબાઈલ નંબર):")
        submit_p = st.form_submit_button("Save Party", type="primary")

        if submit_p:
            if not p_name.strip():
                st.error("મહેરબાની કરીને Party Name ભરો!")
            else:
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO parties (party_name, party_address, party_city, mobile) VALUES (?, ?, ?, ?)", (p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip()))
                    conn.commit()
                    st.success(f"પાર્ટી '{p_name}' સફળતાપૂર્વક ઉમેરાઈ ગઈ છે!")
                except sqlite3.IntegrityError:
                    st.error("આ નામની પાર્ટી પહેલેથી જ અસ્તિત્વમાં છે!")
                conn.close()

    st.markdown("---")
    st.write("### 🏢 સેવ થયેલી પાર્ટીઓની યાદી & ડિલીટ:")
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
    p_rows = cursor.fetchall()
    conn.close()
    
    if p_rows:
        for r in p_rows:
            col_p1, col_p2 = st.columns([4, 1])
            with col_p1:
                st.write(f"🏢 **{r[1]}** | Mobile: {r[4]} | {r[2]} ({r[3]})")
            with col_p2:
                if st.button("🗑️ Delete", key=f"del_party_{r[0]}"):
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM parties WHERE id=?", (r[0],))
                    conn.commit()
                    conn.close()
                    st.success(f"પાર્ટી '{r[1]}' ડિલીટ થઈ ગઈ છે!")
                    st.rerun()

# ----------------- ૨. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)":
    tab1, tab2, tab3 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History & Delete (હિસ્ટ્રી)", "🖨️ Re-Print Receipt (ફરીવાર પ્રિન્ટ)"])

    with tab1:
        st.subheader("Cash Courier Booking")
        col1, col2 = st.columns(2)
        with col1:
            cons_no = st.text_input("Consignment No:", key="c_cons")
            date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="c_date")
            courier_co = st.text_input("Courier Company:", "DTDC", key="c_co")
            mode = st.text_input("Service Mode:", "Surface", key="c_mode")
            origin = st.text_input("Origin:", "BHAVNAGAR", key="c_orig")
            dest = st.text_input("Destination:", key="c_dest")
        with col2:
            sender_name = st.text_input("Sender Name:", key="c_s_name")
            sender_address = st.text_input("Sender Address:", key="c_s_addr")
            sender_city = st.text_input("Sender City/Pin:", key="c_s_city")
            rec_name = st.text_input("Recipient Name:", key="c_r_name")
            rec_address = st.text_input("Recipient Address:", key="c_r_addr")
            rec_city = st.text_input("Recipient City/Pin:", key="c_r_city")

        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="c_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="c_pcs")
        with col5: amount = st.text_input("Total Amount (RS):", key="c_amt")

        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No (મોબાઈલ નંબર):", key="c_wa_num")

        if st.button("💾 Save & Generate Cash Receipt", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("મહેરબાની કરીને Consignment No, Sender Name, Recipient Name અને Amount ભરો!")
            else:
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Cash'))
                    conn.commit()
                    st.success(f"Cash Entry Saved Successfully for Consignment: {cons_no}")
                    
                    pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash')
                    
                    st.download_button(label="📄 Step 1: Download Printable PDF Receipt", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")

                    # 📲 WHATSAPP BUTTON
                    if c_whatsapp_num.strip():
                        wa_msg = (
                            "📦 COURIER SOLUTION RECEIPT\n\n"
                            f"Hello {sender_name},\n"
                            "Your courier booking is confirmed!\n\n"
                            f"Consignment No: {cons_no}\n"
                            f"Date: {date_entry}\n"
                            f"Courier: {courier_co}\n"
                            f"To: {rec_name} ({dest})\n"
                            f"Weight: {weight} Kg ({pcs} Pcs)\n"
                            f"Amount Paid: RS {amount}/-\n\n"
                            "Thank you for choosing Courier Solution!"
                        )
                        wa_url = create_whatsapp_link(c_whatsapp_num.strip(), wa_msg)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Step 2: Send Confirmation on WhatsApp</a>', unsafe_allow_html=True)

                except sqlite3.IntegrityError:
                    st.error("આ Consignment Number પહેલેથી જ અસ્તિત્વમાં છે!")
                conn.close()

    with tab2:
        st.subheader("📜 Cash Booking Records & Collection History")
        st.info(f"📅 ફિલ્ટર કરેલી તારીખ ગાળો: **{start_str}** થી **{end_str}**")

        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, amount FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        cash_rows = cursor.fetchall()
        conn.close()

        filtered_cash = []
        tot_cash = 0

        for r in cash_rows:
            rec_date_str = r[2]
            try:
                rec_dt = datetime.datetime.strptime(rec_date_str, "%d/%m/%Y").date()
                if start_date <= rec_dt <= end_date:
                    filtered_cash.append(r)
                    tot_cash += float(r[5])
            except:
                filtered_cash.append(r)
                try: tot_cash += float(r[5])
                except: pass

        if filtered_cash:
            st.metric("💰 Selected Period Cash Collection", f"RS {tot_cash:,.2f}/-")
            st.write("---")
            for r in filtered_cash:
                col_c1, col_c2 = st.columns([4, 1])
                with col_c1:
                    st.write(f"🧾 **Cons: {r[1]}** | Date: {r[2]} | From: {r[3]} ➔ To: {r[4]} | **Amount: RS {r[5]}/-**")
                with col_c2:
                    if st.button("🗑️ Delete", key=f"del_cash_{r[0]}"):
                        conn = sqlite3.connect("courier_database.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM receipts WHERE id=?", (r[0],))
                        conn.commit()
                        conn.close()
                        st.success(f"Consignment {r[1]} ડિલીટ થઈ ગયું છે!")
                        st.rerun()
        else:
            st.warning("આ પસંદ કરેલી તારીખ ગાળામાં કોઈ કેશ બુકિંગ એન્ટ્રી મળી નથી.")

    with tab3:
        st.subheader("🖨️ Re-Print / View Receipt by Consignment No")
        search_cons = st.text_input("Enter Consignment No to Print (કન્સાઇનમેન્ટ નંબર નાખો):")
        if st.button("🔍 Search & Print Receipt", type="primary"):
            if not search_cons.strip():
                st.error("મહેરબાની કરીને કન્સાઇનમેન્ટ નંબર ભરો!")
            else:
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type FROM receipts WHERE cons_no=?", (search_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()

                if rec_data:
                    st.success("રસીદ સફળતાપૂર્વક મળી ગઈ છે!")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15])
                    st.download_button(label="🖨️ Download HD Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{rec_data[0]}.pdf", mime="application/pdf")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૩. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    tab_cr1, tab_cr2, tab_cr3 = st.tabs(["📋 Credit Booking (નવી એન્ટ્રી)", "🖨️ Re-Print Credit Receipt", "📜 Credit History & View (હિસ્ટ્રી & સુધારો)"])

    with tab_cr1:
        st.subheader("Credit Account Courier Booking")
        
        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
        parties_data = cursor.fetchall()
        conn.close()

        party_names = [r[0] for r in parties_data]

        if not party_names:
            st.warning("⚠️ પહેલા મેનુમાંથી 'Add Account Party' પસંદ કરીને પાર્ટી ઉમેરો!")
        else:
            selected_party = st.selectbox("Select Party Name (પાર્ટી સિલેક્ટ કરો):", party_names)
            
            def_addr, def_city, def_mob = "", "", ""
            for p in parties_data:
                if p[0] == selected_party:
                    def_addr, def_city, def_mob = p[1], p[2], p[3] if len(p) > 3 else ""
                    break

            col1, col2 = st.columns(2)
            with col1:
                cons_no = st.text_input("Consignment No:", key="cr_cons")
                date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="cr_date")
                courier_co = st.text_input("Courier Company:", "DTDC", key="cr_co")
                mode = st.text_input("Service Mode:", "Surface", key="cr_mode")
                origin = st.text_input("Origin:", "BHAVNAGAR", key="cr_orig")
                dest = st.text_input("Destination:", key="cr_dest")
            with col2:
                sender_address = st.text_input("Sender Address:", value=def_addr, key="cr_s_addr")
                sender_city = st.text_input("Sender City/Pin:", value=def_city, key="cr_s_city")
                rec_name = st.text_input("Recipient Name:", key="cr_r_name")
                rec_address = st.text_input("Recipient Address:", key="cr_r_addr")
                rec_city = st.text_input("Recipient City/Pin:", key="cr_r_city")

            col3, col4, col5 = st.columns(3)
            with col3: weight = st.text_input("Weight (Kg):", "1.0", key="cr_wt")
            with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="cr_pcs")
            with col5: amount = st.text_input("Amount (RS):", key="cr_amt")

            cr_wa_mob = st.text_input("Party WhatsApp Mobile No:", value=def_mob if def_mob else "", key="cr_wa_mob")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                save_only = st.button("💾 Save Entry Only (ફક્ત સેવ કરો)", type="secondary", use_container_width=True)
            with btn_col2:
                save_print = st.button("🖨️ Save & Generate Print (સેવ અને પ્રિન્ટ)", type="primary", use_container_width=True)

            if save_only or save_print:
                if not cons_no or not rec_name or not amount:
                    st.error("મહેરબાની કરીને Consignment No, Recipient Name અને Amount ભરો!")
                else:
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    try:
                        cursor.execute("""
                            INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Credit Account'))
                        conn.commit()
                        st.success(f"Credit Entry Saved for Party '{selected_party}' - Consignment: {cons_no}")

                        if save_print:
                            pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account')
                            st.download_button(label="📄 Step 1: Download PDF Receipt", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")

                        # 📲 WHATSAPP BUTTON FOR CREDIT BOOKING
                        if cr_wa_mob.strip():
                            wa_msg = (
                                "📦 COURIER BOOKING CONFIRMATION\n\n"
                                f"Party Name: {selected_party}\n"
                                f"Consignment No: {cons_no}\n"
                                f"Date: {date_entry}\n"
                                f"Destination: {dest}\n"
                                f"Recipient: {rec_name}\n"
                                f"Weight: {weight} Kg ({pcs} Pcs)\n"
                                f"Amount: RS {amount}/-\n\n"
                                "Thank you for business with Courier Solution!"
                            )
                            wa_url = create_whatsapp_link(cr_wa_mob.strip(), wa_msg)
                            st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Step 2: Send Confirmation on WhatsApp</a>', unsafe_allow_html=True)

                    except sqlite3.IntegrityError:
                        st.error("આ Consignment Number પહેલેથી જ અસ્તિત્વમાં છે!")
                    conn.close()

    with tab_cr2:
        st.subheader("🖨️ Re-Print Credit Receipt by Consignment No")
        search_cr_cons = st.text_input("Enter Consignment No to Print (કન્સાઇનમેન્ટ નંબર નાખો):", key="search_cr")
        if st.button("🔍 Search & Print Credit Receipt", type="primary"):
            if not search_cr_cons.strip():
                st.error("મહેરબાની કરીને કન્સાઇનમેન્ટ નંબર ભરો!")
            else:
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type FROM receipts WHERE cons_no=?", (search_cr_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()

                if rec_data:
                    st.success("રસીદ સફળતાપૂર્વક મળી ગઈ છે!")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15])
                    st.download_button(label="🖨️ Download HD Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{search_cr_cons}.pdf", mime="application/pdf")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

    with tab_cr3:
        st.subheader("📜 View Credit Account Bookings & Edit/Delete")
        st.info(f"📅 ફિલ્ટર તારીખ: **{start_str}** થી **{end_str}**")

        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
        p_filter_list = ["🌐 All Parties (બધી પાર્ટી)"] + [r[0] for r in cursor.fetchall()]
        
        sel_filter_party = st.selectbox("Filter by Party (પાર્ટી વાઈઝ ફિલ્ટર કરો):", p_filter_list, key="f_party_hist")

        if sel_filter_party == "🌐 All Parties (બધી પાર્ટી)":
            cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, dest, weight, amount, bill_no, courier_co, mode, origin, sender_address, sender_city, rec_address, rec_city, pcs FROM receipts WHERE booking_type='Credit Account' ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, dest, weight, amount, bill_no, courier_co, mode, origin, sender_address, sender_city, rec_address, rec_city, pcs FROM receipts WHERE booking_type='Credit Account' AND sender_name=? ORDER BY id DESC", (sel_filter_party,))
        
        cr_all_rows = cursor.fetchall()
        conn.close()

        filtered_cr = []
        tot_cr_amt = 0.0

        for r in cr_all_rows:
            rec_date_str = r[2]
            try:
                rec_dt = datetime.datetime.strptime(rec_date_str, "%d/%m/%Y").date()
                if start_date <= rec_dt <= end_date:
                    filtered_cr.append(r)
                    tot_cr_amt += float(r[7])
            except:
                filtered_cr.append(r)
                try: tot_cr_amt += float(r[7])
                except: pass

        st.metric("📊 Total Selected Credit Amount", f"RS {tot_cr_amt:,.2f}/-", f"Total Entries: {len(filtered_cr)}")
        st.markdown("---")

        if filtered_cr:
            for r in filtered_cr:
                rec_id = r[0]
                cons = r[1]
                r_date = r[2]
                party = r[3]
                recip = r[4]
                destination = r[5]
                amt = r[7]
                b_status = f" (Bill: {r[8]})" if r[8] else " (Unbilled)"

                with st.expander(f"🧾 Cons: {cons} | Party: {party} | Date: {r_date} | RS {amt}/-{b_status}"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.write(f"**Recipient:** {recip} ({destination})")
                        st.write(f"**Courier:** {r[9]} | **Mode:** {r[10]}")
                        st.write(f"**Weight:** {r[6]} Kg | **Pieces:** {r[16]}")
                    with col_e2:
                        pdf_b = generate_hd_receipt_pdf(cons, r_date, r[9], r[10], r[11], destination, party, r[12], r[13], recip, r[14], r[15], r[6], r[16], amt, 'Credit Account')
                        st.download_button("🖨️ Download Receipt PDF", data=pdf_b, file_name=f"Receipt_{cons}.pdf", mime="application/pdf", key=f"dl_pdf_{rec_id}")

                    st.markdown("#### ✏️ Edit Entry (એન્ટ્રીમાં સુધારો કરો):")
                    with st.form(f"edit_form_{rec_id}"):
                        edit_col1, edit_col2 = st.columns(2)
                        with edit_col1:
                            e_rec_name = st.text_input("Recipient Name:", value=recip)
                            e_dest = st.text_input("Destination:", value=destination)
                        with edit_col2:
                            e_wt = st.text_input("Weight (Kg):", value=r[6])
                            e_amt = st.text_input("Amount (RS):", value=amt)
                        
                        btn_update = st.form_submit_button("💾 Save Changes (સુધારો સેવ કરો)")

                        if btn_update:
                            conn = sqlite3.connect("courier_database.db")
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE receipts 
                                SET rec_name=?, dest=?, weight=?, amount=?
                                WHERE id=?
                            """, (e_rec_name.strip(), e_dest.strip(), e_wt.strip(), e_amt.strip(), rec_id))
                            conn.commit()
                            conn.close()
                            st.success(f"Consignment {cons} સફળતાપૂર્વક અપડેટ થઈ ગયું છે!")
                            st.rerun()

                    if st.button(f"🗑️ Delete Entry ({cons})", key=f"del_cr_{rec_id}", type="secondary"):
                        conn = sqlite3.connect("courier_database.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM receipts WHERE id=?", (rec_id,))
                        conn.commit()
                        conn.close()
                        st.success(f"Consignment {cons} સફળતાપૂર્વક ડિલીટ થઈ ગયું છે!")
                        st.rerun()
        else:
            st.warning("પસંદ કરેલી પાર્ટી અથવા તારીખ ગાળામાં કોઈ ક્રેડિટ બુકિંગ મળેલ નથી.")

# ----------------- ૪. DIGITAL MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ PDF બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator & WhatsApp Share")
    st.info(f"📅 પસંદ કરેલ બિલિંગ સમયગાળો: **{start_str}** થી **{end_str}**")

    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name, mobile FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    conn.close()

    p_list = [r[0] for r in p_data]

    if not p_list:
        st.warning("કોઈ પાર્ટી ઉમેરેલી નથી.")
    else:
        select_options = ["🌐 All Parties (બધી પાર્ટીઓ માટે એકસાથે)"] + p_list
        sel_party = st.selectbox("Select Party for Bill (બિલ બનાવવાની પાર્ટી પસંદ કરો):", select_options)
        
        party_mob = ""
        for p in p_data:
            if p[0] == sel_party:
                party_mob = p[1] if p[1] else ""
                break

        if sel_party != "🌐 All Parties (બધી પાર્ટીઓ માટે એકસાથે)":
            bill_party_mob = st.text_input("Party WhatsApp Mobile No (મોબાઈલ નંબર):", value=party_mob, key="b_mob_input")

        if sel_party == "🌐 All Parties (બધી પાર્ટીઓ માટે એકસાથે)":
            if st.button("🚀 Generate All Parties Bills (બધી પાર્ટીના બિલ બનાવો)", type="primary"):
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                success_count = 0
                for party in p_list:
                    cursor.execute("SELECT id, cons_no, date, courier_co, dest, rec_name, weight, amount FROM receipts WHERE sender_name=? AND booking_type='Credit Account' AND (bill_no IS NULL OR bill_no='') ORDER BY id DESC", (party,))
                    b_rows = cursor.fetchall()

                    filtered_bill = []
                    tot_bill = 0
                    for r in b_rows:
                        try:
                            if start_date <= datetime.datetime.strptime(r[2], "%d/%m/%Y").date() <= end_date:
                                filtered_bill.append(r)
                                tot_bill += float(r[7])
                        except: pass

                    if filtered_bill:
                        cursor.execute("SELECT COUNT(*) FROM bills")
                        b_count = cursor.fetchone()[0] + 1
                        generated_bill_no = f"BILL-2026-{b_count:03d}"
                        cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                                      (generated_bill_no, party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                        for item in filtered_bill:
                            cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                        conn.commit()
                        success_count += 1
                conn.close()
                st.success(f"✅ કુલ {success_count} પાર્ટીઓ માટે નવા બિલ સફળતાપૂર્વક જનરેટ થઈ ગયા છે!")
                st.rerun()
        else:
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT bill_no, bill_date, total_amount FROM bills WHERE party_name=? AND period=?", (sel_party, f"{start_str} to {end_str}"))
            existing_bill = cursor.fetchone()
            conn.close()

            if existing_bill:
                st.warning(f"⚠️ આ પાર્ટી ('{sel_party}') માટે આ સમયગાળાનું બિલ પહેલેથી જ જનરેટ થઈ ગયેલ છે!")
                st.info(f"બિલ નંબર: **{existing_bill[0]}** | તારીખ: {existing_bill[1]} | કુલ રકમ: RS {existing_bill[2]}/-")
                
                # 📲 WHATSAPP BILL SHARE
                if bill_party_mob.strip():
                    wa_bill_msg = (
                        "🧾 COURIER SOLUTION TAX INVOICE\n\n"
                        f"To: {sel_party}\n"
                        f"Invoice No: {existing_bill[0]}\n"
                        f"Period: {start_str} to {end_str}\n"
                        f"Total Bill Amount: RS {existing_bill[2]}/-\n\n"
                        "Pay via Google Pay/UPI: 7043721851@yapl\n\n"
                        "Thank you for business with Courier Solution!"
                    )
                    wa_bill_url = create_whatsapp_link(bill_party_mob.strip(), wa_bill_msg)
                    st.markdown(f'<a href="{wa_bill_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-bottom:15px;">📲 Share Bill Details on WhatsApp</a>', unsafe_allow_html=True)

            else:
                conn_temp = sqlite3.connect("courier_database.db")
                cur_temp = conn_temp.cursor()
                cur_temp.execute("SELECT COUNT(*) FROM bills")
                b_count = cur_temp.fetchone()[0] + 1
                conn_temp.close()
                generated_bill_no = f"BILL-2026-{b_count:03d}"

                if st.button("📄 Generate & Create Digital PDF Invoice", type="primary"):
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, cons_no, date, courier_co, dest, rec_name, weight, amount FROM receipts WHERE sender_name=? AND booking_type='Credit Account' AND (bill_no IS NULL OR bill_no='') ORDER BY id DESC", (sel_party,))
                    b_rows = cursor.fetchall()

                    filtered_bill = []
                    tot_bill = 0
                    for r in b_rows:
                        try:
                            if start_date <= datetime.datetime.strptime(r[2], "%d/%m/%Y").date() <= end_date:
                                filtered_bill.append(r)
                                tot_bill += float(r[7])
                        except: pass

                    if filtered_bill:
                        cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                                      (generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                        for item in filtered_bill:
                            cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                        conn.commit()
                        conn.close()

                        pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, start_str, end_str, today.strftime("%d/%m/%Y"), filtered_bill, tot_bill)
                        st.success(f"✅ પાર્ટી '{sel_party}' નું બિલ સફળતાપૂર્વક જનરેટ થઈ ગયું છે!")
                        
                        st.download_button(label="📄 Step 1: Download Digital Invoice PDF", data=pdf_bytes, file_name=f"Invoice_{generated_bill_no}_{sel_party}.pdf", mime="application/pdf")

                        # 📲 WHATSAPP BILL SHARE
                        if bill_party_mob.strip():
                            wa_bill_msg = (
                                "🧾 COURIER SOLUTION TAX INVOICE\n\n"
                                f"To: {sel_party}\n"
                                f"Invoice No: {generated_bill_no}\n"
                                f"Period: {start_str} to {end_str}\n"
                                f"Total Bill Amount: RS {tot_bill:,.2f}/-\n\n"
                                "Pay via Google Pay/UPI: 7043721851@yapl\n\n"
                                "Thank you for business with Courier Solution!"
                            )
                            wa_bill_url = create_whatsapp_link(bill_party_mob.strip(), wa_bill_msg)
                            st.markdown(f'<a href="{wa_bill_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Step 2: Share Bill Details on WhatsApp</a>', unsafe_allow_html=True)
                    else:
                        conn.close()
                        st.info("કોઈ અનબિલ એન્ટ્રી મળી નથી.")

    st.markdown("---")
    st.subheader("📜 Generated Bills History & Delete")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, bill_no, party_name, bill_date, period, total_amount FROM bills ORDER BY id DESC")
    all_bills = cursor.fetchall()
    conn.close()

    if all_bills:
        summary_pdf_bytes = generate_bills_summary_pdf(all_bills, f"{start_str} to {end_str}")
        st.download_button(
            label="🖨️ Download Bills Summary Report (PDF)",
            data=summary_pdf_bytes,
            file_name=f"Bills_Summary_Report_{start_str}_to_{end_str}.pdf",
            mime="application/pdf",
            type="primary"
        )
        st.write("")

        for b in all_bills:
            col_b1, col_b2 = st.columns([4, 1])
            with col_b1:
                st.write(f"📄 **Bill No: {b[1]}** | Party: {b[2]} | Date: {b[3]} | Period: {b[4]} | **Amount: RS {b[5]}/-**")
            with col_b2:
                if st.button("🗑️ Delete Bill", key=f"del_bill_{b[0]}"):
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE receipts SET bill_no=NULL WHERE bill_no=?", (b[1],))
                    cursor.execute("DELETE FROM bills WHERE id=?", (b[0],))
                    conn.commit()
                    conn.close()
                    st.success(f"બિલ નંબર {b[1]} સફળતાપૂર્વક ડિલીટ થઈ ગયું છે!")
                    st.rerun()
    else:
        st.info("હજુ સુધી કોઈ બિલ જનરેટ થયેલ નથી.")

# ----------------- ૫. PARTY PAYMENT RECEIVE -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)":
    st.subheader("💳 Party Payment Receive & WhatsApp Receipt")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name, mobile FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    p_list = [r[0] for r in p_data]
    
    cursor.execute("SELECT bill_no, party_name, total_amount FROM bills ORDER BY id DESC")
    b_list = cursor.fetchall()
    conn.close()

    bill_options = ["-- Select Bill No (બિલ નં પસંદ કરો) --"] + [f"{b[0]} | {b[1]} | RS {b[2]}/-" for b in b_list]

    if not p_list:
        st.warning("⚠️ પહેલા મેનુમાંથી 'Add Account Party' પસંદ કરીને પાર્ટી ઉમેરો!")
    else:
        with st.form("payment_form", clear_on_submit=False):
            selected_bill_opt = st.selectbox("Select Pending Bill No:", bill_options)
            pay_party = st.selectbox("Select Party Name:", p_list)
            pay_date = st.text_input("Payment Date:", value=today.strftime("%d/%m/%Y"))
            pay_amount = st.text_input("Payment Amount (RS):")
            pay_mode = st.selectbox("Payment Mode:", ["Cash (રોકડ)", "UPI (ગૂગલપે/ફોનપે)", "Cheque (ચેક)"])
            pay_note = st.text_input("Note / Reference:")
            pay_mob = st.text_input("WhatsApp Mobile No:")
            
            submit_pay = st.form_submit_button("💾 Save Payment (પેમેન્ટ સેવ કરો)", type="primary")

        if submit_pay:
            if not pay_amount.strip():
                st.error("મહેરબાની કરીને રકમ ભરો!")
            else:
                target_bill_no = selected_bill_opt.split(" | ")[0] if "-- Select" not in selected_bill_opt else "DIRECT"
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO party_payments (party_name, bill_no, date, amount, pay_mode, note) VALUES (?, ?, ?, ?, ?, ?)",
                              (pay_party.strip(), target_bill_no, pay_date.strip(), pay_amount.strip(), pay_mode, pay_note.strip()))
                rec_last_id = cursor.lastrowid
                conn.commit()
                conn.close()

                st.success(f"✅ પાર્ટી '{pay_party}' ના RS {pay_amount}/- જમા થઈ ગયા છે!")

                pay_pdf_bytes = generate_payment_pdf_receipt(rec_last_id, pay_party.strip(), target_bill_no, pay_date.strip(), pay_amount.strip(), pay_mode, pay_note.strip())
                st.download_button(label="📄 Step 1: Download Payment Receipt PDF", data=pay_pdf_bytes, file_name=f"Payment_Receipt_REC{rec_last_id:04d}_{pay_party}.pdf", mime="application/pdf")

                # 📲 WHATSAPP PAYMENT RECEIPT
                if pay_mob.strip():
                    wa_pay_msg = (
                        "💳 PAYMENT RECEIPT ACKNOWLEDGEMENT\n\n"
                        f"Received From: {pay_party}\n"
                        f"Receipt No: PAY-REC-{rec_last_id:04d}\n"
                        f"Against Bill: {target_bill_no}\n"
                        f"Amount Received: RS {pay_amount}/-\n"
                        f"Payment Mode: {pay_mode}\n"
                        f"Date: {pay_date}\n\n"
                        "Thank you for payment! - Courier Solution"
                    )
                    wa_pay_url = create_whatsapp_link(pay_mob.strip(), wa_pay_msg)
                    st.markdown(f'<a href="{wa_pay_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Step 2: Send Payment Receipt on WhatsApp</a>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📜 Party Payment History & Delete")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, bill_no, date, amount, pay_mode, note FROM party_payments ORDER BY id DESC")
    pay_rows = cursor.fetchall()
    conn.close()

    if pay_rows:
        pay_summary_pdf_bytes = generate_payments_summary_pdf(pay_rows, f"{start_str} to {end_str}")
        st.download_button(
            label="🖨️ Download Payment Received Summary (PDF)",
            data=pay_summary_pdf_bytes,
            file_name=f"Payment_Summary_Report_{start_str}_to_{end_str}.pdf",
            mime="application/pdf",
            type="primary"
        )
        st.write("")

        tot_received = 0
        for r in pay_rows:
            col_py1, col_py2, col_py3 = st.columns([3, 1.2, 1])
            with col_py1:
                st.write(f"🏢 **{r[1]}** | Bill: **{r[2]}** | Date: {r[3]} | **RS {r[4]}** ({r[5]})")
                try: tot_received += float(r[4])
                except: pass
            with col_py2:
                hist_pdf = generate_payment_pdf_receipt(r[0], r[1], r[2], r[3], r[4], r[5], r[6])
                st.download_button("🖨️ Receipt PDF", data=hist_pdf, file_name=f"Payment_Receipt_{r[0]}.pdf", mime="application/pdf", key=f"pdf_pay_{r[0]}")
            with col_py3:
                if st.button("🗑️ Delete Pay", key=f"del_pay_{r[0]}"):
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM party_payments WHERE id=?", (r[0],))
                    conn.commit()
                    conn.close()
                    st.success("પેમેન્ટ એન્ટ્રી સફળતાપૂર્વક ડિલીટ થઈ ગઈ છે!")
                    st.rerun()
        st.metric("💰 Total Payment Received", f"RS {tot_received:,.2f}/-")
    else:
        st.info("કોઈ પેમેન્ટ રિસીવ રેકોર્ડ મળેલ નથી.")

