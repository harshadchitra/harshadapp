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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
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
    
    # 🚚 કુરિયર માસ્ટર અને ટ્રેકિંગ URL માટે નવી ટેબલ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS couriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            courier_name TEXT UNIQUE,
            tracking_url TEXT
        )
    """)
    
    # ડિફોલ્ટ કુરિયર એન્ટ્રીઓ ઉમેરવી (જો પહેલેથી ન હોય તો)
    default_couriers = [
        ("DTDC", "https://www.dtdc.in/tracking/shipment-tracking.asp?strCnno="),
        ("Delhivery", "https://www.delhivery.com/track/package/"),
        ("Trackon", "https://trackon.in/track?awb=")
    ]
    for c_name, c_url in default_couriers:
        cursor.execute("INSERT OR IGNORE INTO couriers (courier_name, tracking_url) VALUES (?, ?)", (c_name, c_url))

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

    sconn = get_supabase_connection()
    if sconn:
        try:
            scur = sconn.cursor()
            scur.execute("""
                CREATE TABLE IF NOT EXISTS couriers (
                    id SERIAL PRIMARY KEY,
                    courier_name TEXT UNIQUE,
                    tracking_url TEXT
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

        scur.execute("SELECT party_name, party_address, party_city, mobile FROM parties")
        for row in scur.fetchall():
            lcur.execute("INSERT OR IGNORE INTO parties (party_name, party_address, party_city, mobile) VALUES (?, ?, ?, ?)", row)
            
        scur.execute("SELECT courier_name, tracking_url FROM couriers")
        for row in scur.fetchall():
            lcur.execute("INSERT OR IGNORE INTO couriers (courier_name, tracking_url) VALUES (?, ?)", row)
        
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

# ----------------- સેવ ફંક્શન -----------------
def save_receipt_to_cloud_and_local(data_tuple, img_bytes):
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple + (img_bytes,))
    conn.commit()
    conn.close()

    sconn = get_supabase_connection()
    if sconn:
        try:
            scur = sconn.cursor()
            cloud_tuple = (
                data_tuple[0], data_tuple[1], data_tuple[2], data_tuple[3], data_tuple[4], 
                data_tuple[5], data_tuple[6], data_tuple[7], data_tuple[8], data_tuple[9], 
                data_tuple[10], data_tuple[11], data_tuple[12], data_tuple[13], data_tuple[14], 
                data_tuple[15], data_tuple[16], data_tuple[17]
            )
            scur.execute("""
                INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, bill_no, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cons_no) DO UPDATE SET 
                    date = EXCLUDED.date,
                    courier_co = EXCLUDED.courier_co,
                    mode = EXCLUDED.mode,
                    origin = EXCLUDED.origin,
                    dest = EXCLUDED.dest,
                    sender_name = EXCLUDED.sender_name,
                    sender_address = EXCLUDED.sender_address,
                    sender_city = EXCLUDED.sender_city,
                    rec_name = EXCLUDED.rec_name,
                    rec_address = EXCLUDED.rec_address,
                    rec_city = EXCLUDED.rec_city,
                    weight = EXCLUDED.weight,
                    pcs = EXCLUDED.pcs,
                    amount = EXCLUDED.amount,
                    booking_type = EXCLUDED.booking_type,
                    payment_status = EXCLUDED.payment_status
            """, cloud_tuple)
            sconn.commit()
            scur.close()
            sconn.close()
        except Exception as e:
            print("Cloud Save Error:", e)

# ----------------- AI PHOTO AUTO-FILL SCANNER -----------------
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

