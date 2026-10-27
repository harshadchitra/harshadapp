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

# ----------------- 🔄 ડેટાબેઝ સેટઅપ -----------------
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
            parcel_img BLOB,
            payment_status TEXT DEFAULT 'Unpaid'
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE receipts ADD COLUMN parcel_img BLOB")
        conn.commit()
    except Exception:
        pass

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

init_db()

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
        
        lconn.commit()
        scur.close()
        sconn.close()
        lconn.close()
    except Exception:
        pass

if 'synced' not in st.session_state:
    sync_two_way()
    st.session_state['synced'] = True

# ----------------- ફોટો સાથે સેવ કરવાનું પરફેક્ટ ફંક્શન -----------------
def save_receipt_with_image(data_tuple, img_bytes):
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, parcel_img, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple + (img_bytes,))
    conn.commit()
    conn.close()

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

# ----------------- 100% ફોટો સાથે PDF રીસીપ્ટ જનરેટર -----------------
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
    
    # 🌟 અહીં ફોટો પરફેક્ટ રીતે રિસીપ્ટમાં સેટ કર્યો છે
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

# ----------------- ડેશબોર્ડ UI -----------------
st.title("📦 COURIER SOLUTION")
st.caption("Express Cargo & Logistics Management System")
st.markdown("---")

menu = st.sidebar.radio("મેનુ પસંદ કરો (Menu)", [
    "➕ Add Account Party (પાર્ટી ઉમેરો)",
    "💵 Cash Courier Booking (કેશ બુકિંગ & રીપ્રિન્ટ)",
    "📋 Credit Account Booking (ક્રેડિટ બુકિંગ & રીપ્રિન્ટ)"
])

# ----------------- ૧. ADD PARTY -----------------
if menu == "➕ Add Account Party (પાર્ટી ઉમેરો)":
    st.subheader("➕ Add & Manage Monthly Account Parties")
    with st.form("party_form"):
        p_name = st.text_input("Party Name (પાર્ટીનું નામ):")
        p_addr = st.text_input("Address (સરનામું):")
        p_city = st.text_input("City / Pin Code (શહેર / પીનકોડ):")
        p_mob = st.text_input("WhatsApp Mobile No (મોબાઈલ નંબર):")
        submit_p = st.form_submit_button("💾 Save Party", type="primary")
        if submit_p and p_name.strip():
            conn = get_local_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO parties (party_name, party_address, party_city, mobile) VALUES (?, ?, ?, ?)", 
                              (p_name.strip(), p_addr.strip(), p_city.strip(), p_mob.strip()))
                conn.commit()
                st.success(f"પાર્ટી '{p_name}' સેવ થઈ ગઈ છે!")
            except Exception:
                st.error("આ નામની પાર્ટી પહેલેથી જ અસ્તિત્વમાં છે!")
            conn.close()

