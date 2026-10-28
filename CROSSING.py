import streamlit as st
import pandas as pd
import datetime
import io
import urllib.parse
import re
import requests
import json
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

# ----------------- 🔄 ગૂગલ એપ્સ સ્ક્રિપ્ટ ક્લાઉડ કનેક્શન -----------------
WEB_APP_URL = "https://script.google.com/macros/s/AKfycby96uy9MqY8rKeIMSdnNRvVLcRkwcI6vAZI6KrEJLi4yVzhrTuea8tO-lrzRzuw1l8u3g/exec"

def get_google_sheet_data(sheet_name):
    try:
        url = f"{WEB_APP_URL}?sheet={sheet_name}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        print("Read Error:", e)
        return pd.DataFrame()

def save_to_google_sheet(sheet_name, row_data, headers_list):
    try:
        payload = {
            "sheet": sheet_name,
            "headers": headers_list,
            "row": row_data
        }
        response = requests.post(WEB_APP_URL, json=payload)
        return response.status_code == 200
    except Exception as e:
        print("Save Error:", e)
        return False

# ક્લાઉડ શીટમાંથી ડેટા રીડ કરવા માટેના ફંક્શન્સ
def get_courier_data():
    return get_google_sheet_data("Courier_Entries")

def get_parties_data():
    return get_google_sheet_data("Parties")

def get_couriers_data():
    df = get_google_sheet_data("Couriers")
    if df is not None and not df.empty:
        return df
    return pd.DataFrame([
        {"Courier Name": "DTDC", "Tracking URL": "https://www.dtdc.in/tracking/shipment-tracking.asp?strCnno="},
        {"Courier Name": "Delhivery", "Tracking URL": "https://www.delhivery.com/track/package/"},
        {"Courier Name": "Trackon", "Tracking URL": "https://trackon.in/track?awb="}
    ])

def get_packing_receipts_data():
    return get_google_sheet_data("Packing_Receipts")

def get_party_payments_data():
    return get_google_sheet_data("Party_Payments")

def get_bills_data():
    return get_google_sheet_data("Bills")

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