# ----------------- WHATSAPP LINK -----------------
def create_whatsapp_link(phone_num, msg_text):
    clean_phone = ''.join(filter(str.isdigit, str(phone_num)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_text = urllib.parse.quote(msg_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

# ----------------- HD PDF RECEIPT WITH TRACKING URL & PHOTO -----------------
def generate_hd_receipt_pdf(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, tracking_url="", img_bytes=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    f_header_title = ParagraphStyle('HTitle', fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=colors.HexColor('#002147'))
    f_header_sub = ParagraphStyle('HSub', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#333333'))
    f_label_sm = ParagraphStyle('LblSm', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black)
    f_val_lg = ParagraphStyle('ValLg', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.black)
    f_val_huge = ParagraphStyle('ValHuge', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.black)
    f_val_blue = ParagraphStyle('ValBlue', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.blue)
    f_val_green = ParagraphStyle('ValGreen', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor('#008000'))
    f_footer = ParagraphStyle('Foot', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#444444'))
    
    barcode_obj = code128.Code128(cons_no, barHeight=30, barWidth=1.4)
    
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
        Paragraph(f"<b>Origin:</b> <font size=12 color='#002147'>{origin.upper()}</font>", f_val_lg),
        Paragraph(f"<b>Destination:</b><br/><font size=15>{dest.upper()}</font>", f_val_huge),
        Paragraph(f"<b>Date:</b> {date}<br/><b>Booking:</b> {booking_type}", f_val_lg)
    ]]
    t_row2 = Table(row2_data, colWidths=[175, 200, 170])
    t_row2.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    row3_data = [
        [Paragraph("CONSIGNOR (FROM)", f_val_lg), Paragraph("CONSIGNEE (TO)", f_val_lg)],
        [
            Paragraph(f"<font size=13 color='#002147'><b>{sender_name.upper()}</b></font><br/><br/><b>Address:</b> {sender_address}<br/><b>City/Pin:</b> {sender_city}", f_val_lg),
            Paragraph(f"<font size=13 color='#002147'><b>{rec_name.upper()}</b></font><br/><br/><b>Address:</b> {rec_address}<br/><b>City/Pin:</b> {rec_city}", f_val_lg)
        ]
    ]
    t_row3 = Table(row3_data, colWidths=[272.5, 272.5])
    t_row3.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#E6ECF2')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#E6ECF2')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
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
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(t_header)
    story.append(Spacer(1, 5))
    story.append(t_row2)
    story.append(Spacer(1, 5))
    story.append(t_row3)
    story.append(Spacer(1, 5))
    story.append(t_row4)
    story.append(Spacer(1, 8))
    
    # ટ્રેકિંગ URL અને QR કોડ સેクション
    full_track_link = tracking_url + cons_no if tracking_url else ""
    if full_track_link:
        try:
            qr_widget = qr.QrCodeWidget(full_track_link)
            bounds = qr_widget.getBounds()
            qw = bounds[2] - bounds[0]
            qh = bounds[3] - bounds[1]
            d = Drawing(60, 60)
            d.add(qr_widget)
            d.scale(60.0 / qw, 60.0 / qh)
            
            track_text = Paragraph(
                f"<b>🌐 Live Tracking URL ({courier_co}):</b><br/>"
                f"<font size=8 color='blue'><u>{full_track_link}</u></font><br/>"
                "<font size=8 color='darkgreen'><i>📱 Scan QR Code above to track consignment live on phone!</i></font>",
                f_footer
            )
            t_track = Table([[d, track_text]], colWidths=[70, 475])
            t_track.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_track)
            story.append(Spacer(1, 6))
        except Exception:
            pass

    if img_bytes:
        try:
            img_io = io.BytesIO(img_bytes)
            large_photo = RLImage(img_io, width=200, height=130)
            photo_table = Table([[large_photo]], colWidths=[545])
            photo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(photo_table)
            story.append(Spacer(1, 6))
        except Exception:
            pass
            
    foot_data = [[
        Paragraph("<b>Remarks:</b> Booking Generated via Courier Solution.<br/><i>* Subject to terms & conditions.</i>", f_footer),
        Paragraph("________________________<br/><b>Authorized Signatory</b>", f_val_lg)
    ]]
    t_foot = Table(foot_data, colWidths=[335, 210])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_foot)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- અન્ય PDF રિપોર્ટ જનરેટર્સ -----------------
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
        Paragraph("<b>TOTAL</b>", bold_style), "", "", "", "", "",
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

def generate_pdf_invoice(bill_no, party_name, period_str, bill_date, items, total_amount):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    invoice_head_style = ParagraphStyle('InvHead', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#d9534f'), alignment=1, spaceAfter=15)
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
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#008000')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e0e0e0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

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
    
    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Bill No</b>', bold_style), Paragraph('<b>Party Name</b>', bold_style), Paragraph('<b>Bill Date</b>', bold_style), Paragraph('<b>Period</b>', bold_style), Paragraph('<b>Amount (RS)</b>', bold_style)]
    data = [headers]
    tot_amt = 0.0
    for idx, b in enumerate(all_bills, 1):
        amt_val = float(b[5]) if b[5] else 0.0
        tot_amt += amt_val
        data.append([Paragraph(str(idx), normal_style), Paragraph(f"<b>{b[1]}</b>", normal_style), Paragraph(str(b[2]), normal_style), Paragraph(str(b[3]), normal_style), Paragraph(str(b[4]), normal_style), Paragraph(f"RS {amt_val:,.2f}", normal_style)])
    data.append([Paragraph("<b>TOTAL</b>", bold_style), "", "", "", "", Paragraph(f"<b>RS {tot_amt:,.2f}/-</b>", ParagraphStyle('GTotal', parent=bold_style, textColor=colors.HexColor('#008000')))])
    t = Table(data, colWidths=[30, 90, 180, 75, 100, 75])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')), ('SPAN', (0, -1), (4, -1)), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')), ('PADDING', (0,0), (-1,-1), 6)]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

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
    
    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Party Name</b>', bold_style), Paragraph('<b>Bill No</b>', bold_style), Paragraph('<b>Date</b>', bold_style), Paragraph('<b>Mode</b>', bold_style), Paragraph('<b>Note / Ref</b>', bold_style), Paragraph('<b>Amount (RS)</b>', bold_style)]
    data = [headers]
    tot_amt = 0.0
    for idx, r in enumerate(pay_rows, 1):
        amt_val = float(r[4]) if r[4] else 0.0
        tot_amt += amt_val
        data.append([Paragraph(str(idx), normal_style), Paragraph(f"<b>{r[1]}</b>", normal_style), Paragraph(f"{r[2]}", normal_style), Paragraph(f"{r[3]}", normal_style), Paragraph(f"{r[5]}", normal_style), Paragraph(str(r[6]) if r[6] else "-", normal_style), Paragraph(f"RS {amt_val:,.2f}", normal_style)])
    data.append([Paragraph("<b>TOTAL RECEIVED</b>", bold_style), "", "", "", "", "", Paragraph(f"<b>RS {tot_amt:,.2f}/-</b>", ParagraphStyle('GTotal', parent=bold_style, textColor=colors.HexColor('#008000')))])
    t = Table(data, colWidths=[25, 140, 80, 65, 75, 90, 75])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#008000')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')), ('SPAN', (0, -1), (5, -1)), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')), ('PADDING', (0,0), (-1,-1), 6)]))
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
                    st.success(f"પાર્ટી '{p_name}' સફળતાપૂર્વક સેવ થઈ ગઈ છે!")
                    sync_two_way()
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("આ નામની પાર્ટી પહેલેથી જ અસ્તિત્વમાં છે!")
    conn.close()

    st.markdown("---")
    st.write("### 🏢 સેવ થયેલી પાર્ટીઓની યાદી:")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, party_address, party_city, mobile FROM parties ORDER BY party_name ASC")
    p_rows = cursor.fetchall()
    conn.close()
    
    if p_rows:
        for idx, r in enumerate(p_rows, 1):
            r_id, r_name, r_addr, r_city, r_mob = r
            col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
            with col_p1:
                st.write(f"**{idx}. {r_name}** | {r_addr}, {r_city} | Mob: {r_mob if r_mob else '-'}")
            with col_p2:
                if st.button("✏️ Edit", key=f"edit_party_{r_id}"):
                    st.session_state['edit_party_id'] = r_id
                    st.rerun()
            with col_p3:
                if st.button("🗑️ Delete", key=f"del_party_{r_id}"):
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM parties WHERE id=?", (r_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"પાર્ટી '{r_name}' ડિલીટ થઈ ગઈ છે!")
                    st.rerun()
    else:
        st.info("હજુ સુધી કોઈ પાર્ટી ઉમેરેલી નથી.")

