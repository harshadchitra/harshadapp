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
            payment_status TEXT DEFAULT 'Unpaid',
            packing_info TEXT,
            packing_charge TEXT
        )
    """)
    
    for col_def in [("packing_info", "TEXT"), ("packing_charge", "TEXT"), ("payment_status", "TEXT DEFAULT 'Unpaid'")]:
        try:
            cursor.execute(f"ALTER TABLE receipts ADD COLUMN {col_def[0]} {col_def[1]}")
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
        CREATE TABLE IF NOT EXISTS couriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            courier_name TEXT UNIQUE,
            tracking_url TEXT
        )
    """)
    
    default_couriers = [
        ("DTDC", "https://www.dtdc.in/tracking/shipment-tracking.asp?strCnno="),
        ("Delhivery", "https://www.delhivery.com/track/package/"),
        ("Trackon", "https://trackon.in/track?awb=")
    ]
    for c_name, c_url in default_couriers:
        cursor.execute("INSERT OR IGNORE INTO couriers (courier_name, tracking_url) VALUES (?, ?)", (c_name, c_url))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS packing_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT UNIQUE,
            date TEXT,
            customer_name TEXT,
            mobile TEXT,
            packing_items TEXT,
            total_charge TEXT
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

init_db()

def save_receipt_to_cloud_and_local(data_tuple, img_bytes):
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img, payment_status, packing_info, packing_charge)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple + (img_bytes,))
    conn.commit()
    conn.close()

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

