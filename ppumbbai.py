import streamlit as st
import pandas as pd
from datetime import date
import os
st.set_page_config(page_title="3뿜빠이 정산기")

st.title("💰 3뿜빠이 정산기")

DATA_FILE = "ppumbbai_data.csv"

if os.path.exists(DATA_FILE):
    st.session_state.records = pd.read_csv(DATA_FILE).to_dict("records")
else:
    st.session_state.records = []

st.subheader("오늘 정산 입력")

input_date = st.date_input("날짜", date.today())

card = st.number_input("카드 매출", min_value=0, step=10000)
cash = st.number_input("현금 매출", min_value=0, step=10000)

if st.button("저장"):

    total = card + cash

    each = (total // 3) // 10000 * 10000
    fund = total - (each * 3)

    st.session_state.records.append({
        "날짜": input_date,
        "카드": card,
        "현금": cash,
        "총금액": total,
        "A": each,
        "B": each,
        "C": each,
        "공금": fund
    })
    pd.DataFrame(st.session_state.records).to_csv(
    DATA_FILE,
    index=False
    )
    st.success("저장 완료")

if st.session_state.records:

    df = pd.DataFrame(st.session_state.records)

    st.subheader("일별 정산 내역")
    st.dataframe(df, use_container_width=True)

    st.subheader("월간 합계")

    total_sales = df["총금액"].sum()
    a_total = df["A"].sum()
    b_total = df["B"].sum()
    c_total = df["C"].sum()
    fund_total = df["공금"].sum()

    st.metric("총매출", f"{total_sales:,}원")
    st.metric("A 누적", f"{a_total:,}원")
    st.metric("B 누적", f"{b_total:,}원")
    st.metric("C 누적", f"{c_total:,}원")
    st.metric("공금 총액", f"{fund_total:,}원")