# ----------------- ૨. COURIER MASTER (NEW FEATURE) -----------------
elif menu == "🚚 Add Courier Master (કુરિયર અને ટ્રેકિંગ URL ઉમેરો)":
    st.subheader("🚚 Courier Master & Tracking URL Management")
    st.info("💡 અહીં તમે કોઈપણ કુરિયર (જેમ કે DTDC, Delhivery, Trackon, XYZ) અને તેની ટ્રેકિંગ URL (જેની પાછળ કન્સાઇનમેન્ટ નંબર લાગતો હોય) ઉમેરી શકો છો.")

    with st.form("courier_form"):
        c_name_input = st.text_input("Courier Company Name (કુરિયરનું નામ - દા.ત. DTDC):")
        c_url_input = st.text_input("Tracking Base URL (ટ્રેકિંગ લિંક - દા.ત. https://www.dtdc.in/tracking/...?strCnno=):")
        
        submit_courier = st.form_submit_button("💾 Save Courier", type="primary")
        if submit_courier:
            if not c_name_input.strip() or not c_url_input.strip():
                st.error("કુરિયરનું નામ અને ટ્રેકિંગ URL બંને ભરવું ફરજિયાત છે!")
            else:
                try:
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR REPLACE INTO couriers (courier_name, tracking_url) VALUES (?, ?)", 
                                  (c_name_input.strip(), c_url_input.strip()))
                    conn.commit()
                    conn.close()
                    
                    sconn = get_supabase_connection()
                    if sconn:
                        try:
                            scur = sconn.cursor()
                            scur.execute("INSERT INTO couriers (courier_name, tracking_url) VALUES (%s, %s) ON CONFLICT (courier_name) DO UPDATE SET tracking_url = EXCLUDED.tracking_url", 
                                         (c_name_input.strip(), c_url_input.strip()))
                            sconn.commit()
                            scur.close()
                            sconn.close()
                        except Exception: pass

                    st.success(f"કુરિયર '{c_name_input}' સફળતાપૂર્વક સેવ થઈ ગયું છે!")
                    sync_two_way()
                    st.rerun()
                except Exception as e:
                    st.error(f"ભૂલ આવી: {e}")

    st.markdown("---")
    st.subheader("📋 સેવ થયેલા કુરિયર્સ અને લિંક્સ:")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, courier_name, tracking_url FROM couriers ORDER BY courier_name ASC")
    courier_rows = cursor.fetchall()
    conn.close()

    if courier_rows:
        for idx, cr in enumerate(courier_rows, 1):
            cr_id, cr_name, cr_url = cr
            col_c1, col_c2 = st.columns([4, 1])
            with col_c1:
                st.write(f"**{idx}. {cr_name}**")
                st.caption(f"URL: {cr_url}")
            with col_c2:
                if st.button("🗑️ Delete", key=f"del_cr_master_{cr_id}"):
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM couriers WHERE id=?", (cr_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"કુરિયર '{cr_name}' ડિલીટ થઈ ગયું છે!")
                    st.rerun()
    else:
        st.info("કોઈ કુરિયર એડ થયેલ નથી.")