def create_whatsapp_link(phone_num, msg_text):
    clean_phone = ''.join(filter(str.isdigit, str(phone_num)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_text = urllib.parse.quote(msg_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

def generate_hd_receipt_pdf(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, tracking_url="", img_bytes=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    f_header_title = ParagraphStyle('HTitle', fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=colors.HexColor('#002147'))
    f_header_sub = ParagraphStyle('HSub', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#333333'))
    f_label_sm = ParagraphStyle('LblSm', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black)
    f_val_lg = ParagraphStyle('ValLg', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.black)
    f_val_huge = ParagraphStyle('ValHuge', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.black)
    f_val_green = ParagraphStyle('ValGreen', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor('#008000'))
    f_footer = ParagraphStyle('Foot', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#444444'))
    
    barcode_obj = code128.Code128(str(cons_no), barHeight=28, barWidth=1.4)
    
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
    
    row4_data = [
        [Paragraph("Pieces", f_label_sm), Paragraph("Weight", f_label_sm), Paragraph("Total Amount", f_label_sm)],
        [
            Paragraph(f"<b>{pcs} Pcs</b>", f_val_huge),
            Paragraph(f"<b>{weight} Kg</b>", f_val_huge),
            Paragraph(f"<b>RS {amount}/-</b>", f_val_green)
        ]
    ]
    t_row4 = Table(row4_data, colWidths=[150, 150, 245])
    t_row4.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F0F4F8')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(t_header)
    story.append(Spacer(1, 4))
    story.append(t_row2)
    story.append(Spacer(1, 4))
    story.append(t_row3)
    story.append(Spacer(1, 4))
    story.append(t_row4)
    story.append(Spacer(1, 6))
    
    full_track_link = tracking_url + str(cons_no) if tracking_url else ""
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
    
    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Cons No</b>', bold_style), Paragraph('<b>Date</b>', bold_style), Paragraph('<b>Courier</b>', bold_style), Paragraph('<b>Dest</b>', bold_style), Paragraph('<b>Recipient</b>', bold_style), Paragraph('<b>Amount</b>', bold_style)]
    data = [headers]
    for idx, r in enumerate(items, 1):
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(str(r.get('Tracking Number', '')), normal_style),
            Paragraph(str(r.get('Date', '')), normal_style),
            Paragraph(str(r.get('Courier Co', 'DTDC')), bold_style),
            Paragraph(str(r.get('Destination', '')), normal_style),
            Paragraph(str(r.get('Receiver Name', '')), normal_style),
            Paragraph(f"RS {float(r.get('Amount', 0)):,.2f}", normal_style)
        ])
    t_items = Table(data, colWidths=[25, 95, 65, 75, 85, 115, 80])
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
st.caption("Express Cargo & Logistics Management System (Google Apps Script API Mode)")
st.markdown("---")

# SIDEBAR NAVIGATION
st.sidebar.header("⚙️ નેવિગેશન & ફિલ્ટર")
menu = st.sidebar.radio("મેનુ પસંદ કરો (Menu)", [
    "➕ Add Account Party (પાર્ટી ઉમેરો)",
    "🚚 Add Courier Master (કુરિયર અને ટ્રેકિંગ URL ઉમેરો)",
    "💵 Cash Courier Booking (કેશ બુકિંગ)",
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
    df_parties = get_parties_data()

    with st.form("party_form"):
        st.write("### 📝 પાર્ટી ફોર્મ")
        p_name = st.text_input("Party Name:")
        p_addr = st.text_input("Address:")
        p_city = st.text_input("City / Pin Code:")
        p_mob = st.text_input("WhatsApp Mobile No:")
        
        submit_p = st.form_submit_button("💾 Save Party", type="primary")
        if submit_p:
            if not p_name.strip():
                st.error("પાર્ટીનું નામ ભરો!")
            else:
                headers = ["Party Name", "Address", "City", "Mobile"]
                row_vals = [p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip()]
                save_to_google_sheet("Parties", row_vals, headers)
                st.success(f"પાર્ટી '{p_name}' ગૂગલ શીટમાં સેવ થઈ ગઈ છે!")
                st.rerun()

    st.markdown("---")
    st.write("### 🏢 સેવ થયેલી પાર્ટીઓની યાદી:")
    if not df_parties.empty:
        st.dataframe(df_parties, use_container_width=True)
    else:
        st.info("કોઈ પાર્ટી ઉમેરેલી નથી.")

# ----------------- ૨. COURIER MASTER -----------------
elif menu == "🚚 Add Courier Master (કુરિયર અને ટ્રેકિંગ URL ઉમેરો)":
    st.subheader("🚚 Courier Master & Tracking URL Management")
    df_couriers = get_couriers_data()

    with st.form("courier_form"):
        c_name_input = st.text_input("Courier Company Name (દા.ત. DTDC, Delhivery):")
        c_url_input = st.text_input("Tracking Base URL:")
        submit_courier = st.form_submit_button("💾 Save Courier", type="primary")
        if submit_courier and c_name_input.strip() and c_url_input.strip():
            headers = ["Courier Name", "Tracking URL"]
            row_vals = [c_name_input.strip(), c_url_input.strip()]
            save_to_google_sheet("Couriers", row_vals, headers)
            st.success("કુરિયર ગૂગલ શીટમાં સેવ થઈ ગયું છે!")
            st.rerun()

    st.markdown("---")
    if not df_couriers.empty:
        st.dataframe(df_couriers, use_container_width=True)

# ----------------- ૩. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ)":
    tab1, tab2, tab3 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History", "🖨️ Re-Print Receipt"])
    
    df_couriers = get_couriers_data()
    courier_names_list = df_couriers["Courier Name"].tolist() if not df_couriers.empty else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = dict(zip(df_couriers["Courier Name"], df_couriers["Tracking URL"])) if not df_couriers.empty else {}

    with tab1:
        st.subheader("Cash Courier Booking")
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

        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="c_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="c_pcs")
        with col5: amount = st.text_input("Total Amount (RS):", key="c_amt")
        
        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No:", key="c_wa_num")
        c_initial_pay_status = st.selectbox("Payment Status:", ["Paid (ચૂકવાઈ ગયું)", "Unpaid (બાકી)"], key="c_init_status")

        if st.button("💾 Save & Generate Receipt", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("જરૂરી ખાના ભરો!")
            else:
                img_bytes = uploaded_photo.getvalue() if uploaded_photo else None
                status_val = "Paid" if "Paid" in c_initial_pay_status else "Unpaid"
                
                headers = [
                    "Date", "Tracking Number", "Courier Co", "Mode", "Origin", "Destination", 
                    "Sender Name", "Sender Address", "Sender City", "Receiver Name", "Receiver Address", 
                    "Receiver City", "Weight", "Pcs", "Amount", "Booking Type", "Bill No", 
                    "Payment Status", "Packing Info", "Packing Charge"
                ]
                row_vals = [
                    date_entry, str(cons_no).strip(), selected_courier.strip(), mode.strip(), 
                    origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), 
                    sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), 
                    str(weight).strip(), str(pcs).strip(), str(amount).strip(), 'Cash', "", status_val, "None", "0"
                ]
                
                save_to_google_sheet("Courier_Entries", row_vals, headers)
                st.success(f"✅ કેશ બુકિંગ ગૂગલ શીટમાં સેવ થઈ ગયું છે!")
                
                t_url = courier_url_dict.get(selected_courier, "")
                pdf_bytes = generate_hd_receipt_pdf(
                    cons_no, date_entry, selected_courier, mode, origin, dest, sender_name, 
                    sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, 
                    str(amount).strip(), 'Cash', t_url, img_bytes
                )
                st.download_button(label="📄 Download Printable PDF Receipt", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")

    with tab2:
        st.subheader("📜 Cash Booking Records")
        df_courier = get_courier_data()
        if not df_courier.empty and "Booking Type" in df_courier.columns:
            cash_df = df_courier[df_courier["Booking Type"] == "Cash"]
            if not cash_df.empty:
                st.dataframe(cash_df, use_container_width=True)
            else:
                st.info("કોઈ કેશ એન્ટ્રી નથી.")
        else:
            st.info("કોઈ ડેટા નથી.")

    with tab3:
        st.subheader("🖨️ Re-Print Receipt by Consignment No")
        search_cons = st.text_input("Enter Consignment No:")
        if st.button("🔍 Search & Print", type="primary"):
            if search_cons.strip():
                df_courier = get_courier_data()
                if not df_courier.empty and "Tracking Number" in df_courier.columns:
                    matched = df_courier[df_courier["Tracking Number"].astype(str) == search_cons.strip()]
                    if not matched.empty:
                        rec = matched.iloc[0]
                        st.success("રસીદ મળી ગઈ છે!")
                        c_co_name = rec.get("Courier Co", "DTDC")
                        t_url = courier_url_dict.get(c_co_name, "")
                        pdf_bytes = generate_hd_receipt_pdf(
                            str(rec["Tracking Number"]), str(rec["Date"]), c_co_name, str(rec.get("Mode", "Surface")), 
                            str(rec.get("Origin", "")), str(rec.get("Destination", "")), str(rec.get("Sender Name", "")), 
                            str(rec.get("Sender Address", "")), str(rec.get("Sender City", "")), str(rec.get("Receiver Name", "")), 
                            str(rec.get("Receiver Address", "")), str(rec.get("Receiver City", "")), str(rec.get("Weight", "1")), 
                            str(rec.get("Pcs", "1")), str(rec.get("Amount", "0")), str(rec.get("Booking Type", "Cash")), t_url, None
                        )
                        st.download_button(label="🖨️ Download PDF", data=pdf_bytes, file_name=f"Receipt_{search_cons}.pdf", mime="application/pdf", type="primary")
                    else:
                        st.error("કોઈ એન્ટ્રી મળી નથી!")
                else:
                    st.error("ડેટાબેઝ ખાલી છે!")

# ----------------- ૪. SEPARATE PACKING SERVICE -----------------
elif menu == "📦 Separate Packing Service (અલગ પેકિંગ સર્વિસ રિસીપ્ટ)":
    st.subheader("📦 Separate Packing Service & Material Billing")
    
    cust_name = st.text_input("Customer Name:", key="sep_cust_name")
    cust_mob = st.text_input("Mobile No:", key="sep_cust_mob")
    pack_date = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="sep_pack_date")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        item_box = st.checkbox("Box Packing")
        item_tape = st.checkbox("Cellotape")
    with col_p2:
        item_bag = st.checkbox("Online Bag")
        item_other = st.checkbox("Other Material")

    custom_items_desc = st.text_input("Custom Details / Notes:", key="sep_custom_desc")
    total_pack_charge = st.text_input("Total Packing Charge (RS):", "50", key="sep_total_charge")

    if st.button("💾 Save & Generate Packing Receipt", type="primary", key="sep_save_btn"):
        if not cust_name.strip() or not total_pack_charge.strip():
            st.error("નામ અને ચાર્જ ભરો!")
        else:
            selected_items = []
            if item_box: selected_items.append("Box Packing")
            if item_tape: selected_items.append("Cellotape")
            if item_bag: selected_items.append("Online Bag")
            if item_other: selected_items.append("Other")
            if custom_items_desc: selected_items.append(custom_items_desc)
            items_str = ", ".join(selected_items) if selected_items else "General Packing"

            df_packs = get_packing_receipts_data()
            p_count = len(df_packs) + 1
            rec_no = f"PACK-REC-{p_count:04d}"

            headers = ["Receipt No", "Date", "Customer Name", "Mobile", "Packing Items", "Total Charge"]
            row_vals = [rec_no, pack_date.strip(), cust_name.strip(), cust_mob.strip(), items_str, str(total_pack_charge).strip()]
            save_to_google_sheet("Packing_Receipts", row_vals, headers)
            st.success(f"પેકિંગ રિસીપ્ટ ગૂગલ શીટમાં સેવ થઈ ગઈ છે! [Receipt No: {rec_no}]")
            
            pdf_pack_bytes = generate_packing_pdf_receipt(rec_no, pack_date, cust_name, cust_mob, items_str, total_pack_charge)
            st.download_button(label="📄 Download Packing Receipt PDF", data=pdf_pack_bytes, file_name=f"Packing_Receipt_{rec_no}.pdf", mime="application/pdf", type="primary", key="dl_sep_pack_pdf")

    st.markdown("---")
    st.subheader("📜 Previous Packing Receipts History")
    df_packs = get_packing_receipts_data()
    if not df_packs.empty:
        st.dataframe(df_packs, use_container_width=True)
    else:
        st.info("કોઈ પેકિંગ રિસીપ્ટ એન્ટ્રી નથી.")

# ----------------- ૫. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    st.subheader("Credit Account Booking")
    df_parties = get_parties_data()
    df_couriers = get_couriers_data()
    
    party_names = df_parties["Party Name"].tolist() if not df_parties.empty and "Party Name" in df_parties.columns else []
    party_dict = df_parties.set_index("Party Name").to_dict(orient="index") if not df_parties.empty and "Party Name" in df_parties.columns else {}
    courier_names_list = df_couriers["Courier Name"].tolist() if not df_couriers.empty and "Courier Name" in df_couriers.columns else ["DTDC", "Delhivery", "Trackon"]
    courier_url_dict = dict(zip(df_couriers["Courier Name"], df_couriers["Tracking URL"])) if not df_couriers.empty and "Courier Name" in df_couriers.columns else {}

    if not party_names:
        st.warning("⚠️ પહેલા પાર્ટી ઉમેરો!")
    else:
        selected_party = st.selectbox("Select Party Name:", party_names)
        p_info = party_dict.get(selected_party, {"Address": "", "City": "", "Mobile": ""})

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
            sender_address = st.text_input("Sender Address:", value=p_info.get("Address", ""), key=f"cr_s_addr_{selected_party}")
            sender_city = st.text_input("Sender City/Pin:", value=p_info.get("City", ""), key=f"cr_s_city_{selected_party}")
            rec_name = st.text_input("Recipient Name:", key="cr_r_name")
            rec_address = st.text_input("Recipient Address:", key="cr_r_addr")
            rec_city = st.text_input("Recipient City/Pin:", value=cr_auto_pin, key="cr_r_city")
        
        col3, col4, col5 = st.columns(3)
        with col3: weight = st.text_input("Weight (Kg):", "1.0", key="cr_wt")
        with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="cr_pcs")
        with col5: amount = st.text_input("Amount (RS):", key="cr_amt")
        
        if st.button("💾 Save Credit Booking to Cloud", type="primary"):
            if not cons_no or not rec_name or not amount:
                st.error("બધી માહિતી ભરો!")
            else:
                cr_img_bytes = cr_uploaded_photo.getvalue() if cr_uploaded_photo else None
                
                headers = [
                    "Date", "Tracking Number", "Courier Co", "Mode", "Origin", "Destination", 
                    "Sender Name", "Sender Address", "Sender City", "Receiver Name", "Receiver Address", 
                    "Receiver City", "Weight", "Pcs", "Amount", "Booking Type", "Bill No", 
                    "Payment Status", "Packing Info", "Packing Charge"
                ]
                row_vals = [
                    date_entry, str(cons_no).strip(), selected_courier.strip(), mode.strip(), 
                    origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), 
                    sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), 
                    str(weight).strip(), str(pcs).strip(), str(amount).strip(), 'Credit Account', "", 'Unpaid', "None", "0"
                ]
                
                save_to_google_sheet("Courier_Entries", row_vals, headers)
                st.success(f"✅ ક્રેડિટ બુકિંગ ગૂગલ શીટમાં સેવ થઈ ગયું છે!")
                
                t_url = courier_url_dict.get(selected_courier, "")
                pdf_bytes = generate_hd_receipt_pdf(
                    cons_no, date_entry, selected_courier, mode, origin, dest, selected_party, 
                    sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, 
                    str(amount).strip(), 'Credit Account', t_url, cr_img_bytes
                )
                st.download_button(label="🖨️ Download Credit Receipt PDF", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")

# ----------------- ૬. MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ પીડીએફ બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator")
    df_parties = get_parties_data()
    p_list = df_parties["Party Name"].tolist() if not df_parties.empty and "Party Name" in df_parties.columns else []
    
    if not p_list:
        st.warning("કોઈ પાર્ટી નથી.")
    else:
        sel_party = st.selectbox("Select Party for Bill:", p_list)
        if st.button("📄 Generate Digital PDF Invoice", type="primary"):
            df_courier = get_courier_data()
            if not df_courier.empty and "Sender Name" in df_courier.columns:
                b_rows_df = df_courier[(df_courier["Sender Name"] == sel_party) & (df_courier["Booking Type"] == "Credit Account") & ((df_courier["Bill No"] == "") | (df_courier["Bill No"].isna()))]
                if not b_rows_df.empty:
                    df_bills = get_bills_data()
                    b_count = len(df_bills) + 1
                    generated_bill_no = f"BILL-2026-{b_count:03d}"
                    tot_bill = sum(float(x) for x in b_rows_df["Amount"] if x)

                    headers_b = ["Bill No", "Party Name", "Bill Date", "Period", "Total Amount"]
                    row_vals_b = [generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)]
                    save_to_google_sheet("Bills", row_vals_b, headers_b)

                    items_list = b_rows_df.to_dict(orient="records")
                    pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, f"{start_str} to {end_str}", today.strftime("%d/%m/%Y"), items_list, tot_bill)
                    st.success("બિલ સફળતાપૂર્વક બની ગયું છે!")
                    st.download_button(label="📄 Download Invoice PDF", data=pdf_bytes, file_name=f"Invoice_{generated_bill_no}.pdf", mime="application/pdf", type="primary")
                else:
                    st.info("કોઈ અનબિલ એન્ટ્રી નથી.")
            else:
                st.info("કોઈ એન્ટ્રી નથી.")

# ----------------- ૭. PAYMENT RECEIVE -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા & રસીદ)":
    st.subheader("💳 Party Payment Receive")
    df_parties = get_parties_data()
    p_list = df_parties["Party Name"].tolist() if not df_parties.empty and "Party Name" in df_parties.columns else []
    
    if p_list:
        with st.form("pay_form"):
            pay_party = st.selectbox("Party Name:", p_list)
            pay_amt = st.text_input("Amount Received (RS):")
            pay_mode = st.selectbox("Mode:", ["Cash", "UPI", "Cheque"])
            sub = st.form_submit_button("Save Payment", type="primary")
        if sub and pay_amt.strip():
            df_pays = get_party_payments_data()
            rec_id = len(df_pays) + 1
            headers_p = ["Party Name", "Bill No", "Date", "Amount", "Pay Mode", "Note"]
            row_vals_p = [pay_party, "DIRECT", today.strftime("%d/%m/%Y"), str(pay_amt).strip(), pay_mode, ""]
            save_to_google_sheet("Party_Payments", row_vals_p, headers_p)
            st.success("પેમેન્ટ જમા થઈ ગયું!")
            pdf_b = generate_payment_pdf_receipt(rec_id, pay_party, "DIRECT", today.strftime("%d/%m/%Y"), pay_amt, pay_mode, "")
            st.download_button("Download Receipt", data=pdf_b, file_name=f"Pay_{rec_id}.pdf", mime="application/pdf", type="primary")

# ----------------- ૮. SUMMARY -----------------
elif menu == "📊 Summary & Reports (કેશ & ક્રેડિટ સમરી)":
    st.subheader("📊 Summary & Reports")
    df_courier = get_courier_data()
    df_packs = get_packing_receipts_data()

    c_sum = sum(float(x) for x in df_courier[df_courier["Booking Type"] == "Cash"]["Amount"]) if not df_courier.empty and "Booking Type" in df_courier.columns else 0.0
    cr_sum = sum(float(x) for x in df_courier[df_courier["Booking Type"] == "Credit Account"]["Amount"]) if not df_courier.empty and "Booking Type" in df_courier.columns else 0.0
    p_sum = sum(float(x) for x in df_packs["Total Charge"]) if not df_packs.empty and "Total Charge" in df_packs.columns else 0.0

    st.metric("📦 Total Cash Bookings", f"RS {c_sum:,.2f}/-")
    st.metric("📋 Total Credit Bookings", f"RS {cr_sum:,.2f}/-")
    st.metric("📦 Separate Packing Receipts Total", f"RS {p_sum:,.2f}/-")