# ----------------- ૨. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & રીપ્રિન્ટ)":
    tab1, tab2 = st.tabs(["💵 Cash Booking & Print (નવી એન્ટ્રી & પ્રિન્ટ)", "🖨️ Re-Print Receipt with Photo (ફોટો સાથે રીપ્રિન્ટ)"])
    with tab1:
        st.subheader("Cash Courier Booking")
        uploaded_photo = st.file_uploader("📷 પાર્સલ/લેબલનો ફોટો અપલોડ કરો:", type=["jpg", "jpeg", "png"], key="c_photo")
        
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
        c_whatsapp_num = st.text_input("Customer WhatsApp Mobile No:", key="c_wa_num")
        c_initial_pay_status = st.selectbox("Payment Status:", ["Paid (ચૂકવાઈ ગયું)", "Unpaid (બાકી)"], key="c_init_status")

        if st.button("💾 Save & Generate Receipt with Photo", type="primary"):
            if not cons_no or not sender_name or not rec_name or not amount:
                st.error("મહેરબાની કરીને જરૂરી ખાના ભરો!")
            else:
                img_bytes = uploaded_photo.getvalue() if uploaded_photo else None
                status_val = "Paid" if "Paid" in c_initial_pay_status else "Unpaid"
                
                data_tuple = (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), sender_name.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Cash', status_val)
                
                try:
                    # 🌟 ડેટાબેઝમાં ફોટો સાથે ડાયરેક્ટ સેવ કરો
                    save_receipt_with_image(data_tuple, img_bytes)
                    st.success(f"Cash Entry Saved with Photo for Consignment: {cons_no}")
                    
                    pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash', img_bytes)
                    st.download_button(label="📄 Download Printable PDF Receipt with Photo", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")
                    
                    if c_whatsapp_num.strip():
                        wa_msg = f"📦 COURIER SOLUTION\nConsignment No: {cons_no}\nTo: {rec_name} ({dest})\nAmount: RS {amount}/- [{status_val}]"
                        wa_url = create_whatsapp_link(c_whatsapp_num.strip(), wa_msg)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;margin-top:10px;">📲 Send on WhatsApp</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"ભૂલ આવી: {e}")

    with tab2:
        st.subheader("🖨️ Re-Print Receipt with Photo by Consignment No")
        search_cons = st.text_input("Enter Consignment No to Print:", key="search_cons_cash")
        if st.button("🔍 Search & Print Receipt with Photo", type="primary", key="btn_search_cash"):
            if search_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, payment_status, parcel_img FROM receipts WHERE cons_no=?", (search_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ અને ફોટો સફળતાપૂર્વક મળી ગયા છે!")
                    # ડેટાબેઝમાંથી ફોટો (parcel_img) પણ સાથે પાસ કર્યો છે
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], rec_data[17])
                    st.download_button(label=f"🖨️ Download Printable Receipt with Photo [{rec_data[0]}]", data=pdf_bytes, file_name=f"Receipt_{rec_data[0]}.pdf", mime="application/pdf", type="primary")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૩. CREDIT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ બુકિંગ & રીપ્રિન્ટ)":
    tab_cr1, tab_cr2 = st.tabs(["📋 Credit Booking & Print", "🖨️ Re-Print Credit Receipt with Photo"])
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
            
            col1, col2 = st.columns(2)
            with col1:
                cons_no = st.text_input("Consignment No:", key="cr_cons")
                date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="cr_date")
                courier_co = st.text_input("Courier Company:", "DTDC", key="cr_co")
                mode = st.text_input("Service Mode:", "Surface", key="cr_mode")
                origin = st.text_input("Origin:", "BHAVNAGAR", key="cr_orig")
                dest = st.text_input("Destination:", key="cr_dest")
            with col2:
                sender_address = st.text_input("Sender Address:", value=default_s_addr, key=f"cr_s_addr_{selected_party}")
                sender_city = st.text_input("Sender City/Pin:", value=default_s_city, key=f"cr_s_city_{selected_party}")
                rec_name = st.text_input("Recipient Name:", key="cr_r_name")
                rec_address = st.text_input("Recipient Address:", key="cr_r_addr")
                rec_city = st.text_input("Recipient City/Pin:", key="cr_r_city")
            
            col3, col4, col5 = st.columns(3)
            with col3: weight = st.text_input("Weight (Kg):", "1.0", key="cr_wt")
            with col4: pcs = st.text_input("Pieces (Pcs):", "1", key="cr_pcs")
            with col5: amount = st.text_input("Amount (RS):", key="cr_amt")
            
            if st.button("💾 Save & Print Credit Receipt with Photo", type="primary"):
                if not cons_no or not rec_name or not amount:
                    st.error("મહેરબાની કરીને બધી માહિતી ભરો!")
                else:
                    cr_img_bytes = cr_uploaded_photo.getvalue() if cr_uploaded_photo else None
                    data_tuple = (cons_no.strip(), date_entry.strip(), courier_co.strip(), mode.strip(), origin.strip(), dest.strip(), selected_party.strip(), sender_address.strip(), sender_city.strip(), rec_name.strip(), rec_address.strip(), rec_city.strip(), weight.strip(), pcs.strip(), amount.strip(), 'Credit Account', 'Unpaid')
                    try:
                        save_receipt_with_image(data_tuple, cr_img_bytes)
                        st.success(f"Credit Entry Saved with Photo for '{selected_party}'")

                        pdf_bytes = generate_hd_receipt_pdf(cons_no, date_entry, courier_co, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account', cr_img_bytes)
                        st.download_button(label="🖨️ Download Credit Receipt PDF with Photo", data=pdf_bytes, file_name=f"Receipt_{cons_no}.pdf", mime="application/pdf", type="primary")
                    except Exception as e:
                        st.error(f"ભૂલ આવી: {e}")

    with tab_cr2:
        st.subheader("🖨️ Re-Print Credit Receipt with Photo by Consignment No")
        search_cr_cons = st.text_input("Enter Consignment No to Print:", key="search_cr")
        if st.button("🔍 Search & Print Credit Receipt with Photo", type="primary", key="btn_search_cr"):
            if search_cr_cons.strip():
                conn = get_local_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type, payment_status, parcel_img FROM receipts WHERE cons_no=?", (search_cr_cons.strip(),))
                rec_data = cursor.fetchone()
                conn.close()
                if rec_data:
                    st.success("રસીદ અને ફોટો સફળતાપૂર્વક મળી ગયા છે!")
                    pdf_bytes = generate_hd_receipt_pdf(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15], rec_data[17])
                    st.download_button(label=f"🖨️ Download HD Printable Receipt with Photo [{search_cr_cons}]", data=pdf_bytes, file_name=f"Receipt_{search_cr_cons}.pdf", mime="application/pdf", type="primary")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")
