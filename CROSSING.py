import streamlit as st
import sqlite3
import psycopg2
import datetime
import io
import urllib.parse
import re
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import code128, qr

# Optional AI / OCR Scanner Libraries
try:
    import cv2
    import numpy as np
    from pyzbar.pyzbar import decode
    import pytesseract
    SCANNER_AVAILABLE = True
except ImportError:
    SCANNER_AVAILABLE = False

# Page Configuration
st.set_page_config(page_title="Courier Solution", page_icon="📦", layout="centered")

# ----------------- 🔄 ક્લાઉડ સુપાબેઝ હાઇબ્રિડ ડેટાબેઝ સેટઅપ -----------------
LOCAL_DB = "courier_database.db"

def get_local_connection():
    return sqlite3.connect(LOCAL_DB, check_same_thread=False)

def get_supabase_connection():
    try:
        if "postgres" in st.secrets:
            db_url = st.secrets["postgres"]["url"]
            conn = psycopg2.connect(db_url)
            return conn
    except Exception:
        return None
    return None

def init_db():
    # લોકલ ડેટાબેઝ ઇનિશિયલાઈઝેશન
    conn = get_local_connection()
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
            bill_no TEXT,
            parcel_img BLOB,
            payment_status TEXT DEFAULT 'Unpaid'
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE receipts ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")
        conn.commit()
    except Exception:
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

    # સુપાબેઝ ક્લાઉડ ટેબલ ક્રિએશન અને ડેટા સિંક
    sconn = get_supabase_connection()
    if sconn:
        try:
            scur = sconn.cursor()
            scur.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id SERIAL PRIMARY KEY,
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
                    bill_no TEXT,
                    payment_status TEXT DEFAULT 'Unpaid'
                )
            """)
            scur.execute("""
                CREATE TABLE IF NOT EXISTS parties (
                    id SERIAL PRIMARY KEY,
                    party_name TEXT UNIQUE,
                    party_address TEXT,
                    party_city TEXT,
                    mobile TEXT
                )
            """)
            scur.execute("""
                CREATE TABLE IF NOT EXISTS party_payments (
                    id SERIAL PRIMARY KEY,
                    party_name TEXT,
                    bill_no TEXT,
                    date TEXT,
                    amount TEXT,
                    pay_mode TEXT,
                    note TEXT
                )
            """)
            scur.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    id SERIAL PRIMARY KEY,
                    bill_no TEXT UNIQUE,
                    party_name TEXT,
                    bill_date TEXT,
                    period TEXT,
                    total_amount TEXT
                )
            """)
            sconn.commit()
            scur.close()
            sconn.close()
        except Exception:
            pass

@st.cache_data(ttl=10)
def sync_two_way():
    sconn = get_supabase_connection()
    if not sconn:
        return
    try:
        lconn = get_local_connection()
        lcur = lconn.cursor()
        scur = sconn.cursor()

        # પાર્ટીઓ સિંક કરો
        scur.execute("SELECT party_name, party_address, party_city, mobile FROM parties")
        for row in scur.fetchall():
            lcur.execute("INSERT OR IGNORE INTO parties (party_name, party_address, party_city, mobile) VALUES (?, ?, ?, ?)", row)
        
        # રિસીપ્ટ્સ/બુકિંગ સિંક કરો
        scur.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, bill_no, payment_status FROM receipts")
        for row in scur.fetchall():
            lcur.execute("INSERT OR IGNORE INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, bill_no, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)

        lconn.commit()
        scur.close()
        sconn.close()
        lconn.close()
    except Exception:
        pass

init_db()
if 'synced' not in st.session_state:
    sync_two_way()
    st.session_state['synced'] = True

# Helper function to save to both Local and Supabase Cloud (દૂર કરેલ એરર સાથે સુધારેલું ફંક્શન)
def save_receipt_to_cloud_and_local(data_tuple, img_bytes):
    # Local Save
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple + (img_bytes,))
    conn.commit()
    conn.close()

    # Supabase Cloud Save
    sconn = get_supabase_connection()
    if sconn:
        try:
            scur = sconn.cursor()
            scur.execute("""
                INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, bill_no, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cons_no) DO NOTHING
            """, data_tuple[:16] + (None, data_tuple[17]))
            sconn.commit()
            scur.close()
            sconn.close()
        except Exception:
            pass

# ----------------- AI PHOTO AUTO-FILL SCANNER FUNCTION -----------------
def scan_label_image(image_bytes):
    extracted_cons_no = ""
    extracted_pincode = ""
    if not SCANNER_AVAILABLE:
        return extracted_cons_no, extracted_pincode
    try:
        image = Image.open(io.BytesIO(image_bytes))
        img_np = np.array(image)
        barcodes = decode(img_np)
        for barcode in barcodes:
            extracted_cons_no = barcode.data.decode('utf-8')
            break
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
        pincodes = re.findall(r'\b[1-9][0-9]{5}\b', text)
        if pincodes:
            extracted_pincode = pincodes[-1]
    except Exception:
        pass
    return extracted_cons_no, extracted_pincode