def create_whatsapp_link(phone_num, msg_text):
    clean_phone = ''.join(filter(str.isdigit, str(phone_num)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_text = urllib.parse.quote(msg_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

def generate_hd_receipt_pdf(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, packing_info="None", packing_charge="0", tracking_url="", img_bytes=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    f_header_title = ParagraphStyle('HTitle', fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=colors.HexColor('#002147'))
    f_header_sub = ParagraphStyle('HSub', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#333333'))
    f_label_sm = ParagraphStyle('LblSm', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black)
    f_val_lg = ParagraphStyle('ValLg', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.black)
    f_val_huge = ParagraphStyle('ValHuge', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.black)
    f_val_blue = ParagraphStyle('ValBlue', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.blue)
    f_val_green = ParagraphStyle('ValGreen', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor('#008000'))
    f_footer = ParagraphStyle('Foot', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#444444'))
    
    barcode_obj = code128.Code128(cons_no, barHeight=28, barWidth=1.4)
    
    header_data = [
        [Paragraph("📦 <b>COURIER SOLUTION</b>", f_header_title), Paragraph("Consignment Number", f_label_sm)],
        [Paragraph(f"<b>EXPRESS CARGO | Courier: <font color='blue'>{courier_co}</font></b>", f_header_sub), barcode_obj],
        ["", Paragraph(f"<b>{cons_no}</b>", f_val_lg)]
    ]
    t_header = Table(header_data, colWidths=[335, 210])
    t_header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('LINEBEFORE', (1,0), (1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    
    row2_data = [[
        Paragraph(f"<b>Origin:</b> <font size=11 color='#002147'>{origin.upper()}</font>", f_val_lg),
        Paragraph(f"<b>Destination:</b><br/><font size=14>{dest.upper()}</font>", f_val_huge),
        Paragraph(f"<b>Date:</b> {date}<br/><b>Booking:</b> {booking_type}", f_val_lg)
    ]]
    t_row2 = Table(row2_data, colWidths=[175, 200, 170])
    t_row2.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    
    row3_data = [
        [Paragraph("CONSIGNOR (FROM)", f_val_lg), Paragraph("CONSIGNEE (TO)", f_val_lg)],
        [
            Paragraph(f"<font size=12 color='#002147'><b>{sender_name.upper()}</b></font><br/><b>Address:</b> {sender_address}<br/><b>City/Pin:</b> {sender_city}", f_val_lg),
            Paragraph(f"<font size=12 color='#002147'><b>{rec_name.upper()}</b></font><br/><b>Address:</b> {rec_address}<br/><b>City/Pin:</b> {rec_city}", f_val_lg)
        ]
    ]
    t_row3 = Table(row3_data, colWidths=[272.5, 272.5])
    t_row3.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#E6ECF2')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#E6ECF2')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    
    p_charge_val = f"RS {float(packing_charge):,.2f}" if packing_charge and float(packing_charge) > 0 else "FREE"
    row4_data = [
        [Paragraph("Pieces", f_label_sm), Paragraph("Weight", f_label_sm), Paragraph("Packing Details", f_label_sm), Paragraph("Packing Charge", f_label_sm), Paragraph("Total Amount", f_label_sm)],
        [
            Paragraph(f"<b>{pcs} Pcs</b>", f_val_huge),
            Paragraph(f"<b>{weight} Kg</b>", f_val_huge),
            Paragraph(f"<b>{packing_info}</b>", f_val_lg),
            Paragraph(f"<b>{p_charge_val}</b>", f_val_blue),
            Paragraph(f"<b>RS {amount}/-</b>", f_val_green)
        ]
    ]
    t_row4 = Table(row4_data, colWidths=[80, 80, 150, 115, 120])
    t_row4.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F0F4F8')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    
    story.append(t_header)
    story.append(Spacer(1, 4))
    story.append(t_row2)
    story.append(Spacer(1, 4))
    story.append(t_row3)
    story.append(Spacer(1, 4))
    story.append(t_row4)
    story.append(Spacer(1, 6))
    
    full_track_link = tracking_url + cons_no if tracking_url else ""
    if full_track_link:
        try:
            qr_widget = qr.QrCodeWidget(full_track_link)
            bounds = qr_widget.getBounds()
            qw = bounds[2] - bounds[0]
            qh = bounds[3] - bounds[1]
            d = Drawing(50, 50)
            d.add(qr_widget)
            d.scale(50.0 / qw, 50.0 / qh)
            
            track_text = Paragraph(
                f"<b>🌐 Live Tracking URL ({courier_co}):</b> <font size=7 color='blue'><u>{full_track_link}</u></font><br/>"
                "<font size=7 color='darkgreen'><i>📱 Scan QR to track consignment live!</i></font>",
                f_footer
            )
            t_track = Table([[d, track_text]], colWidths=[60, 485])
            t_track.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
                ('PADDING', (0,0), (-1,-1), 3),
            ]))
            story.append(t_track)
            story.append(Spacer(1, 4))
        except Exception:
            pass

    if img_bytes:
        try:
            img_io = io.BytesIO(img_bytes)
            large_photo = RLImage(img_io, width=180, height=110)
            photo_table = Table([[large_photo]], colWidths=[545])
            photo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
                ('PADDING', (0,0), (-1,-1), 3),
            ]))
            story.append(photo_table)
            story.append(Spacer(1, 4))
        except Exception:
            pass
            
    foot_data = [[
        Paragraph("<b>Remarks:</b> Booking Generated via Courier Solution.<br/><i>* Subject to terms & conditions.</i>", f_footer),
        Paragraph("________________________<br/><b>Authorized Signatory</b>", f_val_lg)
    ]]
    t_foot = Table(foot_data, colWidths=[335, 210])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_foot)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generate_packing_pdf_receipt(receipt_no, date, customer_name, mobile, items_desc, total_charge):
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
    story.append(Paragraph("PACKING MATERIAL & SERVICE RECEIPT", rec_head_style))
    
    data = [
        [Paragraph("<b>Receipt No:</b>", normal_style), Paragraph(f"{receipt_no}", normal_style)],
        [Paragraph("<b>Date:</b>", normal_style), Paragraph(f"{date}", normal_style)],
        [Paragraph("<b>Customer Name:</b>", normal_style), Paragraph(f"<font size=12 color='#002147'><b>{customer_name}</b></font>", normal_style)],
        [Paragraph("<b>Mobile No:</b>", normal_style), Paragraph(f"{mobile if mobile else 'N/A'}", normal_style)],
        [Paragraph("<b>Packing Items / Details:</b>", normal_style), Paragraph(f"<b>{items_desc}</b>", normal_style)],
        [Paragraph("<b>Total Packing Amount:</b>", normal_style), Paragraph(f"<font size=13 color='green'><b>₹ {float(total_charge):,.2f}/-</b></font>", normal_style)]
    ]
    t = Table(data, colWidths=[180, 340])
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
    t_foot.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
    story.append(t_foot)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generate_pdf_invoice(bill_no, party_name, period_str, bill_date, items, total_amount):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    invoice_head_style = ParagraphStyle('InvHead', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#d9534f'), alignment=1, spaceAfter=15)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, leading=13)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.black, fontName='Helvetica-Bold', leading=13)
    
    story.append(Paragraph("📦 COURIER SOLUTION", title_style))
    story.append(Paragraph("Express Cargo & Logistics Services", sub_title_style))
    story.append(Paragraph("TAX INVOICE / MONTHLY BILL", invoice_head_style))
    
    details_data = [
        [
            Paragraph(f"<b>Invoice To:</b><br/><font size=11 color='#002147'><b>{party_name}</b></font><br/>Billing Period: {period_str}", normal_style),
            Paragraph(f"<b>Invoice No:</b> <font color='red'><b>{bill_no}</b></font><br/><b>Date:</b> {bill_date}<br/><b>Status:</b> UNPAID", normal_style)
        ]
    ]
    t_details = Table(details_data, colWidths=[310, 230])
    t_details.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')), ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('PADDING', (0,0), (-1,-1), 8)]))
    story.append(t_details)
    story.append(Spacer(1, 15))
    
    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Cons No</b>', bold_style), Paragraph('<b>Date</b>', bold_style), Paragraph('<b>Courier</b>', bold_style), Paragraph('<b>Dest</b>', bold_style), Paragraph('<b>Recipient</b>', bold_style), Paragraph('<b>Packing</b>', bold_style), Paragraph('<b>Amount</b>', bold_style)]
    data = [headers]
    for idx, r in enumerate(items, 1):
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(str(r[1]), normal_style),
            Paragraph(str(r[2]), normal_style),
            Paragraph(str(r[3]), bold_style),
            Paragraph(str(r[4]), normal_style),
            Paragraph(str(r[5]), normal_style),
            Paragraph(str(r[20] if len(r)>20 and r[20] else 'Free'), normal_style),
            Paragraph(f"RS {float(r[7]):,.2f}", normal_style)
        ])
    t_items = Table(data, colWidths=[25, 85, 60, 65, 75, 95, 85, 55])
    t_items.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')), ('PADDING', (0,0), (-1,-1), 5)]))
    story.append(t_items)
    story.append(Spacer(1, 15))
    
    total_data = [
        [
            Paragraph("<b>TOTAL PAYABLE AMOUNT:</b>", ParagraphStyle('TotLbl', parent=styles['Normal'], fontSize=11, alignment=2)),
            Paragraph(f"<b>RS {total_amount:,.2f}/-</b>", ParagraphStyle('TotVal', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#008000'), alignment=2))
        ]
    ]
    t_total = Table(total_data, colWidths=[380, 160])
    t_total.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9')), ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#008000')), ('PADDING', (0,0), (-1,-1), 8)]))
    story.append(t_total)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

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
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')), ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#008000')), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e0e0e0')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 10)]))
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
    "🚚 Add Courier Master (કુરિયર અને ટ્રેકિંગ URL ઉમેરો)",
    "💵 Cash Courier Booking (કેશ બુકિંગ & પેકિંગ)",
    "📦 Separate Packing Service (અલગ પેકિંગ સર્વિસ રિસીપ્ટ)",
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
        st.write("### 📝 પાર્ટી ફોર્મ")
        p_name_val = edit_data[1] if edit_data else ""
        p_addr_val = edit_data[2] if edit_data else ""
        p_city_val = edit_data[3] if edit_data else ""
        p_mob_val = edit_data[4] if edit_data else ""

        p_name = st.text_input("Party Name:", value=p_name_val)
        p_addr = st.text_input("Address:", value=p_addr_val)
        p_city = st.text_input("City / Pin Code:", value=p_city_val)
        p_mob = st.text_input("WhatsApp Mobile No:", value=p_mob_val)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1: submit_p = st.form_submit_button("💾 Save Party", type="primary")
        with col_f2: cancel_edit = st.form_submit_button("❌ Cancel Edit")

        if cancel_edit:
            st.session_state['edit_party_id'] = None
            st.rerun()

        if submit_p:
            if not p_name.strip():
                st.error("પાર્ટીનું નામ ભરો!")
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
                    st.success(f"પાર્ટી '{p_name}' સેવ થઈ ગઈ છે!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("આ નામની પાર્ટી પહેલેથી છે!")
    conn.close()

# ----------------- ૨. COURIER MASTER -----------------
elif menu == "🚚 Add Courier Master (કુરિયર અને ટ્રેકિંગ URL ઉમેરો)":
    st.subheader("🚚 Courier Master & Tracking URL Management")
    with st.form("courier_form"):
        c_name_input = st.text_input("Courier Company Name (દા.ત. DTDC, Delhivery):")
        c_url_input = st.text_input("Tracking Base URL:")
        submit_courier = st.form_submit_button("💾 Save Courier", type="primary")
        if submit_courier and c_name_input.strip() and c_url_input.strip():
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO couriers (courier_name, tracking_url) VALUES (?, ?)", (c_name_input.strip(), c_url_input.strip()))
            conn.commit()
            conn.close()
            st.success("કુરિયર સેવ થઈ ગયું છે!")
            st.rerun()

# ----------------- ૩. CASH BOOKING WITH PACKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & પેકિંગ)":
    tab1, tab2, tab3 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History", "🖨️ Re-Print Receipt"])
    
    conn_c = get_local_connection()
    cur_c = conn_c.cursor()
    cur_c.execute("SELECT courier_name, tracking_url FROM couriers ORDER BY courier_name ASC")
    courier_master_data = cur_c.fetchall()
    conn_c.close()
    
    courier_names_list = [c[0] for c in courier_master_data] if courier_master_data else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = {c[0]: c[1] for c in courier_master_data} if courier_master_data else {}

    with tab1:
        st.subheader("Cash Courier Booking with Packing Charges")
        uploaded_photo = st.file_uploader("📷 પાર્સલ/લેબલનો ફોટો અપલોડ કરો:", type=["jpg", "jpeg", "png"], key="c_photo")
        auto_cons, auto_pin = "", ""
        if uploaded_photo:
            auto_cons, auto_pin = scan_label_image(uploaded_photo.getvalue())

        col1, col2 = st.columns(2)
        with col1:
            cons_no = st.text_input("Consignment No:", value=auto_cons, key="c_cons")
            date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="c_date")
            selected_courier = st.selectbox("Courier Company:", courier_names_list, key="c_co_select")
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

        st.markdown("---")
        st.write("### 📦 Courier Packing & Material Options (પેકિંગ ઓપ્શન)")
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            packing_option = st.selectbox("Select Packing Type:", ["Free Packing (કોઈ ચાર્જ નહીં)", "Cellotape (સેલોટેપ)", "Box Packing (બોક્સ)", "Online Bag (ઓનલાઈન બેગ)", "Custom Packing (મેન્યુઅલ ચાર્જ)"])
        with p_col2:
            packing_charge_input = st.text_input("Packing Charge (RS):", "0")
        with p_col3:
            weight = st.text_input("Weight (Kg):", "1.0", key="c_wt")

        col3, col4 = st.columns(2)
        with col3: pcs = st.text_input("Pieces (Pcs):", "1", key="c_pcs")
        with col4: amount = st.text_input("Courier Freight Amount (RS):", key="c_amt")
        
        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No:", key="c_wa_num")
        c_initial_pay_status = st.selectbox("Payment Status:", ["Paid (ચૂકવાઈ ગયું)", "Unpaid (બાકી)"], key="c_init_status")

        if st.button("💾 Save & Generate Receipt with Packing", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("મહેરબાની કરીને જરૂરી ખાના ભરો!")
            else:
                img_bytes = uploaded_photo.getvalue() if uploaded_photo else None
                status_val = "Paid" if "Paid" in c_initial_pay_status else "Unpaid"
                
                try:
                    freight_amt = float(amount) if amount else 0.0
                    pack_amt = float(packing_charge_input) if packing_charge_input else 0.0
                    total_final_amt = freight_amt + pack_amt
                except Exception:
                    total_final_amt = amount

                data_tuple = (
                    cons_no.strip(), date_entry.strip(), selected_courier.strip(), mode.strip(), 
                    origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), 
                    sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), 
                    weight.strip(), pcs.strip(), str(total_final_amt), 'Cash', None, status_val,
                    packing_option, packing_charge_input.strip()
                )
                
                try:
                    save_receipt_to_cloud_and_local(data_tuple, img_bytes)
                    st.success(f"Cash Entry Saved Successfully with Packing for Consignment: {cons_no}")
                    
                    t_url = courier_url_dict.get(selected_courier, "")
                    pdf_bytes = generate_hd_receipt_pdf(
                        cons_no, date_entry, selected_courier, mode, origin, dest, sender_name, 
                        sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, 
                        str(total_final_amt), 'Cash', packing_option, packing_charge_input, t_url, img_bytes
                    )
                    st.download_button(label="📄 Download Printable PDF Receipt with Packing & Tracking", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")
                    
                    if c_whatsapp_num.strip():
                        track_link_full = t_url + cons_no if t_url else ""
                        wa_msg = (
                            f"📦 COURIER SOLUTION RECEIPT\n\nConsignment No: {cons_no}\nCourier: {selected_courier}\n"
                            f"Packing: {packing_option} [Charge: RS {packing_charge_input}/-]\n"
                            f"To: {rec_name} ({dest})\nTotal Amount: RS {total_final_amt}/- [{status_val}]\n"
                            f"{f'Tracking Link: {track_link_full}' if track_link_full else ''}"
                        )
                        wa_url = create_whatsapp_link(c_whatsapp_num.strip(), wa_msg)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Send on WhatsApp</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"ભૂલ આવી: {e}")

    with tab2:
        st.subheader("📜 Cash Booking Records")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cons_no, date, courier_co, sender_name, rec_name, amount, payment_status, packing_info, packing_charge FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        cash_rows = cursor.fetchall()
        conn.close()
        for r in cash_rows:
            st.write(f"Cons: **{r[0]}** | Date: {r[1]} | Courier: {r[2]} | From: {r[3]} ➔ To: {r[4]} | Total: RS {r[5]} | Packing: {r[7]} (RS {r[8]})")

    with tab3:
        st.subheader("🖨️ Re-Print Receipt by Consignment No")
        search_cons = st.text_input("Enter Consignment No:")
        if st.button("🔍 Search & Print", type="primary"):
            if search_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img, packing_info, packing_charge FROM receipts WHERE cons_no=?", (search_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ મળી ગઈ છે!")
                    c_co_name = rec_data[2]
                    t_url = courier_url_dict.get(c_co_name, "")
                    pdf_bytes = generate_hd_receipt_pdf(
                        rec_data[0], rec_data[1], c_co_name, rec_data[3], rec_data[4], rec_data[5], 
                        rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], 
                        rec_data[12], rec_data[13], rec_data[14], rec_data[15], rec_data[17], rec_data[18], t_url, rec_data[16]
                    )
                    st.download_button(label="🖨️ Download Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{rec_data[0]}.pdf", mime="application/pdf", type="primary")
                else:
                    st.error("કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૪. SEPARATE PACKING SERVICE MENU (FIXED) -----------------
elif menu == "📦 Separate Packing Service (અલગ પેકિંગ સર્વિસ રિસીપ્ટ)":
    st.subheader("📦 Separate Packing Service & Material Billing")
    st.info("💡 અહીંથી તમે કોઈપણ ગ્રાહકને કુરિયર વગર ખાલી પેકિંગ મટીરીયલ (બોક્સ, સેલોટેપ, ઓનલાઈન બેગ વગેરે) કે સર્વિસનું અલગથી બિલ કે રિસીપ્ટ બનાવી આપી શકો છો.")

    # એરર દૂર કરવા માટે st.form ને હટાવીને સાદા ઇનપુટ અને બટન મૂક્યા છે
    cust_name = st.text_input("Customer Name (ગ્રાહકનું નામ):", key="sep_cust_name")
    cust_mob = st.text_input("Mobile No (મોબાઈલ નંબર):", key="sep_cust_mob")
    pack_date = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="sep_pack_date")
    
    st.markdown("---")
    st.write("### પેકિંગ મટીરીયલ અને આઇટમ્સ સિલેક્ટ કરો:")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        item_box = st.checkbox("Box Packing (બોક્સ પૅકિંગ)")
        item_tape = st.checkbox("Cellotape (સેલોટેપ)")
    with col_p2:
        item_bag = st.checkbox("Online Bag (ઓનલાઈન બેગ)")
        item_other = st.checkbox("Other Material (અન્ય મટીરીયલ)")

    custom_items_desc = st.text_input("Custom Details / Notes (વિગત લખો - દા.ત. 2 Large Box, 1 Tape):", key="sep_custom_desc")
    total_pack_charge = st.text_input("Total Packing Charge (કુલ પેકિંગ ચાર્જ RS):", "50", key="sep_total_charge")

    if st.button("💾 Save & Generate Packing Receipt", type="primary", key="sep_save_btn"):
        if not cust_name.strip() or not total_pack_charge.strip():
            st.error("મહેરબાની કરીને ગ્રાહકનું નામ અને પેકિંગ ચાર્જ ભરો!")
        else:
            selected_items = []
            if item_box: selected_items.append("Box Packing")
            if item_tape: selected_items.append("Cellotape")
            if item_bag: selected_items.append("Online Bag")
            if item_other: selected_items.append("Other")
            if custom_items_desc: selected_items.append(custom_items_desc)
            
            items_str = ", ".join(selected_items) if selected_items else "General Packing"

            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM packing_receipts")
            p_count = cursor.fetchone()[0] + 1
            rec_no = f"PACK-REC-{p_count:04d}"

            cursor.execute("""
                INSERT INTO packing_receipts (receipt_no, date, customer_name, mobile, packing_items, total_charge)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rec_no, pack_date.strip(), cust_name.strip(), cust_mob.strip(), items_str, total_pack_charge.strip()))
            conn.commit()
            conn.close()

            st.success(f"પેકિંગ રિસીપ્ટ સફળતાપૂર્વક બની ગઈ છે! [Receipt No: {rec_no}]")
            
            pdf_pack_bytes = generate_packing_pdf_receipt(rec_no, pack_date, cust_name, cust_mob, items_str, total_pack_charge)
            st.download_button(
                label="📄 Download Packing Receipt PDF",
                data=pdf_pack_bytes,
                file_name=f"Packing_Receipt_{rec_no}_{cust_name}.pdf",
                mime="application/pdf",
                type="primary",
                key="dl_sep_pack_pdf"
            )

            if cust_mob.strip():
                wa_pack_msg = (
                    "📦 COURIER SOLUTION - PACKING RECEIPT\n\n"
                    f"Customer: {cust_name}\n"
                    f"Receipt No: {rec_no}\n"
                    f"Items: {items_str}\n"
                    f"Total Amount: RS {total_pack_charge}/-\n\n"
                    "Thank you for visiting Courier Solution!"
                )
                wa_p_url = create_whatsapp_link(cust_mob.strip(), wa_pack_msg)
                st.markdown(f'<a href="{wa_p_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Send Packing Receipt on WhatsApp</a>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📜 Previous Packing Receipts History")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, receipt_no, date, customer_name, mobile, packing_items, total_charge FROM packing_receipts ORDER BY id DESC")
    all_packs = cursor.fetchall()
    conn.close()

    if all_packs:
        for idx, pr in enumerate(all_packs, 1):
            p_id, p_rec, p_date, p_cust, p_mob, p_items, p_amt = pr
            col_pr1, col_pr2, col_pr3 = st.columns([3, 1.2, 1])
            with col_pr1:
                st.write(f"[{idx}] **{p_rec}** | Date: {p_date} | Customer: **{p_cust}** | Items: {p_items} | **RS {p_amt}/-**")
            with col_pr2:
                hist_p_pdf = generate_packing_pdf_receipt(p_rec, p_date, p_cust, p_mob, p_items, p_amt)
                st.download_button("🖨️ PDF", data=hist_p_pdf, file_name=f"Packing_Receipt_{p_rec}.pdf", mime="application/pdf", key=f"dl_pack_{p_id}")
            with col_pr3:
                if st.button("🗑️ Delete", key=f"del_pack_{p_id}"):
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM packing_receipts WHERE id=?", (p_id,))
                    conn.commit()
                    conn.close()
                    st.success("પેકિંગ રિસીપ્ટ ડિલીટ થઈ ગઈ છે!")
                    st.rerun()
    else:
        st.info("કોઈ સેપરેટ પેકિંગ રિસીપ્ટ એન્ટ્રી નથી.")

# ----------------- ૫. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    st.subheader("Credit Account Booking with Packing Charges")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
    parties_data = cursor.fetchall()
    cur_c = conn.cursor()
    cur_c.execute("SELECT courier_name, tracking_url FROM couriers ORDER BY courier_name ASC")
    courier_master_data = cur_c.fetchall()
    conn.close()
    
    party_dict = {r[0]: {"address": r[1], "city": r[2], "mobile": r[3]} for r in parties_data}
    party_names = list(party_dict.keys())
    courier_names_list = [c[0] for c in courier_master_data] if courier_master_data else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = {c[0]: c[1] for c in courier_master_data} if courier_master_data else {}

    if not party_names:
        st.warning("⚠️ પહેલા પાર્ટી ઉમેરો!")
    else:
        selected_party = st.selectbox("Select Party Name:", party_names)
        cr_uploaded_photo = st.file_uploader("📷 પાર્સલ ફોટો અપલોડ કરો:", type=["jpg", "jpeg", "png"], key="cr_photo")
        cr_auto_cons, cr_auto_pin = "", ""
        if cr_uploaded_photo:
            cr_auto_cons, cr_auto_pin = scan_label_image(cr_uploaded_photo.getvalue())
        
        col1, col2 = st.columns(2)
        with col1:
            cons_no = st.text_input("Consignment No:", value=cr_auto_cons, key="cr_cons")
            date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="cr_date")
            selected_courier = st.selectbox("Courier Company:", courier_names_list, key="cr_co_select")
            mode = st.text_input("Service Mode:", "Surface", key="cr_mode")
            origin = st.text_input("Origin:", "BHAVNAGAR", key="cr_orig")
            dest = st.text_input("Destination:", key="cr_dest")
        with col2:
            sender_address = st.text_input("Sender Address:", value=party_dict[selected_party]["address"], key=f"cr_s_addr_{selected_party}")
            sender_city = st.text_input("Sender City/Pin:", value=party_dict[selected_party]["city"], key=f"cr_s_city_{selected_party}")
            rec_name = st.text_input("Recipient Name:", key="cr_r_name")
            rec_address = st.text_input("Recipient Address:", key="cr_r_addr")
            rec_city = st.text_input("Recipient City/Pin:", value=cr_auto_pin, key="cr_r_city")
        
        st.markdown("---")
        p_col1, p_col2 = st.columns(2)
        with p_col1: packing_option = st.selectbox("Select Packing Type:", ["Free Packing", "Cellotape", "Box Packing", "Online Bag", "Custom Packing"], key="cr_pack")
        with p_col2: packing_charge_input = st.text_input("Packing Charge (RS):", "0", key="cr_pack_amt")

        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="cr_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="cr_pcs")
        with col5: amount = st.text_input("Freight Amount (RS):", key="cr_amt")
        
        if st.button("💾 Save & Print Credit Booking with Packing", type="primary"):
            if not cons_no or not rec_name or not amount:
                st.error("બધી માહિતી ભરો!")
            else:
                cr_img_bytes = cr_uploaded_photo.getvalue() if cr_uploaded_photo else None
                try:
                    freight_amt = float(amount) if amount else 0.0
                    pack_amt = float(packing_charge_input) if packing_charge_input else 0.0
                    total_final_amt = freight_amt + pack_amt
                except Exception:
                    total_final_amt = amount

                data_tuple = (
                    cons_no.strip(), date_entry.strip(), selected_courier.strip(), mode.strip(), 
                    origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), 
                    sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), 
                    weight.strip(), pcs.strip(), str(total_final_amt), 'Credit Account', None, 'Unpaid',
                    packing_option, packing_charge_input.strip()
                )
                try:
                    save_receipt_to_cloud_and_local(data_tuple, cr_img_bytes)
                    st.success(f"Credit Entry Saved for '{selected_party}'")
                    t_url = courier_url_dict.get(selected_courier, "")
                    pdf_bytes = generate_hd_receipt_pdf(
                        cons_no, date_entry, selected_courier, mode, origin, dest, selected_party, 
                        sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, 
                        str(total_final_amt), 'Credit Account', packing_option, packing_charge_input, t_url, cr_img_bytes
                    )
                    st.download_button(label="🖨️ Download Credit Receipt PDF", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")
                except Exception as e:
                    st.error(f"ભૂલ આવી: {e}")

# ----------------- ૬. MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ પીડીએફ બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    conn.close()
    p_list = [r[0] for r in p_data]
    if not p_list:
        st.warning("કોઈ પાર્ટી નથી.")
    else:
        sel_party = st.selectbox("Select Party for Bill:", p_list)
        if st.button("📄 Generate Digital PDF Invoice", type="primary"):
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, cons_no, date, courier_co, dest, rec_name, weight, amount, packing_info, packing_charge FROM receipts WHERE sender_name=? AND booking_type='Credit Account' AND (bill_no IS NULL OR bill_no='') ORDER BY id DESC", (sel_party,))
            b_rows = cursor.fetchall()
            if b_rows:
                cursor.execute("SELECT COUNT(*) FROM bills")
                b_count = cursor.fetchone()[0] + 1
                generated_bill_no = f"BILL-2026-{b_count:03d}"
                tot_bill = sum(float(r[7]) for r in b_rows if r[7])
                cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                              (generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                for item in b_rows:
                    cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                conn.commit()
                conn.close()

                pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, f"{start_str} to {end_str}", today.strftime("%d/%m/%Y"), b_rows, tot_bill)
                st.success(f"બિલ સફળતાપૂર્વક બની ગયું છે!")
                st.download_button(label="📄 Download Invoice PDF", data=pdf_bytes, file_name=f"Invoice_{generated_bill_no}.pdf", mime="application/pdf", type="primary")
            else:
                conn.close()
                st.info("કોઈ અનબિલ એન્ટ્રી નથી.")

# ----------------- ૭. PAYMENT RECEIVE -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)":
    st.subheader("💳 Party Payment Receive")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    conn.close()
    p_list = [r[0] for r in p_data]
    if p_list:
        with st.form("pay_form"):
            pay_party = st.selectbox("Party Name:", p_list)
            pay_amt = st.text_input("Amount Received (RS):")
            pay_mode = st.selectbox("Mode:", ["Cash", "UPI", "Cheque"])
            sub = st.form_submit_button("Save Payment", type="primary")
        if sub and pay_amt.strip():
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO party_payments (party_name, bill_no, date, amount, pay_mode, note) VALUES (?, 'DIRECT', ?, ?, ?, '')",
                          (pay_party, today.strftime("%d/%m/%Y"), pay_amt, pay_mode))
            rec_id = cursor.lastrowid
            conn.commit()
            conn.close()
            st.success("પેમેન્ટ જમા થઈ ગયું!")
            pdf_b = generate_payment_pdf_receipt(rec_id, pay_party, "DIRECT", today.strftime("%d/%m/%Y"), pay_amt, pay_mode, "")
            st.download_button("Download Receipt", data=pdf_b, file_name=f"Pay_{rec_id}.pdf", mime="application/pdf", type="primary")

# ----------------- ૮. SUMMARY -----------------
elif menu == "📊 Summary & Reports (કેશ & ક્રેડિટ સમરી)":
    st.subheader("📊 Summary & Reports")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM receipts WHERE booking_type='Cash'")
    c_sum = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(amount) FROM receipts WHERE booking_type='Credit Account'")
    cr_sum = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(total_charge) FROM packing_receipts")
    p_sum = cursor.fetchone()[0] or 0.0
    conn.close()
    st.metric("📦 Total Cash Bookings", f"RS {c_sum:,.2f}/-")
    st.metric("📋 Total Credit Bookings", f"RS {cr_sum:,.2f}/-")
    st.metric("📦 Separate Packing Receipts Total", f"RS {p_sum:,.2f}/-")