# ----------------- ૩. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)":
    tab1, tab2, tab3 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History & Date Filter (હિસ્ટ્રી & ટોટલ)", "🖨️ Re-Print Receipt (ફરીવાર પ્રિન્ટ)"])
    
    # કુરિયર માસ્ટર ડેટા મેળવવો
    conn_c = get_local_connection()
    cur_c = conn_c.cursor()
    cur_c.execute("SELECT courier_name, tracking_url FROM couriers ORDER BY courier_name ASC")
    courier_master_data = cur_c.fetchall()
    conn_c.close()
    
    courier_names_list = [c[0] for c in courier_master_data] if courier_master_data else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = {c[0]: c[1] for c in courier_master_data} if courier_master_data else {}

    with tab1:
        st.subheader("Cash Courier Booking")
        uploaded_photo = st.file_uploader("📷 પાર્સલ/લેબલનો ફોટો અપલોડ કરો:", type=["jpg", "jpeg", "png"], key="c_photo")
        auto_cons = ""
        auto_pin = ""
        if uploaded_photo:
            auto_cons, auto_pin = scan_label_image(uploaded_photo.getvalue())
            if auto_cons or auto_pin:
                st.success(f"🎯 સ્કેન સફળ! બારકોડ: {auto_cons} | પિનકોડ: {auto_pin}")

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

        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="c_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="c_pcs")
        with col5: amount = st.text_input("Total Amount (RS):", key="c_amt")
        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No:", key="c_wa_num")
        c_initial_pay_status = st.selectbox("Payment Status:", ["Paid (ચૂકવાઈ ગયું)", "Unpaid (બાકી)"], key="c_init_status")

        if st.button("💾 Save & Generate Cash Receipt", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("મહેરબાની કરીને જરૂરી ખાના ભરો!")
            else:
                img_bytes = uploaded_photo.getvalue() if uploaded_photo else None
                status_val = "Paid" if "Paid" in c_initial_pay_status else "Unpaid"
                
                data_tuple = (cons_no.strip(), date_entry.strip(), selected_courier.strip(), mode.strip(), origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Cash', None, status_val)
                
                try:
                    save_receipt_to_cloud_and_local(data_tuple, img_bytes)
                    st.success(f"Cash Entry Saved Successfully for Consignment: {cons_no}")
                    sync_two_way()
                    
                    t_url = courier_url_dict.get(selected_courier, "")
                    pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, selected_courier, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash', t_url, img_bytes)
                    st.download_button(label="📄 Download Printable PDF Receipt with Tracking & Photo", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")
                    
                    if c_whatsapp_num.strip():
                        track_link_full = t_url + cons_no if t_url else ""
                        wa_msg = (
                            f"📦 COURIER SOLUTION RECEIPT\n\nConsignment No: {cons_no}\nCourier: {selected_courier}\n"
                            f"To: {rec_name} ({dest})\nAmount: RS {amount}/- [{status_val}]\n"
                            f"{f'Tracking Link: {track_link_full}' if track_link_full else ''}"
                        )
                        wa_url = create_whatsapp_link(c_whatsapp_num.strip(), wa_msg)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Send on WhatsApp</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"ભૂલ આવી: {e}")

    with tab2:
        st.subheader("📜 Cash Booking Records & Date-Wise Total Summary")
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, amount, payment_status, courier_co, mode, origin, dest, sender_address, sender_city, rec_address, rec_city, weight, pcs, parcel_img FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        cash_rows = cursor.fetchall()
        conn.close()
        
        filtered_cash_history = []
        tot_c_amt = 0.0
        for r in cash_rows:
            try:
                if start_date <= datetime.datetime.strptime(r[2], "%d/%m/%Y").date() <= end_date:
                    filtered_cash_history.append(r)
                    tot_c_amt += float(r[5]) if r[5] else 0.0
            except Exception: pass
            
        st.metric("📦 કુલ કેશ બુકિંગ રકમ", f"RS {tot_c_amt:,.2f}/-")
        st.markdown("---")
        if filtered_cash_history:
            for idx, r in enumerate(filtered_cash_history, 1):
                r_id, cons, r_date, s_name, r_name, amt, p_status, c_co, c_mode, orig, destination, s_addr, s_city, r_addr, r_city, wt, pcs, p_img = r
                with st.expander(f"[{idx}] Cons: {cons} | Courier: {c_co} | Date: {r_date} | From: {s_name} ➔ To: {r_name} | RS {amt}/- [{p_status}]"):
                    t_url = courier_url_dict.get(c_co, "")
                    pdf_hist = generate_hd_receipt_pdf(cons, r_date, c_co, c_mode, orig, destination, s_name, s_addr, s_city, r_name, r_addr, r_city, wt, pcs, amt, 'Cash', t_url, p_img)
                    st.download_button("🖨️ Download Receipt PDF with Tracking", data=pdf_hist, file_name=f"Receipt_{cons}.pdf", mime="application/pdf", key=f"dl_cash_hist_{r_id}")

    with tab3:
        st.subheader("🖨️ Re-Print Receipt by Consignment No")
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
                    c_co_name = rec_data[2]
                    t_url = courier_url_dict.get(c_co_name, "")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], c_co_name, rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], t_url, rec_data[16])
                    st.download_button(label="🖨️ Download Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{rec_data[0]}.pdf", mime="application/pdf")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૪. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    tab_cr1, tab_cr2, tab_cr3 = st.tabs(["📋 Credit Booking (નવી એન્ટ્રી)", "🖨️ Re-Print Credit Receipt", "📜 Credit History & View"])
    
    conn_c = get_local_connection()
    cur_c = conn_c.cursor()
    cur_c.execute("SELECT courier_name, tracking_url FROM couriers ORDER BY courier_name ASC")
    courier_master_data = cur_c.fetchall()
    conn_c.close()
    courier_names_list = [c[0] for c in courier_master_data] if courier_master_data else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = {c[0]: c[1] for c in courier_master_data} if courier_master_data else {}

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
            st.warning("⚠️ પહેલા 'Add Account Party' માં જઈને પાર્ટી ઉમેરો!")
        else:
            selected_party = st.selectbox("Select Party Name:", party_names)
            default_s_addr = party_dict[selected_party]["address"] if selected_party in party_dict else ""
            default_s_city = party_dict[selected_party]["city"] if selected_party in party_dict else ""

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
                sender_address = st.text_input("Sender Address:", value=default_s_addr, key=f"cr_s_addr_{selected_party}")
                sender_city = st.text_input("Sender City/Pin:", value=default_s_city, key=f"cr_s_city_{selected_party}")
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
                    data_tuple = (cons_no.strip(), date_entry.strip(), selected_courier.strip(), mode.strip(), origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Credit Account', None, 'Unpaid')
                    try:
                        save_receipt_to_cloud_and_local(data_tuple, cr_img_bytes)
                        st.success(f"Credit Entry Saved for '{selected_party}'")
                        sync_two_way()

                        t_url = courier_url_dict.get(selected_courier, "")
                        pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, selected_courier, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account', t_url, cr_img_bytes)
                        st.download_button(label="🖨️ Download Credit Receipt PDF", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf")
                    except Exception as e:
                        st.error(f"ભૂલ આવી: {e}")

    with tab_cr2:
        st.subheader("🖨️ Re-Print Credit Receipt by Consignment No")
        search_cr_cons = st.text_input("Enter Consignment No to Print:", key="search_cr")
        if st.button("🔍 Search & Print Credit Receipt", type="primary"):
            if search_cr_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img FROM receipts WHERE cons_no=?", (search_cr_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ સફળતાપૂર્વક મળી ગઈ છે!")
                    c_co_name = rec_data[2]
                    t_url = courier_url_dict.get(c_co_name, "")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], c_co_name, rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], t_url, rec_data[16])
                    st.download_button(label="🖨️ Download Printable Receipt (PDF)", data=pdf_bytes, file_name=f"Receipt_{search_cr_cons}.pdf", mime="application/pdf")
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
                    t_url = courier_url_dict.get(c_co, "")
                    pdf_b = generate_hd_receipt_pdf(cons, r_date, c_co, c_mode, orig, destination, party, s_addr, s_city, recip, r_addr, r_city, wt, pcs, amt, 'Credit Account', t_url, p_img)
                    st.download_button("🖨️ Download Receipt PDF", data=pdf_b, file_name=f"Receipt_{cons}.pdf", mime="application/pdf", key=f"dl_pdf_{rec_id}")

