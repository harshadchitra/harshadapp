import streamlit as st
import sqlite3
import os
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

# ----------------- HD ઈમેજ જનરેટર -----------------
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

    # Weight, Pcs, Amount
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

# ----------------- મેઈન એપ્લિકેશન યુઝર ઇન્ટરફેસ (Sidebar Navigation) -----------------
st.title("📦 Courier Solution Management")
st.markdown("---")

menu = st.sidebar.selectbox("મેનુ પસંદ કરો (Menu)", ["Cash Booking (રોકડ કુરિયર)", "Credit Account Booking (ક્રેડિટ બુકિંગ)", "Add Account Party (પાર્ટી ઉમેરો)", "Monthly Billing & History (માસિક બિલિંગ)"])

# 1. CASH BOOKING
if menu == "Cash Booking (રોકડ કુરિયર)":
    st.subheader("💵 Cash Courier Booking")
    
    col1, col2 = st.columns(2)
    with col1:
        cons_no = st.text_input("Consignment No:")
        date = st.text_input("Date", value="17/10/2026")
        courier_co = st.text_input("Courier Company", value="DTDC")
        mode = st.text_input("Service Mode", value="Surface")
        origin = st.text_input("Origin", value="B.N.R.")
        dest = st.text_input("Destination")
    with col2:
        sender_name = st.text_input("Sender Name")
        sender_address = st.text_input("Sender Address")
        sender_city = st.text_input("Sender City/Pin")
        rec_name = st.text_input("Recipient Name")
        rec_address = st.text_input("Recipient Address")
        rec_city = st.text_input("Recipient City/Pin")

    col3, col4, col5 = st.columns(3)
    with col3: weight = st.text_input("Weight (Kg)", value="1.0")
    with col4: pcs = st.text_input("Pieces (Pcs)", value="1")
    with col5: amount = st.text_input("Total Amount (RS)")

    if st.button("💾 Save & Generate Receipt", type="primary"):
        if not cons_no or not sender_name or not rec_name or not amount:
            st.error("ਕૃਪਾ ਕਰਕੇ Consignment No, Sender Name, Recipient Name અને Amount ભરો!")
        else:
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash'))
                conn.commit()
                st.success("Cash Booking Successfully Saved!")
                
                # Show Receipt Image
                img = generate_exact_image(cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Cash')
                st.image(img, caption=f"Receipt: {cons_no}", use_container_width=True)
            except sqlite3.IntegrityError:
                st.error("આ Consignment Number પહેલેથી જ અજિસ્ટ છે!")
            conn.close()

# 2. CREDIT ACCOUNT BOOKING
elif menu == "Credit Account Booking (ક્રેડિટ બુકિંગ)":
    st.subheader("📋 Credit Account Courier Booking")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    parties = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not parties:
        st.warning("પહેલા સાઇડબારમાંથી અથવા 'Add Account Party' મેનુમાંથી પાર્ટી ઉમેરો!")
    
    selected_party = st.selectbox("Select Party Name:", parties if parties else ["No Party"])
    
    # Fetch party details
    p_addr, p_city = "", ""
    if parties:
        conn = sqlite3.connect("courier_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT party_address, party_city FROM parties WHERE party_name=?", (selected_party,))
        res = cursor.fetchone()
        conn.close()
        if res: p_addr, p_city = res[0], res[1]

    col1, col2 = st.columns(2)
    with col1:
        cons_no = st.text_input("Consignment No:")
        date = st.text_input("Date", value="17/10/2026")
        courier_co = st.text_input("Courier Company", value="DTDC")
        mode = st.text_input("Service Mode", value="Surface")
        origin = st.text_input("Origin", value="B.N.R.")
        dest = st.text_input("Destination")
    with col2:
        sender_address = st.text_input("Sender Address", value=p_addr)
        sender_city = st.text_input("Sender City/Pin", value=p_city)
        rec_name = st.text_input("Recipient Name")
        rec_address = st.text_input("Recipient Address")
        rec_city = st.text_input("Recipient City/Pin")

    col3, col4, col5 = st.columns(3)
    with col3: weight = st.text_input("Weight (Kg)", value="1.0")
    with col4: pcs = st.text_input("Pieces (Pcs)", value="1")
    with col5: amount = st.text_input("Amount (RS)")

    if st.button("💾 Save Credit Entry", type="primary"):
        if not cons_no or not selected_party or not rec_name or not amount:
            st.error("ਕૃਪਾ ਕਰਕੇ જરૂરી માહિતી ભરો!")
        else:
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO receipts (cons_no, date, courier_co, mode, origin, dest, sender_name, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, booking_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (cons_no, date, courier_co, mode, origin, dest, selected_party, sender_address, sender_city, rec_name, rec_address, rec_city, weight, pcs, amount, 'Credit Account'))
                conn.commit()
                st.success(f"Credit Entry Saved for Party: {selected_party}")
            except sqlite3.IntegrityError:
                st.error("આ Consignment Number પહેલેથી અજિસ્ટ છે!")
            conn.close()

# 3. ADD ACCOUNT PARTY
elif menu == "Add Account Party (પાર્ટી ઉમેરો)":
    st.subheader("➕ Add Monthly Credit Party Master")
    
    p_name = st.text_input("Party Name:")
    p_addr = st.text_input("Party Address:")
    p_city = st.text_input("Party City / Pin:")

    if st.button("Save Party", type="primary"):
        if not p_name:
            st.error("ਕૃਪਾ ਕਰਕੇ પાર્ટીનું નામ લખો!")
        else:
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO parties (party_name, party_address, party_city) VALUES (?, ?, ?)", (p_name, p_addr, p_city))
                conn.commit()
                st.success(f"Party '{p_name}' successfully added!")
            except sqlite3.IntegrityError:
                st.error("આ નામની પાર્ટી પહેલેથી જ અજિસ્ટ છે!")
            conn.close()

# 4. MONTHLY BILLING & HISTORY
elif menu == "Monthly Billing & History (માસિક બિલિંગ)":
    st.subheader("📊 Party Monthly Bill Generator")
    
    conn = sqlite3.connect("courier_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT party_name FROM parties ORDER BY party_name ASC")
    parties = [row[0] for row in cursor.fetchall()]
    conn.close()

    if parties:
        sel_party = st.selectbox("Select Party for Bill:", parties)
        if st.button("Generate Bill"):
            conn = sqlite3.connect("courier_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT cons_no, date, dest, rec_name, weight, amount FROM receipts WHERE sender_name LIKE ? AND booking_type='Credit Account'", (f"%{sel_party}%",))
            rows = cursor.fetchall()
            conn.close()

            if rows:
                total_bill = 0
                table_data = []
                for r in rows:
                    table_data.append({
                        "Consignment": r[0],
                        "Date": r[1],
                        "Destination": r[2],
                        "Recipient": r[3],
                        "Weight": r[4],
                        "Amount (RS)": r[5]
                    })
                    try: total_bill += float(r[5])
                    except: pass
                
                st.table(table_data)
                st.success(f"Total Payable Bill for {sel_party}: RS {total_bill:,.2f}/-")
            else:
                st.info("આ પાર્ટી માટે કોઈ ક્રેડિટ બિલિંગ એન્ટ્રી મળી નથી.")
    else:
        st.warning("કોઈ પાર્ટી એડ કરેલી નથી.")
