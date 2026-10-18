import streamlit as st
import sqlite3
import datetime
import io
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Page Configuration
st.set_page_config(page_title="Courier Solution", page_icon="📦", layout="centered")

# ----------------- ડેટાબેઝ સેટઅપ -----------------
def init_db():
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    
    # રસીપ્ટ ટેબલ
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

    # પાર્ટી માસ્ટર ટેબલ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT UNIQUE,
            party_address TEXT,
            party_city TEXT
        )
    """)

    # પાર્ટી પેમેન્ટ રિસીવ ટેબલ
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

    # મંથલી બિલ રેકોર્ડ ટેબલ
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

# ----------------- PDF INVOICE GENERATOR -----------------
def generate_pdf_invoice(bill_no, party_name, start_str, end_str, bill_date, items, total_amount):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#002147'), alignment=1, spaceAfter=2)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
    invoice_head_style = ParagraphStyle('InvHead', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#d9534f'), alignment=1, spaceAfter=15)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontSize=10, textColor=colors.black, leading=14)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=10, textColor=colors.black, fontName='Helvetica-Bold', leading=14)

    # Header
    story.append(Paragraph("COURIER SOLUTION", title_style))
    story.append(Paragraph("Express Cargo & Logistics Services", sub_title_style))
    story.append(Paragraph("TAX INVOICE / MONTHLY BILL", invoice_head_style))

    # Party & Bill Details Box
    details_data = [
        [
            Paragraph(f"<b>Invoice To:</b><br/><font size=12 color='#002147'><b>{party_name}</b></font><br/>Billing Period: {start_str} to {end_str}", normal_style),
            Paragraph(f"<b>Invoice No:</b> <font color='red'><b>{bill_no}</b></font><br/><b>Date:</b> {bill_date}<br/><b>Status:</b> UNPAID", normal_style)
        ]
    ]
    t_details = Table(details_data, colWidths=[300, 240])
    t_details.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#002147')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_details)
    story.append(Spacer(1, 15))

    # Table Header
    headers = [Paragraph('<b>Sr</b>', bold_style), Paragraph('<b>Consignment No</b>', bold_style), Paragraph('<b>Date</b>', bold_style), Paragraph('<b>Destination</b>', bold_style), Paragraph('<b>Recipient</b>', bold_style), Paragraph('<b>Wt(kg)</b>', bold_style), Paragraph('<b>Amount(RS)</b>', bold_style)]
    data = [headers]

    for idx, r in enumerate(items, 1):
        data.append([
            Paragraph(str(idx), normal_style),
            Paragraph(r[1], normal_style),
            Paragraph(r[2], normal_style),
            Paragraph(r[3], normal_style),
            Paragraph(r[4], normal_style),
            Paragraph(str(r[5]), normal_style),
            Paragraph(f"RS {float(r[6]):,.2f}", normal_style)
        ])

    t_items = Table(data, colWidths=[30, 100, 75, 100, 115, 45, 75])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002147')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 15))

    # Total Amount Box
    total_data = [
        [Paragraph(f"<b>TOTAL PAYABLE AMOUNT:</b>", ParagraphStyle('TotLbl', parent=styles['Normal'], fontSize=12, alignment=2)),
         Paragraph(f"<b>RS {total_amount:,.2f}/-</b>", ParagraphStyle('TotVal', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#008000'), alignment=2))]
    ]
    t_total = Table(total_data, colWidths=[380, 160])
    t_total.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#008000')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_total)
    story.append(Spacer(1, 20))

    # Footer Notes
    story.append(Paragraph("<i>* Subject to Terms & Conditions. Payment due within 7 days.</i>", ParagraphStyle('Foot', parent=styles['Normal'], fontSize=8, textColor=colors.gray)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------- HD PRINTS (BOOKING) -----------------
def generate_exact_image(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type):
    width, height = 1200, 620
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 30)
        font_sub = ImageFont.truetype("arial.ttf", 16)
        font_bold = ImageFont.truetype("arialbd.ttf", 18)
        font_regular = ImageFont.truetype("arial.ttf", 15)
    except:
        font_title = font_sub = font_bold = font_regular = ImageFont.load_default()

    draw.rectangle([10, 10, width-10, height-10], outline="#002147", width=3)
    draw.text((width//2 - 150, 20), "COURIER SOLUTION", fill="#002147", font=font_title)
    draw.text((width//2 - 140, 55), "Express Cargo & Logistics Services", fill="#555555", font=font_sub)
    draw.line([(20, 80), (width-20, 80)], fill="#002147", width=2)

    draw.rectangle([20, 90, width-20, 150], outline="#002147", width=2)
    draw.text((30, 100), f"Consignment No: {cons_no}", fill="red", font=font_bold)
    draw.text((450, 100), f"Date: {date}", fill="black", font=font_bold)
    draw.text((850, 100), f"Courier Co: {courier_co}", fill="blue", font=font_bold)
    draw.text((30, 125), f"Mode: {mode}", fill="black", font=font_regular)
    draw.text((450, 125), f"Origin: {origin}", fill="black", font=font_regular)
    draw.text((850, 125), f"Destination: {dest}", fill="black", font=font_regular)

    # Sender
    draw.rectangle([20, 160, width//2 - 10, 390], outline="#002147", width=2)
    draw.rectangle([20, 160, width//2 - 10, 190], fill="#002147")
    draw.text((width//4 - 70, 165), "SENDER (From)", fill="white", font=font_bold)
    draw.text((30, 205), f"Name: {sender_name}", fill="black", font=font_bold)
    draw.text((30, 240), f"Address: {sender_address}", fill="black", font=font_regular)
    draw.text((30, 280), f"City/Pin: {sender_city}", fill="black", font=font_regular)

    # Recipient
    draw.rectangle([width//2 + 10, 160, width-20, 390], outline="#002147", width=2)
    draw.rectangle([width//2 + 10, 160, width-20, 190], fill="#002147")
    draw.text((3*width//4 - 70, 165), "RECIPIENT (To)", fill="white", font=font_bold)
    draw.text((width//2 + 20, 205), f"Name: {rec_name}", fill="black", font=font_bold)
    draw.text((width//2 + 20, 240), f"Address: {rec_address}", fill="black", font=font_regular)
    draw.text((width//2 + 20, 280), f"City/Pin: {rec_city}", fill="black", font=font_regular)

    # Details
    draw.rectangle([20, 400, width-20, 500], outline="#002147", width=2)
    draw.rectangle([20, 400, width-20, 430], fill="#e6ecf2")
    draw.text((120, 405), "Weight (Kg)", fill="black", font=font_bold)
    draw.text((420, 405), "Quantity (Pcs)", fill="black", font=font_bold)
    draw.text((700, 405), "Total Amount (RS)", fill="black", font=font_bold)
    draw.text((1000, 405), "Type", fill="black", font=font_bold)

    draw.line([(320, 400), (320, 500)], fill="#002147", width=2)
    draw.line([(620, 400), (620, 500)], fill="#002147", width=2)
    draw.line([(900, 400), (900, 500)], fill="#002147", width=2)

    draw.text((120, 450), f"{weight} kg", fill="black", font=font_bold)
    draw.text((420, 450), f"{pcs} Pcs", fill="black", font=font_bold)
    draw.text((700, 450), f"RS {amount}/-", fill="green", font=font_bold)
    draw.text((1000, 450), f"{booking_type}", fill="blue" if booking_type == "Cash" else "purple", font=font_bold)

    draw.text((30, 525), "* Subject to terms & conditions. Goods carried at owner's risk.", fill="black", font=font_sub)
    draw.line([(width-250, 555), (width-50, 555)], fill="black", width=2)
    draw.text((width-220, 565), "Authorized Signatory", fill="black", font=font_bold)

    return img

# ----------------- DASHBOARD UI -----------------
st.title("📦 COURIER SOLUTION")
st.caption("Express Cargo & Logistics Management System")
st.markdown("---")

# SIDEBAR NAVIGATION & FILTER
st.sidebar.header("⚙️ નેવિગેશન & ફિલ્ટર")
menu = st.sidebar.radio("મેનુ પસંદ કરો (Menu)", [
    "➕ Add Account Party (પાર્ટી ઉમેરો)",
    "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)",
    "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)",
    "📊 Party Monthly Billing (ડિજિટલ PDF બિલ)",
    "💳 Party Payment Receive (પેમેન્ટ જમા વિથ બિલ નં)"
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
        submit_p = st.form_submit_button("Save Party", type="primary")

        if submit_p:
            if not p_name.strip():
                st.error("મહેરબાની કરીને Party Name ભરો!")
            else:
                conn = sqlite3.connect("courier_database.db")
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO parties (party_name, party_address, party_city) VALUES (?, ?, ?)", (p_name.strip(), p_addr.strip(), p_city.strip()))
                    conn.commit()
                    st.success(f"પાર્ટી '{p_name}' સફળતાપૂર્વક ઉમેરાઈ ગઈ છે!")
                except sqlite3.IntegrityError:
                    st.error("આ નામની પાર્ટી પહેલેથી જ અસ્તિત્વમાં છે!")
                conn.close()

    st.markdown("---")
    st.write("### 🏢 સેવ થયેલી પાર્ટીઓની યાદી & ડિલીટ:")
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, party_address, party_city FROM parties ORDER BY party_name ASC")
    p_rows = cursor.fetchall()
    conn.close()
    
    if p_rows:
        for r in p_rows:
            col_p1, col_p2 = st.columns([4, 1])
            with col_p1:
                st.write(f"🏢 *{r[1]}* | {r[2]} ({r[3]})")
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
            origin = st.text_input("Origin:", "B.N.R.", key="c_orig")
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
                    
                    img = generate_exact_image(cons_no, date_entry, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash')
                    st.image(img, caption=f"Receipt - {cons_no}", use_container_width=True)
                    
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button(label="🖨️ Download Receipt Image (For Print/WhatsApp)", data=buf.getvalue(), file_name=f"Receipt_{cons_no}.png", mime="image/png")
                except sqlite3.IntegrityError:
                    st.error("આ Consignment Number પહેલેથી જ અસ્તિત્વમાં છે!")
                conn.close()

    with tab2:
        st.subheader("📜 Cash Booking Records & Collection History")
        st.info(f"📅 ફિલ્ટર કરેલી તારીખ ગાળો: *{start_str}* થી *{end_str}*")

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
                    st.write(f"🧾 *Cons: {r[1]}* | Date: {r[2]} | From: {r[3]} ➔ To: {r[4]} | *Amount: RS {r[5]}/-*")
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
                    img = generate_exact_image(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15])
                    st.image(img, caption=f"Receipt - {rec_data[0]}", use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button(label="🖨️ Download Receipt Image", data=buf.getvalue(), file_name=f"Receipt_{rec_data[0]}.png", mime="image/png")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૩. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
    tab_cr1, tab_cr2 = st.tabs(["📋 Credit Booking (નવી એન્ટ્રી)", "🖨️ Re-Print Credit Receipt (ફરીવાર પ્રિન્ટ)"])

    with tab_cr1:
        st.subheader("Credit Account Courier Booking")
        
        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT party_name, party_address, party_city FROM parties ORDER BY party_name ASC")
        parties_data = cursor.fetchall()
        conn.close()

        party_names = [r[0] for r in parties_data]

        if not party_names:
            st.warning("⚠️ પહેલા મેનુમાંથી 'Add Account Party' પસંદ કરીને પાર્ટી ઉમેરો!")
        else:
            selected_party = st.selectbox("Select Party Name (પાર્ટી સિલેક્ટ કરો):", party_names)
            
            def_addr, def_city = "", ""
            for p in parties_data:
                if p[0] == selected_party:
                    def_addr, def_city = p[1], p[2]
                    break

            col1, col2 = st.columns(2)
            with col1:
                cons_no = st.text_input("Consignment No:", key="cr_cons")
                date_entry = st.text_input("Date:", value=today.strftime("%d/%m/%Y"), key="cr_date")
                courier_co = st.text_input("Courier Company:", "DTDC", key="cr_co")
                mode = st.text_input("Service Mode:", "Surface", key="cr_mode")
                origin = st.text_input("Origin:", "B.N.R.", key="cr_orig")
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
                            img = generate_exact_image(cons_no, date_entry, courier_co, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account')
                            st.image(img, caption=f"Credit Receipt - {cons_no}", use_container_width=True)
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            st.download_button(label="🖨️ Download Receipt Image", data=buf.getvalue(), file_name=f"Receipt_{cons_no}.png", mime="image/png")
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
                    img = generate_exact_image(rec_data[0], rec_data[1], rec_data[2], rec_data[3], rec_data[4], rec_data[5], rec_data[6], rec_data[7], rec_data[8], rec_data[9], rec_data[10], rec_data[11], rec_data[12], rec_data[13], rec_data[14], rec_data[15])
                    st.image(img, caption=f"Receipt - {rec_data[0]}", use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button(label="🖨️ Download Receipt Image", data=buf.getvalue(), file_name=f"Receipt_{rec_data[0]}.png", mime="image/png")
                else:
                    st.error("આ કન્સાઇનમેન્ટ નંબરની કોઈ એન્ટ્રી મળી નથી!")

# ----------------- ૪. DIGITAL MONTHLY BILLING (PDF INVOICE) -----------------
elif menu == "📊 Party Monthly Billing (ડિજિટલ PDF બિલ)":
    st.subheader("📊 Party Digital PDF Invoice Generator")
    st.info(f"📅 પસંદ કરેલ બિલિંગ સમયગાળો: *{start_str}* થી *{end_str}*")

    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    p_list = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) FROM bills")
    b_count = cursor.fetchone()[0] + 1
    generated_bill_no = f"BILL-2026-{b_count:03d}"
    conn.close()

    if not p_list:
        st.warning("કોઈ પાર્ટી ઉમેરેલી નથી.")
    else:
        col_b1, col_b2 = st.columns([2, 1])
        with col_b1:
            sel_party = st.selectbox("Select Party for Bill (બિલ બનાવવાની પાર્ટી પસંદ કરો):", p_list)
        with col_b2:
            st.text_input("Generated Bill No (ઓટો બિલ નંબર):", value=generated_bill_no, disabled=True)

        if st.button("📄 Generate & Create Digital PDF Invoice", type="primary"):
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, cons_no, date, dest, rec_name, weight, amount FROM receipts WHERE sender_name=? AND booking_type='Credit Account' ORDER BY id DESC", (sel_party,))
            b_rows = cursor.fetchall()

            filtered_bill = []
            tot_bill = 0

            for r in b_rows:
                rec_date_str = r[2]
                try:
                    rec_dt = datetime.datetime.strptime(rec_date_str, "%d/%m/%Y").date()
                    if start_date <= rec_dt <= end_date:
                        filtered_bill.append(r)
                        tot_bill += float(r[6])
                except:
                    filtered_bill.append(r)
                    try: tot_bill += float(r[6])
                    except: pass

            if filtered_bill:
                # Save Bill DB
                try:
                    cursor.execute("INSERT INTO bills (bill_no, party_name, bill_date, period, total_amount) VALUES (?, ?, ?, ?, ?)",
                                   (generated_bill_no, sel_party, today.strftime("%d/%m/%Y"), f"{start_str} to {end_str}", str(tot_bill)))
                    for item in filtered_bill:
                        cursor.execute("UPDATE receipts SET bill_no=? WHERE id=?", (generated_bill_no, item[0]))
                    conn.commit()
                except:
                    pass
                conn.close()

                # Generate PDF
                pdf_bytes = generate_pdf_invoice(generated_bill_no, sel_party, start_str, end_str, today.strftime("%d/%m/%Y"), filtered_bill, tot_bill)

                st.success(f"✅ પાર્ટી '{sel_party}' નું બિલ સફળતાપૂર્વક જનરેટ થઈ ગયું છે!")
                
                st.download_button(
                    label="📄 Download Digital Invoice PDF (પીડીએફ ડાઉનલોડ કરો)",
                    data=pdf_bytes,
                    file_name=f"Invoice_{generated_bill_no}_{sel_party}.pdf",
                    mime="application/pdf"
                )

                # Screen Preview Table
                table_data = []
                for idx, r in enumerate(filtered_bill, 1):
                    table_data.append({
                        "Sr No": idx,
                        "Consignment No": r[1],
                        "Date": r[2],
                        "Destination": r[3],
                        "Recipient": r[4],
                        "Weight (Kg)": r[5],
                        "Amount (RS)": f"₹ {float(r[6]):,.2f}"
                    })
                
                st.table(table_data)
                st.metric("Total Payable Bill Amount", f"RS {tot_bill:,.2f}/-")
            else:
                conn.close()
                st.info(f"પાર્ટી '{sel_party}' માટે પસંદ કરેલી તારીખો વચ્ચે કોઈ ક્રેડિટ બુકિંગ મળેલ નથી.")

# ----------------- ૫. PARTY PAYMENT RECEIVE WITH BILL NO -----------------
elif menu == "💳 Party Payment Receive (પેમેન્ટ જમા વિથ બિલ નં)":
    st.subheader("💳 Party Payment Receive (બિલ નંબરથી પેમેન્ટ જમા લો)")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    p_list = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT bill_no, party_name, total_amount FROM bills ORDER BY id DESC")
    b_list = cursor.fetchall()
    conn.close()

    bill_options = ["-- Select Bill No (બિલ નં પસંદ કરો) --"] + [f"{b[0]} | {b[1]} | RS {b[2]}/-" for b in b_list]

    if not p_list:
        st.warning("⚠️ પહેલા મેનુમાંથી 'Add Account Party' પસંદ કરીને પાર્ટી ઉમેરો!")
    else:
        with st.form("payment_form", clear_on_submit=True):
            selected_bill_opt = st.selectbox("Select Bill No for Payment (જે બિલનું પેમેન્ટ આવ્યુ હોય તે બિલ નં પસંદ કરો):", bill_options)
            pay_party = st.selectbox("Select Party Name (પાર્ટીનું નામ):", p_list)
            pay_date = st.text_input("Payment Date (તારીખ):", value=today.strftime("%d/%m/%Y"))
            pay_amount = st.text_input("Payment Amount (જમા થયેલ રકમ RS):")
            pay_mode = st.selectbox("Payment Mode (પેમેન્ટ મોડ):", ["Cash (રોકડ)", "UPI (ગૂગલપે/โฟનપે)", "Cheque (ચેક)"])
            pay_note = st.text_input("Note / Cheque No / Reference (નોંધ):")
            
            submit_pay = st.form_submit_button("💾 Save Payment Receive (જમા કરો)", type="primary")

            if submit_pay:
                if not pay_amount.strip():
                    st.error("મહેરબાની કરીને જમા લેવાની રકમ ભરો!")
                else:
                    target_bill_no = selected_bill_opt.split(" | ")[0] if "-- Select" not in selected_bill_opt else "DIRECT"
                    
                    conn = sqlite3.connect("courier_database.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO party_payments (party_name, bill_no, date, amount, pay_mode, note)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (pay_party.strip(), target_bill_no, pay_date.strip(), pay_amount.strip(), pay_mode, pay_note.strip()))
                    conn.commit()
                    conn.close()
                    st.success(f"પાર્ટી '{pay_party}' માટે (બિલ નં: {target_bill_no}) RS {pay_amount}/- જમા થઈ ગયા છે! ({pay_mode})")

        st.markdown("---")
        st.subheader("📜 Party Payment History (જમા થયેલા પેમેન્ટની હિસ્ટ્રી)")
        
        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, party_name, bill_no, date, amount, pay_mode, note FROM party_payments ORDER BY id DESC")
        pay_rows = cursor.fetchall()
        conn.close()

        if pay_rows:
            tot_received = 0
            for r in pay_rows:
                col_py1, col_py2 = st.columns([4, 1])
                with col_py1:
                    st.write(f"🏢 *{r[1]}* | Bill No: <span style='color:red;'><b>{r[2]}</b></span> | Date: {r[3]} | *RS {r[4]}/-* ({r[5]}) {f'| Note: {r[6]}' if r[6] else ''}", unsafe_allow_html=True)
                    try: tot_received += float(r[4])
                    except: pass
                with col_py2:
                    if st.button("🗑️ Delete", key=f"del_pay_{r[0]}"):
                        conn = sqlite3.connect("courier_database.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM party_payments WHERE id=?", (r[0],))
                        conn.commit()
                        conn.close()
                        st.success("પેમેન્ટ એન્ટ્રી ડિલીટ થઈ ગઈ છે!")
                        st.rerun()
            st.metric("💰 Total Payment Received", f"RS {tot_received:,.2f}/-")
        else:
            st.info("કોઈ પેમેન્ટ રિસીવ રેકોર્ડ મળેલ નથી.")