# ----------------- ૫. DIGITAL MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ પીડીએફ બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator")
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
        sel_party = st.selectbox("Select Party for Bill:", select_options)
        
        if st.button("📄 Generate Digital PDF Invoice", type="primary"):
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
                cursor.execute("SELECT COUNT(*) FROM bills")
                b_count = cursor.fetchone()[0] + 1
                generated_bill_no = f"BILL-2026-{b_count:03d}"
                cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                              (generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                for item in filtered_bill:
                    cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                conn.commit()
                conn.close()
                sync_two_way()

                pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, f"{start_str} to {end_str}", today.strftime("%d/%m/%Y"), filtered_bill, tot_bill)
                st.success(f"✅ પાર્ટી '{sel_party}' નું બિલ સફળતાપૂર્વક જનરેટ થઈ ગયું છે!")
                st.download_button(label="📄 Download Digital Invoice PDF", data=pdf_bytes, file_name=f"Invoice_{generated_bill_no}_{sel_party}.pdf", mime="application/pdf")
            else:
                conn.close()
                st.info("કોઈ અનબિલ એન્ટ્રી મળી નથી.")

# ----------------- ૬. PARTY PAYMENT RECEIVE -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)":
    st.subheader("💳 Party Payment Receive & Receipt")
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT party_name, mobile FROM parties ORDER BY party_name ASC")
    p_data = cursor.fetchall()
    cursor.execute("SELECT bill_no, party_name, total_amount FROM bills ORDER BY id DESC")
    b_list = cursor.fetchall()
    conn.close()
    bill_options = ["-- Select Bill No --"] + [f"{b[0]} | {b[1]} | RS {b[2]}/-" for b in b_list]
    p_list = [r[0] for r in p_data]
    if not p_list:
        st.warning("⚠️ પહેલા પાર્ટી ઉમેરો!")
    else:
        with st.form("payment_form"):
            selected_bill_opt = st.selectbox("Select Pending Bill No:", bill_options)
            pay_party = st.selectbox("Select Party Name:", p_list)
            pay_date = st.text_input("Payment Date:", value=today.strftime("%d/%m/%Y"))
            pay_amount = st.text_input("Payment Amount (RS):")
            pay_mode = st.selectbox("Payment Mode:", ["Cash (રોકડ)", "UPI (ગૂગલપે/ફોનપે)", "Cheque (ચેક)"])
            pay_note = st.text_input("Note / Reference:")
            
            submit_pay = st.form_submit_button("💾 Save Payment", type="primary")
        if submit_pay and pay_amount.strip():
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
            st.download_button(label="📄 Download Payment Receipt PDF", data=pay_pdf_bytes, file_name=f"Payment_Receipt_{pay_party}.pdf", mime="application/pdf")

