import streamlit as st
import sqlite3
import datetime
import io
from PIL import Image, ImageDraw, ImageFont

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
            booking_type TEXT
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
    conn.commit()
    conn.close()

init_db()

# ----------------- HD પ્રિન્ટેબલ ઈમેજ ફંક્શન -----------------
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

    # Sender (મોકલનાર)
    draw.rectangle([20, 160, width//2 - 10, 390], outline="#002147", width=2)
    draw.rectangle([20, 160, width//2 - 10, 190], fill="#002147")
    draw.text((width//4 - 70, 165), "SENDER (From)", fill="white", font=font_bold)
    draw.text((30, 205), f"Name: {sender_name}", fill="black", font=font_bold)
    draw.text((30, 240), f"Address: {sender_address}", fill="black", font=font_regular)
    draw.text((30, 280), f"City/Pin: {sender_city}", fill="black", font=font_regular)

    # Recipient (મેળવનાર)
    draw.rectangle([width//2 + 10, 160, width-20, 390], outline="#002147", width=2)
    draw.rectangle([width//2 + 10, 160, width-20, 190], fill="#002147")
    draw.text((3*width//4 - 70, 165), "RECIPIENT (To)", fill="white", font=font_bold)
    draw.text((width//2 + 20, 205), f"Name: {rec_name}", fill="black", font=font_bold)
    draw.text((width//2 + 20, 240), f"Address: {rec_address}", fill="black", font=font_regular)
    draw.text((width//2 + 20, 280), f"City/Pin: {rec_city}", fill="black", font=font_regular)

    # Weight, Quantity, Amount, Type
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
    "📊 Party Monthly Billing (માસિક બિલ બનાવટ)"
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
    st.write("### 🏢 હાલમાં સેવ થયેલી પાર્ટીઓની યાદી:")
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, party_name, party_address, party_city FROM parties ORDER BY party_name ASC")
    p_rows = cursor.fetchall()
    conn.close()
    if p_rows:
        p_list = [{"ID": r[0], "Party Name": r[1], "Address": r[2], "City": r[3]} for r in p_rows]
        st.dataframe(p_list, use_container_width=True)

# ----------------- ૨. CASH BOOKING -----------------
elif menu == "💵 Cash Courier Booking (કેશ બુકિંગ & હિસ્ટ્રી)":
    tab1, tab2 = st.tabs(["💵 Cash Booking (નવી એન્ટ્રી)", "📜 Cash History & Collection (હિસ્ટ્રી)"])

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
                    filtered_cash.append({"ID": r[0], "Consignment": r[1], "Date": r[2], "Sender": r[3], "Recipient": r[4], "Amount (RS)": r[5]})
                    tot_cash += float(r[5])
            except:
                # જો તારીખ ફોર્મેટ મેચ ન થાય તો બાય ડિફોલ્ટ બતાવવું
                filtered_cash.append({"ID": r[0], "Consignment": r[1], "Date": r[2], "Sender": r[3], "Recipient": r[4], "Amount (RS)": r[5]})
                try: tot_cash += float(r[5])
                except: pass

        if filtered_cash:
            st.dataframe(filtered_cash, use_container_width=True)
            st.metric("💰 Selected Period Cash Collection", f"RS {tot_cash:,.2f}/-")
        else:
            st.warning("આ પસંદ કરેલી તારીખ ગાળામાં કોઈ કેશ બુકિંગ એન્ટ્રી મળી નથી.")

# ----------------- ૩. CREDIT ACCOUNT BOOKING -----------------
elif menu == "📋 Credit Account Booking (ક્રેડિટ એકાઉન્ટ બુકિંગ)":
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

# ----------------- ૪. MONTHLY BILLING -----------------
elif menu == "📊 Party Monthly Billing (માસિક બિલ બનાવટ)":
    st.subheader("📊 Party Monthly Bill Generator")
    st.info(f"📅 પસંદ કરેલ બિલિંગ સમયગાળો: *{start_str}* થી *{end_str}* (સાઇડબારમાંથી તારીખ બદલી શકો છો)")

    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    p_list = [r[0] for r in cursor.fetchall()]
    conn.close()

    if not p_list:
        st.warning("કોઈ પાર્ટી ઉમેરેલી નથી.")
    else:
        sel_party = st.selectbox("Select Party for Bill (બિલ બનાવવાની પાર્ટી પસંદ કરો):", p_list)
        if st.button("Generate Monthly Bill", type="primary"):
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT cons_no, date, dest, rec_name, weight, amount FROM receipts WHERE sender_name=? AND booking_type='Credit Account'", (sel_party,))
            b_rows = cursor.fetchall()
            conn.close()

            filtered_bill = []
            tot_bill = 0

            for r in b_rows:
                rec_date_str = r[1]
                try:
                    rec_dt = datetime.datetime.strptime(rec_date_str, "%d/%m/%Y").date()
                    if start_date <= rec_dt <= end_date:
                        filtered_bill.append({"Consignment": r[0], "Date": r[1], "Destination": r[2], "Recipient": r[3], "Weight": r[4], "Amount (RS)": r[5]})
                        tot_bill += float(r[5])
                except:
                    filtered_bill.append({"Consignment": r[0], "Date": r[1], "Destination": r[2], "Recipient": r[3], "Weight": r[4], "Amount (RS)": r[5]})
                    try: tot_bill += float(r[5])
                    except: pass

            if filtered_bill:
                st.write(f"### 📄 Monthly Bill Statement for: *{sel_party}* ({start_str} to {end_str})")
                st.dataframe(filtered_bill, use_container_width=True)
                st.success(f"💰 Total Monthly Payable Bill for '{sel_party}': RS {tot_bill:,.2f}/-")
            else:
                st.info(f"પાર્ટી '{sel_party}' માટે પસંદ કરેલી તારીખો વચ્ચે કોઈ ક્રેડિટ બુકિંગ મળેલ નથી.")