# ----------------- WHATSAPP LINK GENERATOR FUNCTION -----------------
def create_whatsapp_link(phone_num, msg_text):
    clean_phone = ''.join(filter(str.isdigit, str(phone_num)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_text = urllib.parse.quote(msg_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

# ----------------- PDF RECEIPT GENERATOR WITH LARGE PARCEL PHOTO -----------------
def generate_hd_receipt_pdf(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, img_bytes=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    f_header_title = ParagraphStyle('HTitle', fontName='Helvetica-Bold', fontSize=26, leading=30, textColor=colors.HexColor('#002147'))
    f_header_sub = ParagraphStyle('HSub', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#333333'))
    f_label_sm = ParagraphStyle('LblSm', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.black)
    f_val_lg = ParagraphStyle('ValLg', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.black)
    f_val_huge = ParagraphStyle('ValHuge', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.black)
    f_val_blue = ParagraphStyle('ValBlue', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.blue)
    f_val_green = ParagraphStyle('ValGreen', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#008000'))
    f_footer = ParagraphStyle('Foot', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#444444'))
    barcode_obj = code128.Code128(cons_no, barHeight=35, barWidth=1.5)
    
    header_data = [
        [Paragraph("📦 <b>COURIER SOLUTION</b>", f_header_title), Paragraph("Consignment Number", f_label_sm)],
        [Paragraph("<b>EXPRESS CARGO & LOGISTICS SERVICES</b>", f_header_sub), barcode_obj],
        ["", Paragraph(f"<b>{cons_no}</b>", f_val_lg)]
    ]
    t_header = Table(header_data, colWidths=[335, 210])
    t_header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('LINEBEFORE', (1,0), (1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    row2_data = [[
        Paragraph(f"<b>Origin:</b> <font size=13 color='#002147'>{origin.upper()}</font><br/><b>Courier:</b> <font color='blue'>{courier_co.upper()}</font>", f_val_lg),
        Paragraph(f"<b>Destination:</b><br/><font size=16>{dest.upper()}</font>", f_val_huge),
        Paragraph(f"<b>Date:</b> {date}<br/><b>Booking:</b> {booking_type}", f_val_lg)
    ]]
    t_row2 = Table(row2_data, colWidths=[175, 200, 170])
    t_row2.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    row3_data = [
        [Paragraph("CONSIGNOR (FROM)", f_val_lg), Paragraph("CONSIGNEE (TO)", f_val_lg)],
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
        [Paragraph("Pieces (Pcs)", f_label_sm), Paragraph("Weight (Kg)", f_label_sm), Paragraph("Total Amount (RS)", f_label_sm), Paragraph("Payment Status", f_label_sm)],
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
    story.append(t_header)
    story.append(Spacer(1, 6))
    story.append(t_row2)
    story.append(Spacer(1, 6))
    story.append(t_row3)
    story.append(Spacer(1, 6))
    story.append(t_row4)
    story.append(Spacer(1, 10))
    if img_bytes:
        try:
            img_io = io.BytesIO(img_bytes)
            large_photo = RLImage(img_io, width=220, height=150)
            photo_table = Table([[large_photo]], colWidths=[545])
            photo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(photo_table)
            story.append(Spacer(1, 10))
        except Exception:
            pass
    foot_data = [[
        Paragraph("<b>Shipment Remarks:</b> Booking Generated via Courier Solution.<br/><i>* Parcel Proof Photo attached above. Subject to terms.</i>", f_footer),
        Paragraph("________________________<br/><b>Authorized Signatory</b><br/>(Courier Solution)", f_val_lg)
    ]]
    t_foot = Table(foot_data, colWidths=[335, 210])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_foot)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- SUMMARY PDF REPORT GENERATOR -----------------
def generate_summary_pdf_report(title_text, period_str, headers, rows, total_amt_str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black)
    
    story.append(Paragraph("📦 COURIER SOLUTION", title_style))
    story.append(Paragraph(f"<b>{title_text}</b><br/>Period: {period_str}", sub_style))
    
    table_headers = [Paragraph(f'<b>{h}</b>', bold_style) for h in headers]
    data = [table_headers]
    for r in rows:
        data.append([Paragraph(str(cell), normal_style) for cell in r])
        
    data.append([
        Paragraph("<b>TOTAL</b>", bold_style),
        "", "", "", "", "",
        Paragraph(f"<b>{total_amt_str}</b>", ParagraphStyle('GTotal', parent=bold_style, textColor=colors.HexColor('#008000')))
    ])
    
    t = Table(data, colWidths=[30, 80, 75, 85, 95, 115, 65])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('SPAN', (0, -1), (5, -1)),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- BILL PDF INVOICE GENERATOR WITH UPI -----------------
def generate_pdf_invoice(bill_no, party_name, period_str, bill_date, items, total_amount):
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
            Paragraph(f"<b>Invoice To:</b><br/><font size=11 color='#002147'><b>{party_name}</b></font><br/>Billing Period: {period_str}", normal_style),
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
    "📊 Party Monthly Billing (ડિજિટલ પીડીએફ બિલ)",
    "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)",
    "📊 Summary & Reports (કેશ & ક્રેડિટ સમરી)"
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
    st.subheader("➕ Add & Manage Monthly Account Parties")
    if 'edit_party_id' not in st.session_state:
        st.session_state['edit_party_id'] = None

    conn = get_local_connection()
    cursor = conn.cursor()
    edit_data = None
    if st.session_state['edit_party_id']:
        cursor.execute("SELECT id, party_name, party_address, party_city, mobile FROM parties WHERE id=?", (st.session_state['edit_party_id'],))
        edit_data = cursor.fetchone()

    with st.form("party_form"):
        st.write("### 📝 પાર્ટી ફોર્મ (નવી ઉમેરો અથવા એડિટ કરો)")
        p_name_val = edit_data[1] if edit_data else ""
        p_addr_val = edit_data[2] if edit_data else ""
        p_city_val = edit_data[3] if edit_data else ""
        p_mob_val = edit_data[4] if edit_data else ""

        p_name = st.text_input("Party Name (પાર્ટીનું નામ):", value=p_name_val)
        p_addr = st.text_input("Address (સરનામું):", value=p_addr_val)
        p_city = st.text_input("City / Pin Code (શહેર / પીનકોડ):", value=p_city_val)
        p_mob = st.text_input("WhatsApp Mobile No (મોબાઈલ નંબર):", value=p_mob_val)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            submit_p = st.form_submit_button("💾 Save Party", type="primary")
        with col_f2:
            cancel_edit = st.form_submit_button("❌ Cancel Edit")

        if cancel_edit:
            st.session_state['edit_party_id'] = None
            st.rerun()

        if submit_p:
            if not p_name.strip():
                st.error("મહેરબાની કરીને Party Name ભરો!")
            else:
                try:
                    if st.session_state['edit_party_id']:
                        cursor.execute("UPDATE parties SET party_name=?, party_address=?, party_city=?, mobile=? WHERE id=?", 
                                      (p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip(), st.session_state['edit_party_id']))
                        conn.commit()
                        st.session_state['edit_party_id'] = None
                    else:
                        cursor.execute("INSERT INTO parties (party_name, party_address, party_city, mobile) VALUES (?, ?, ?, ?)", 
                                      (p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip()))
                        conn.commit()
                    
                    # Supabase Cloud Sync Save
                    sconn = get_supabase_connection()
                    if sconn:
                        try:
                            scur = sconn.cursor()
                            scur.execute("""
                                INSERT INTO parties (party_name, party_address, party_city, mobile)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (party_name) DO UPDATE SET party_address = EXCLUDED.party_address, party_city = EXCLUDED.party_city, mobile = EXCLUDED.mobile
                            """, (p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip()))
                            sconn.commit()
                            scur.close()
                            sconn.close()
                        except Exception:
                            pass

                    st.success(f"પાર્ટી '{p_name}' સફળતાપૂર્વક સેવ થઈ ગઈ છે!")
                    sync_two_way()
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("આ નામની પાર્ટી પહેલેથી જ અસ્તિત્વમાં છે!")
    conn.close()

    st.markdown("---")
    st.write("### 🏢 સેવ થયેલી પાર્ટીઓની યાદી (Table View):")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
    p_rows = cursor.fetchall()
    conn.close()
    
    if p_rows:
        header_cols = st.columns([0.5, 2.5, 2.5, 1.5, 1, 1])
        header_cols[0].write("<b>ક્રમ</b>", unsafe_allow_html=True)
        header_cols[1].write("<b>પાર્ટીનું નામ</b>", unsafe_allow_html=True)
        header_cols[2].write("<b>સરનામું / શહેર</b>", unsafe_allow_html=True)
        header_cols[3].write("<b>મોબાઈલ નંબર</b>", unsafe_allow_html=True)
        header_cols[4].write("<b>એડિટ</b>", unsafe_allow_html=True)
        header_cols[5].write("<b>ડિલીટ</b>", unsafe_allow_html=True)
        st.markdown("---")

        for idx, r in enumerate(p_rows, 1):
            r_id, r_name, r_addr, r_city, r_mob = r
            row_cols = st.columns([0.5, 2.5, 2.5, 1.5, 1, 1])
            row_cols[0].write(str(idx))
            row_cols[1].write(f"**{r_name}**")
            row_cols[2].write(f"{r_addr}, {r_city}")
            row_cols[3].write(r_mob if r_mob else "-")
            
            with row_cols[4]:
                if st.button("✏️ Edit", key=f"edit_party_{r_id}"):
                    st.session_state['edit_party_id'] = r_id
                    st.rerun()
            with row_cols[5]:
                if st.button("🗑️ Delete", key=f"del_party_{r_id}"):
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM parties WHERE id=?", (r_id,))
                    conn.commit()
                    conn.close()

                    sconn = get_supabase_connection()
                    if sconn:
                        try:
                            scur = sconn.cursor()
                            scur.execute("DELETE FROM parties WHERE party_name=%s", (r_name,))
                            sconn.commit()
                            scur.close()
                            sconn.close()
                        except Exception: pass

                    st.success(f"પાર્ટી '{r_name}' ડિલીટ થઈ ગઈ છે!")
                    st.rerun()
    else:
        st.info("હજુ સુધી કોઈ પાર્ટી ઉમેરેલી નથી.")

# ----------------- ૨. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)":
    tab1, tab2, tab3 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History & Date Filter (હિસ્ટ્રી & ટોટલ)", "🖨️ Re-Print Receipt (ફરીવાર પ્રિન્ટ)"])
    with tab1:
        st.subheader("Cash Courier Booking")
        st.markdown("### 📷 Auto-Scan Label (સ્માર્ટ ફોટો સ્કેનર - બારકોડ & પિનકોડ ઓટો-ફિલ)")
        uploaded_photo = st.file_uploader("પાર્સલ/લેબલનો ફોટો લો અથવા અપલોડ કરો:", type=["jpg", "jpeg", "png"], key="c_photo")
        auto_cons = ""
        auto_pin = ""
        if uploaded_photo:
            img_bytes_temp = uploaded_photo.getvalue()
            auto_cons, auto_pin = scan_label_image(img_bytes_temp)
            if auto_cons or auto_pin:
                st.success(f"🎯 સ્કેન સફળ! બારકોડ: {auto_cons} | પિનકોડ: {auto_pin}")

        col1, col2 = st.columns(2)
        with col1:
            cons_no = st.text_input("Consignment No:", value=auto_cons, key="c_cons")
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
            rec_city = st.text_input("Recipient City/Pin:", value=auto_pin, key="c_r_city")

        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="c_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="c_pcs")
        with col5: amount = st.text_input("Total Amount (RS):", key="c_amt")
        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No (મોબાઈલ નંબર):", key="c_wa_num")
        c_initial_pay_status = st.selectbox("Payment Status (પેમેન્ટ સ્ટેટસ):", ["Paid (ચૂકવાઈ ગયું)", "Unpaid (બાકી)"], key="c_init_status")

        if st.button("💾 Save & Generate Cash Receipt", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("મહેરબાની કરીને Consignment No, Sender Name, Recipient Name અને Amount ભરો!")
            else:
                img_bytes = uploaded_photo.getvalue() if uploaded_photo else None
                status_val = "Paid" if "Paid" in c_initial_pay_status else "Unpaid"
                
                data_tuple = (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Cash', None, status_val)
                
                try:
                    save_receipt_to_cloud_and_local(data_tuple, img_bytes)
                    st.success(f"Cash Entry Saved Successfully for Consignment: {cons_no} [{status_val}]")
                    sync_two_way()
                    
                    pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash', img_bytes)
                    st.download_button(label="📄 Step 1: Download Printable PDF Receipt", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")
                    
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
                            f"Amount: RS {amount}/- [{status_val}]\n\n"
                            "Thank you for choosing Courier Solution!"
                        )
                        wa_url = create_whatsapp_link(c_whatsapp_num.strip(), wa_msg)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Step 2: Send Confirmation on WhatsApp</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"એન્ટ્રી સેવ કરતી વખતે ભૂલ આવી: {e}")

    with tab2:
        st.subheader("📜 Cash Booking Records & Date-Wise Total Summary")
        st.info(f"📅 કેશ હિસ્ટ્રી ડેટ ફિલ્ટર: **{start_str}** થી **{end_str}**")
        
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, amount, payment_status FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        cash_rows = cursor.fetchall()
        conn.close()
        
        filtered_cash_history = []
        tot_c_amt = 0.0
        tot_c_paid = 0.0
        tot_c_unpaid = 0.0
        
        for r in cash_rows:
            try:
                r_dt = datetime.datetime.strptime(r[2], "%d/%m/%Y").date()
                if start_date <= r_dt <= end_date:
                    filtered_cash_history.append(r)
                    amt_v = float(r[5]) if r[5] else 0.0
                    tot_c_amt += amt_v
                    if r[6] == "Paid":
                        tot_c_paid += amt_v
                    else:
                        tot_c_unpaid += amt_v
            except Exception:
                pass
                
        st.markdown("---")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("📦 કુલ કેશ બુકિંગ રકમ", f"RS {tot_c_amt:,.2f}/-")
        mc2.metric("🟢 કુલ Paid (ચૂકવાઈ ગયેલ)", f"RS {tot_c_paid:,.2f}/-")
        mc3.metric("🔴 કુલ Unpaid (બાકી)", f"RS {tot_c_unpaid:,.2f}/-")
        st.markdown("---")
        
        if filtered_cash_history:
            for idx, r in enumerate(filtered_cash_history, 1):
                r_id, cons, r_date, s_name, r_name, amt, p_status = r
                cur_status_str = f"🟢 PAID" if p_status == "Paid" else f"🔴 UNPAID"
                
                with st.expander(f"[{idx}] Cons: {cons} | Date: {r_date} | From: {s_name} ➔ To: {r_name} | RS {amt}/- | Status: {cur_status_str}"):
                    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 1.2, 1.2, 1])
                    with col_h1:
                        st.write(f"**Date:** {r_date} | **Amount:** RS {amt}/-")
                        st.write(f"**Current Payment:** {cur_status_str}")
                    with col_h2:
                        if st.button("🟢 Mark Paid", key=f"mark_paid_{r_id}"):
                            conn = get_local_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE receipts SET payment_status='Paid' WHERE id=?", (r_id,))
                            conn.commit()
                            conn.close()
                            sync_two_way()
                            st.success(f"Consignment {cons} નો Status 'Paid' કરી દીધો છે!")
                            st.rerun()
                    with col_h3:
                        if st.button("🔴 Mark Unpaid", key=f"mark_unpaid_{r_id}"):
                            conn = get_local_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE receipts SET payment_status='Unpaid' WHERE id=?", (r_id,))
                            conn.commit()
                            conn.close()
                            sync_two_way()
                            st.warning(f"Consignment {cons} નો Status 'Unpaid' કરી દીધો છે!")
                            st.rerun()
                    with col_h4:
                        if st.button("🗑️ Delete", key=f"del_cash_{r_id}"):
                            conn = get_local_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM receipts WHERE id=?", (r_id,))
                            conn.commit()
                            conn.close()

                            sconn = get_supabase_connection()
                            if sconn:
                                try:
                                    scur = sconn.cursor()
                                    scur.execute("DELETE FROM receipts WHERE cons_no=%s", (cons,))
                                    sconn.commit()
                                    scur.close()
                                    sconn.close()
                                except Exception: pass

                            st.success(f"Consignment {cons} ડિલીટ થઈ ગયું છે!")
                            st.rerun()
        else:
            st.warning("આ તારીખની મર્યાદામાં કોઈ કેશ બુકિંગ એન્ટ્રી મળી નથી.")

    with tab3:
        st.subheader("🖨️ Re-Print / View Receipt by Consignment No")
        search_cons = st.text_input("Enter Consignment No to Print:")
        if st.button("🔍 Search & Print Receipt", type="primary"):
            if search_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img FROM receipts WHERE cons_no=?", (search_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ સફળતાપૂર્વક મળી ગઈ છે!")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], rec_data[16])
                    st.download_button(label="🖨️ Download Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{rec_data[0]}.pdf", mime="application/pdf")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૩. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    tab_cr1, tab_cr2, tab_cr3 = st.tabs(["📋 Credit Booking (નવી એન્ટ્રી)", "🖨️ Re-Print Credit Receipt", "📜 Credit History & View (હિસ્ટ્રી & સુધારો)"])
    with tab_cr1:
        st.subheader("Credit Account Courier Booking")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
        parties_data = cursor.fetchall()
        conn.close()
        
        party_dict = {r[0]: {"address": r[1], "city": r[2], "mobile": r[3]} for r in parties_data}
        party_names = list(party_dict.keys())

        if not party_names:
            st.warning("⚠️ પહેલા 'Add Account Party' પસંદ કરીને પાર્ટી ઉમેરો!")
        else:
            selected_party = st.selectbox("Select Party Name (પાર્ટી સિલેક્ટ કરો):", party_names)
            default_s_addr = party_dict[selected_party]["address"] if selected_party in party_dict else ""
            default_s_city = party_dict[selected_party]["city"] if selected_party in party_dict else ""

            cr_uploaded_photo = st.file_uploader("📷 Auto-Scan Parcel Photo (બારકોડ & પિનકોડ ઓટો-ફિલ):", type=["jpg", "jpeg", "png"], key="cr_photo")
            cr_auto_cons = ""
            cr_auto_pin = ""
            if cr_uploaded_photo:
                cr_auto_cons, cr_auto_pin = scan_label_image(cr_uploaded_photo.getvalue())
            
            col1, col2 = st.columns(2)
            with col1:
                cons_no = st.text_input("Consignment No:", value=cr_auto_cons, key="cr_cons")
                date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="cr_date")
                courier_co = st.text_input("Courier Company:", "DTDC", key="cr_co")
                mode = st.text_input("Service Mode:", "Surface", key="cr_mode")
                origin = st.text_input("Origin:", "BHAVNAGAR", key="cr_orig")
                dest = st.text_input("Destination:", key="cr_dest")
            with col2:
                sender_address = st.text_input("Sender Address (મોકલનારનું સરનામું):", value=default_s_addr, key=f"cr_s_addr_{selected_party}")
                sender_city = st.text_input("Sender City/Pin (શહેર/પીન):", value=default_s_city, key=f"cr_s_city_{selected_party}")
                rec_name = st.text_input("Recipient Name:", key="cr_r_name")
                rec_address = st.text_input("Recipient Address:", key="cr_r_addr")
                rec_city = st.text_input("Recipient City/Pin:", value=cr_auto_pin, key="cr_r_city")
            
            col3, col4, col5 = st.columns(3)
            with col3: weight = st.text_input("Weight (Kg):", "1.0", key="cr_wt")
            with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="cr_pcs")
            with col5: amount = st.text_input("Amount (RS):", key="cr_amt")
            
            if st.button("💾 Save & Print Credit Booking", type="primary"):
                if not cons_no or not rec_name or not amount:
                    st.error("મહેરબાની કરીને બધી માહિતી ભરો!")
                else:
                    cr_img_bytes = cr_uploaded_photo.getvalue() if cr_uploaded_photo else None
                    data_tuple = (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Credit Account', None, 'Unpaid')
                    try:
                        save_receipt_to_cloud_and_local(data_tuple, cr_img_bytes)
                        st.success(f"Credit Entry Saved for '{selected_party}'")
                        sync_two_way()

                        pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account', cr_img_bytes)
                        st.download_button(label="🖨️ Download Credit Receipt PDF", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")
                    except Exception as e:
                        st.error(f"એન્ટ્રી સેવ કરતી વખતે ભૂલ આવી: {e}")

    with tab_cr2:
        st.subheader("🖨️ Re-Print Credit Receipt by Consignment No")
        search_cr_cons = st.text_input("Enter Consignment No to Print (કન્સાઇનમેન્ટ નંબર નાખો):", key="search_cr")
        if st.button("🔍 Search & Print Credit Receipt", type="primary"):
            if search_cr_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img FROM receipts WHERE cons_no=?", (search_cr_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ સફળતાપૂર્વક મળી ગઈ છે!")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], rec_data[16])
                    st.download_button(label="🖨️ Download HD Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{search_cr_cons}.pdf", mime="application/pdf")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

    with tab_cr3:
        st.subheader("📜 View Credit Account Bookings & Edit/Delete")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, dest, weight, amount, bill_no, courier_co, mode, origin, sender_address, sender_city, rec_address, rec_city, pcs, parcel_img FROM receipts WHERE booking_type='Credit Account' ORDER BY id DESC")
        cr_all_rows = cursor.fetchall()
        conn.close()
        if cr_all_rows:
            for idx, r in enumerate(cr_all_rows, 1):
                rec_id, cons, r_date, party, recip, destination, wt, amt, b_no, c_co, c_mode, orig, s_addr, s_city, r_addr, r_city, pcs, p_img = r
                b_status = f" (Bill: {b_no})" if b_no else " (Unbilled)"
                with st.expander(f"[{idx}] Cons: {cons} | Party: {party} | Date: {r_date} | RS {amt}/-{b_status}"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.write(f"**Recipient:** {recip} ({destination})")
                        st.write(f"**Courier:** {c_co} | **Mode:** {c_mode}")
                        st.write(f"**Weight:** {wt} Kg | **Pieces:** {pcs}")
                    with col_e2:
                        pdf_b = generate_hd_receipt_pdf(cons, r_date, c_co, c_mode, orig, destination, party, s_addr, s_city, recip, r_addr, r_city, wt, pcs, amt, 'Credit Account', p_img)
                        st.download_button("🖨️ Download Receipt PDF", data=pdf_b, file_name=f"Receipt_{cons}.pdf", mime="application/pdf", key=f"dl_pdf_{rec_id}")
                    if st.button(f"🗑️ Delete Entry ({cons})", key=f"del_cr_{rec_id}"):
                        conn = get_local_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM receipts WHERE id=?", (rec_id,))
                        conn.commit()
                        conn.close()

                        sconn = get_supabase_connection()
                        if sconn:
                            try:
                                scur = sconn.cursor()
                                scur.execute("DELETE FROM receipts WHERE cons_no=%s", (cons,))
                                sconn.commit()
                                scur.close()
                                sconn.close()
                            except Exception: pass

                        st.success(f"Consignment {cons} સફળતાપૂર્વક ડિલીટ થઈ ગયું છે!")
                        st.rerun()

# ----------------- ૪. DIGITAL MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ પીડીએફ બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator & WhatsApp Share")
    st.info(f"📅 પસંદ કરેલ બિલિંગ સમયગાળો: **{start_str}** થી **{end_str}**")
    conn = get_local_connection()
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
                conn = get_local_connection()
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
                        except Exception: pass
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
                sync_two_way()
                st.success(f"✅ કુલ {success_count} પાર્ટીઓ માટે નવા બિલ સફળતાપૂર્વક જનરેટ થઈ ગયા છે!")
                st.rerun()
        else:
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT bill_no, bill_date, total_amount FROM bills WHERE party_name=? AND period=?", (sel_party, f"{start_str} to {end_str}"))
            existing_bill = cursor.fetchone()
            conn.close()
            if existing_bill:
                st.warning(f"⚠️ આ પાર્ટી ('{sel_party}') માટે આ સમયગાળાનું બિલ પહેલેથી જ જનરેટ થઈ ગયેલ છે!")
                st.info(f"બિલ નંબર: **{existing_bill[0]}** | તારીખ: {existing_bill[1]} | કુલ રકમ: RS {existing_bill[2]}/-")
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
                conn_temp = get_local_connection()
                cur_temp = conn_temp.cursor()
                cur_temp.execute("SELECT COUNT(*) FROM bills")
                b_count = cur_temp.fetchone()[0] + 1
                conn_temp.close()
                generated_bill_no = f"BILL-2026-{b_count:03d}"
                if st.button("📄 Generate & Create Digital PDF Invoice", type="primary"):
                    conn = get_local_connection()
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
                        except Exception: pass
                    if filtered_bill:
                        cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                                      (generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                        for item in filtered_bill:
                            cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                        conn.commit()
                        conn.close()
                        sync_two_way()

                        pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, f"{start_str} to {end_str}", today.strftime("%d/%m/%Y"), filtered_bill, tot_bill)
                        st.success(f"✅ પાર્ટી '{sel_party}' નું બિલ સફળતાપૂર્વક જનરેટ થઈ ગયું છે!")
                        st.download_button(label="📄 Step 1: Download Digital Invoice PDF", data=pdf_bytes, file_name=f"Invoice_{generated_bill_no}_{sel_party}.pdf", mime="application/pdf")
                    else:
                        conn.close()
                        st.info("કોઈ અનબિલ એન્ટ્રી મળી નથી.")

    st.markdown("---")
    st.subheader("📜 Generated Bills History & Delete")
    conn = get_local_connection()
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
        for idx, b in enumerate(all_bills, 1):
            bill_id, b_no, b_party, b_date, b_period, b_amt = b
            with st.expander(f"[{idx}] Bill No: {b_no} | Party: {b_party} | Amount: RS {b_amt}/- ({b_date})"):
                col_b1, col_b2, col_b3 = st.columns([2, 2, 1])
                conn_b = get_local_connection()
                cur_b = conn_b.cursor()
                cur_b.execute("SELECT id, cons_no, date, courier_co, dest, rec_name, weight, amount FROM receipts WHERE bill_no=?", (b_no,))
                items_for_b = cur_b.fetchall()
                cur_b.execute("SELECT mobile FROM parties WHERE party_name=?", (b_party,))
                party_m_row = cur_b.fetchone()
                p_mob_num = party_m_row[0] if party_m_row and party_m_row[0] else ""
                conn_b.close()
                with col_b1:
                    try:
                        b_pdf_bytes = generate_pdf_invoice(b_no, b_party, b_period, b_date, items_for_b, float(b_amt))
                        st.download_button("🖨️ Download Invoice PDF", data=b_pdf_bytes, file_name=f"Invoice_{b_no}_{b_party}.pdf", mime="application/pdf", key=f"dl_inv_{bill_id}")
                    except Exception:
                        st.write("PDF Error")
                with col_b2:
                    if p_mob_num:
                        wa_b_msg = (
                            "🧾 COURIER SOLUTION TAX INVOICE\n\n"
                            f"To: {b_party}\n"
                            f"Invoice No: {b_no}\n"
                            f"Period: {b_period}\n"
                            f"Total Bill Amount: RS {b_amt}/-\n\n"
                            "Pay via Google Pay/UPI: 7043721851@yapl\n\n"
                            "Thank you for business with Courier Solution!"
                        )
                        wa_b_url = create_whatsapp_link(p_mob_num, wa_b_msg)
                        st.markdown(f'<a href="{wa_b_url}" target="_blank" style="background-color:#25D366;color:white;padding:6px 12px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;">📲 WhatsApp Share</a>', unsafe_allow_html=True)
                with col_b3:
                    if st.button("🗑️ Delete Bill", key=f"del_bill_{bill_id}"):
                        conn = get_local_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE receipts SET bill_no=NULL WHERE bill_no=?", (b_no,))
                        cursor.execute("DELETE FROM bills WHERE id=?", (bill_id,))
                        conn.commit()
                        conn.close()

                        sconn = get_supabase_connection()
                        if sconn:
                            try:
                                scur = sconn.cursor()
                                scur.execute("UPDATE receipts SET bill_no=NULL WHERE bill_no=%s", (b_no,))
                                scur.execute("DELETE FROM bills WHERE bill_no=%s", (b_no,))
                                sconn.commit()
                                scur.close()
                                sconn.close()
                            except Exception: pass

                        st.success(f"બિલ નંબર {b_no} સફળતાપૂર્વક ડિલીટ થઈ ગયું છે!")
                        st.rerun()
    else:
        st.info("હજુ સુધી કોઈ બિલ જનરેટ થયેલ નથી.")

# ----------------- ૫. PARTY PAYMENT RECEIVE -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)":
    st.subheader("💳 Party Payment Receive & WhatsApp Receipt")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT party_name, mobile FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    cursor.execute("SELECT bill_no, party_name, total_amount FROM bills ORDER BY id DESC")
    b_list = cursor.fetchall()
    conn.close()
    bill_options = ["-- Select Bill No (બિલ નં પસંદ કરો) --"] + [f"{b[0]} | {b[1]} | RS {b[2]}/-" for b in b_list]
    p_list = [r[0] for r in p_data]
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
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO party_payments (party_name, bill_no, date, amount, pay_mode, note) VALUES (?, ?, ?, ?, ?, ?)",
                              (pay_party.strip(), target_bill_no, pay_date.strip(), pay_amount.strip(), pay_mode, pay_note.strip()))
                rec_last_id = cursor.lastrowid
                conn.commit()
                conn.close()
                sync_two_way()

                st.success(f"✅ પાર્ટી '{pay_party}' ના RS {pay_amount}/- જમા થઈ ગયા છે!")
                pay_pdf_bytes = generate_payment_pdf_receipt(rec_last_id, pay_party.strip(), target_bill_no, pay_date.strip(), pay_amount.strip(), pay_mode, pay_note.strip())
                st.download_button(label="📄 Step 1: Download Payment Receipt PDF", data=pay_pdf_bytes, file_name=f"Payment_Receipt_REC{rec_last_id:04d}_{pay_party}.pdf", mime="application/pdf")
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
    conn = get_local_connection()
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
        for idx, r in enumerate(pay_rows, 1):
            col_py1, col_py2, col_py3 = st.columns([3, 1.2, 1])
            with col_py1:
                st.write(f"[{idx}] 🏢 **{r[1]}** | Bill: **{r[2]}** | Date: {r[3]} | **RS {r[4]}** ({r[5]})")
                try: tot_received += float(r[4])
                except Exception: pass
            with col_py2:
                hist_pdf = generate_payment_pdf_receipt(r[0], r[1], r[2], r[3], r[4], r[5], r[6])
                st.download_button("🖨️ Receipt PDF", data=hist_pdf, file_name=f"Payment_Receipt_{r[0]}.pdf", mime="application/pdf", key=f"pdf_pay_{r[0]}")
            with col_py3:
                if st.button("🗑️ Delete Pay", key=f"del_pay_{r[0]}"):
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM party_payments WHERE id=?", (r[0],))
                    conn.commit()
                    conn.close()

                    sconn = get_supabase_connection()
                    if sconn:
                        try:
                            scur = sconn.cursor()
                            scur.execute("DELETE FROM party_payments WHERE party_name=%s AND amount=%s AND date=%s", (r[1], r[4], r[3]))
                            sconn.commit()
                            scur.close()
                            sconn.close()
                        except Exception: pass

                    st.success("પેમેન્ટ એન્ટ્રી સફળતાપૂર્વક ડિલીટ થઈ ગઈ છે!")
                    st.rerun()
        st.metric("💰 Total Payment Received", f"RS {tot_received:,.2f}/-")
    else:
        st.info("કોઈ પેમેન્ટ રિસીવ રેકોર્ડ મળેલ નથી.")

# ----------------- ૬. SUMMARY & REPORTS -----------------
elif menu == "📊 Summary & Reports (કેશ & ક્રેડિટ સમરી)":
    st.subheader("📊 Comprehensive Summary & Reports (કેશ અને ક્રેડિટ સમરી)")
    st.info(f"📅 ફિલ્ટર સમયગાળો (Date Range): **{start_str}** થી **{end_str}**")
    
    sum_tab1, sum_tab2 = st.tabs(["💵 Cash Booking Summary (કેશ સમરી)", "📋 Credit Account Summary (ક્રેડિટ સમરી)"])
    with sum_tab1:
        st.write("### 💵 Cash Courier Bookings Date-Wise Summary")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, courier_co, sender_name, rec_name, amount, payment_status FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        all_cash = cursor.fetchall()
        conn.close()
        
        filtered_cash = []
        tot_cash_amt = 0.0
        tot_paid_amt = 0.0
        tot_unpaid_amt = 0.0
        
        for r in all_cash:
            try:
                r_date_obj = datetime.datetime.strptime(r[2], "%d/%m/%Y").date()
                if start_date <= r_date_obj <= end_date:
                    filtered_cash.append(r)
                    amt = float(r[6]) if r[6] else 0.0
                    tot_cash_amt += amt
                    if r[7] == "Paid":
                        tot_paid_amt += amt
                    else:
                        tot_unpaid_amt += amt
            except Exception:
                pass
                
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("📦 Total Cash Booking", f"RS {tot_cash_amt:,.2f}/-")
        col_s2.metric("🟢 Total Paid (જમા)", f"RS {tot_paid_amt:,.2f}/-")
        col_s3.metric("🔴 Total Unpaid (બાકી)", f"RS {tot_unpaid_amt:,.2f}/-")
        st.markdown("---")
        
        if filtered_cash:
            pdf_rows = []
            for idx, r in enumerate(filtered_cash, 1):
                st.write(f"**{idx}. Cons:** {r[1]} | **Date:** {r[2]} | **Courier:** {r[3]} | **From:** {r[4]} ➔ **To:** {r[5]} | **RS {r[6]}** [{r[7]}]")
                pdf_rows.append([str(idx), str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5]), f"RS {float(r[6]):,.2f} ({r[7]})"])
                
            cash_sum_pdf = generate_summary_pdf_report("CASH BOOKING SUMMARY REPORT", f"{start_str} to {end_str}", ["Sr", "Cons No", "Date", "Courier", "Sender", "Recipient", "Amount / Status"], pdf_rows, f"RS {tot_cash_amt:,.2f}/- (Paid: {tot_paid_amt:,.2f} | Unpaid: {tot_unpaid_amt:,.2f})")
            st.download_button(
                label="🖨️ Download Cash Summary Report (PDF)",
                data=cash_sum_pdf,
                file_name=f"Cash_Summary_{start_str}_to_{end_str}.pdf",
                mime="application/pdf",
                type="primary"
            )
        else:
            st.warning("આ તારીખની મર્યાદામાં કોઈ કેશ બુકિંગ એન્ટ્રી મળી નથી.")
            
    with sum_tab2:
        st.write("### 📋 Credit Account Bookings Party-Wise Summary")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
        party_rows = cursor.fetchall()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, dest, amount, bill_no FROM receipts WHERE booking_type='Credit Account' ORDER BY id DESC")
        all_credit = cursor.fetchall()
        conn.close()
        
        party_names_opt = ["🌐 All Parties (બધી પાર્ટીઓ)"] + [p[0] for p in party_rows]
        sel_sum_party = st.selectbox("Select Party Filter for Summary:", party_names_opt, key="sum_party_sel")
        
        filtered_credit = []
        tot_credit_amt = 0.0
        
        for r in all_credit:
            try:
                r_date_obj = datetime.datetime.strptime(r[2], "%d/%m/%Y").date()
                if start_date <= r_date_obj <= end_date:
                    if sel_sum_party == "🌐 All Parties (બધી પાર્ટીઓ)" or r[3] == sel_sum_party:
                        filtered_credit.append(r)
                        tot_credit_amt += float(r[6]) if r[6] else 0.0
            except Exception:
                pass
                
        st.metric("📊 Total Credit Booking Amount", f"RS {tot_credit_amt:,.2f}/-")
        st.markdown("---")
        
        if filtered_credit:
            cred_pdf_rows = []
            for idx, r in enumerate(filtered_credit, 1):
                b_text = f"Bill: {r[7]}" if r[7] else "Unbilled"
                st.write(f"**{idx}. Cons:** {r[1]} | **Party:** {r[3]} | **Date:** {r[2]} | **To:** {r[4]} ({r[5]}) | **RS {r[6]}** [{b_text}]")
                cred_pdf_rows.append([str(idx), str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5]), f"RS {float(r[6]):,.2f}"])
                
            cred_sum_pdf = generate_summary_pdf_report(f"CREDIT ACCOUNT SUMMARY ({sel_sum_party})", f"{start_str} to {end_str}", ["Sr", "Cons No", "Date", "Party Name", "Recipient", "Destination", "Amount"], cred_pdf_rows, f"RS {tot_credit_amt:,.2f}/-")
            st.download_button(
                label="🖨️ Download Credit Summary Report (PDF)",
                data=cred_sum_pdf,
                file_name=f"Credit_Summary_{sel_sum_party}_{start_str}_to_{end_str}.pdf",
                mime="application/pdf",
                type="primary"
            )
        else:
            st.warning("આ ફિલ્ટર મુજબ કોઈ ક્રેડિટ બુકિંગ એન્ટ્રી મળી નથી.")