# ----------------- ٧. SUMMARY & REPORTS -----------------
elif menu == "📊 Summary & Reports (કેશ & ક્રેડિટ સમરી)":
    st.subheader("📊 Comprehensive Summary & Reports")
    st.info(f"📅 ફિલ્ટર સમયગાળો: **{start_str}** થી **{end_str}**")
    sum_tab1, sum_tab2 = st.tabs(["💵 Cash Summary", "📋 Credit Summary"])
    with sum_tab1:
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, courier_co, sender_name, rec_name, amount, payment_status FROM receipts WHERE booking_type='Cash' ORDER BY id DESC")
        all_cash = cursor.fetchall()
        conn.close()
        tot_cash_amt = sum(float(r[6]) for r in all_cash if r[6])
        st.metric("📦 Total Cash Booking", f"RS {tot_cash_amt:,.2f}/-")
    with sum_tab2:
        conn = get_local_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, cons_no, date, sender_name, rec_name, dest, amount FROM receipts WHERE booking_type='Credit Account' ORDER BY id DESC")
        all_credit = cursor.fetchall()
        conn.close()
        tot_cred_amt = sum(float(r[6]) for r in all_credit if r[6])
        st.metric("📊 Total Credit Booking", f"RS {tot_cred_amt:,.2f}/-")
