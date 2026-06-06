import streamlit as st
import pandas as pd
from datetime import date
import os

st.set_page_config(page_title="3뿜빠이 정산기")
st.title("💰 3뿜빠이 정산기")

DATA_FILE = "ppumbbai_data_v2.csv"
SETTING_FILE = "ppumbbai_settings.csv"
if os.path.exists(SETTING_FILE):
    settings = pd.read_csv(SETTING_FILE)
    default_a = settings.loc[0, "A"]
    default_b = settings.loc[0, "B"]
    default_c = settings.loc[0, "C"]
else:
    default_a = "A"
    default_b = "B"
    default_c = "C"
try:
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        st.session_state.records = pd.read_csv(DATA_FILE).to_dict("records")
    else:
        st.session_state.records = []
except:
    st.session_state.records = []

st.subheader("오늘 정산 입력")

input_date = st.date_input("날짜", date.today())
a_card = st.number_input("A 카드", min_value=0, step=10000)
b_card = st.number_input("B 카드", min_value=0, step=10000)
c_card = st.number_input("C 카드", min_value=0, step=10000)

cash_total = st.number_input("현금 총액", min_value=0, step=10000)

if st.button("저장"):
    total = a_card + b_card + c_card + cash_total

    each = (total // 3) // 10000 * 10000
    fund = total - (each * 3)

    a_cash = max(0, each - a_card)
    b_cash = max(0, each - b_card)
    c_cash = max(0, each - c_card)

    st.session_state.records.append({
        "날짜": input_date,
        "A카드": a_card,
        "B카드": b_card,
        "C카드": c_card,
        "현금총액": cash_total,

        "A현금지급": a_cash,
        "B현금지급": b_cash,
        "C현금지급": c_cash,
        "총금액": total,
        "A": each,
        "B": each,
        "C": each,
        "공금": fund
    })

    pd.DataFrame(st.session_state.records).to_csv(DATA_FILE, index=False)
    st.success("저장 완료")
    st.rerun()

if st.session_state.records:
    df = pd.DataFrame(st.session_state.records)
    df["날짜"] = pd.to_datetime(df["날짜"])

    month_list = sorted(
        df["날짜"].dt.strftime("%Y-%m").unique(),
        reverse=True
    )

    selected_month = st.selectbox("조회 월 선택", month_list)

    df = df[df["날짜"].dt.strftime("%Y-%m") == selected_month]
    df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d")

    st.subheader("일별 정산 내역")
    st.dataframe(df, use_container_width=True)
    latest = df.iloc[-1]

    st.subheader("오늘 현금 분배 결과")

    total_money = int(latest["총금액"])
    target_money = int(latest["A"])
    a_pay = int(latest["A현금지급"])
    b_pay = int(latest["B현금지급"])
    c_pay = int(latest["C현금지급"])
    fund_money = int(latest["공금"])

    st.metric("총매출", f"{total_money:,}원")
    st.metric("1인 목표금액", f"{target_money:,}원")

st.text("A 현금 지급: " + str(a_pay) + "원")
st.text("B 현금 지급: " + str(b_pay) + "원")
st.text("C 현금 지급: " + str(c_pay) + "원")

st.metric("공금", f"{fund_money:,}원")

st.subheader("기록 수정")

    edit_idx = st.number_input(
        "수정할 행 번호",
        min_value=0,
        max_value=len(df)-1,
        step=1,
        key="edit_idx"
    )

    edit_a_card = st.number_input(
        "수정 A 카드",
        min_value=0,
        step=10000,
        key="edit_a_card"
    )

    edit_b_card = st.number_input(
        "수정 B 카드",
        min_value=0,
        step=10000,
        key="edit_b_card"
    )

    edit_c_card = st.number_input(
        "수정 C 카드",
        min_value=0,
        step=10000,
        key="edit_c_card"
    )

    edit_cash_total = st.number_input(
        "수정 현금 총액",
        min_value=0,
        step=10000,
        key="edit_cash_total"
    )

    if st.button("수정 저장"):
        total = edit_a_card + edit_b_card + edit_c_card + edit_cash_total

        each = (total // 3) // 10000 * 10000
        fund = total - (each * 3)

        a_cash = each - edit_a_card
        b_cash = each - edit_b_card
        c_cash = each - edit_c_card

        st.session_state.records[edit_idx]["A카드"] = edit_a_card
        st.session_state.records[edit_idx]["B카드"] = edit_b_card
        st.session_state.records[edit_idx]["C카드"] = edit_c_card
        st.session_state.records[edit_idx]["현금총액"] = edit_cash_total
        st.session_state.records[edit_idx]["A현금지급"] = a_cash
        st.session_state.records[edit_idx]["B현금지급"] = b_cash
        st.session_state.records[edit_idx]["C현금지급"] = c_cash
        st.session_state.records[edit_idx]["총금액"] = total
        st.session_state.records[edit_idx]["A"] = each
        st.session_state.records[edit_idx]["B"] = each
        st.session_state.records[edit_idx]["C"] = each
        st.session_state.records[edit_idx]["공금"] = fund

        pd.DataFrame(st.session_state.records).to_csv(DATA_FILE, index=False)

        st.success("수정 완료")
        st.rerun()
        st.subheader("기록 삭제")

        delete_idx = st.number_input(
            "삭제할 행 번호",
            min_value=0,
            max_value=len(df)-1,
            step=1
        )

        if st.button("선택 기록 삭제"):
            st.session_state.records.pop(delete_idx)
            pd.DataFrame(st.session_state.records).to_csv(DATA_FILE, index=False)
            st.rerun()

    st.subheader("이름 설정")

    name_a = st.text_input("A 이름", default_a)
    name_b = st.text_input("B 이름", default_b)
    name_c = st.text_input("C 이름", default_c)

    if st.button("이름 저장"):
        pd.DataFrame([{
            "A": name_a,
            "B": name_b,
            "C": name_c
        }]).to_csv(
            SETTING_FILE,
            index=False
        )

        st.success("이름 저장 완료")

    st.subheader("월간 합계")

    total_sales = df["총금액"].sum()
    a_total = df["A"].sum()
    b_total = df["B"].sum()
    c_total = df["C"].sum()
    fund_total = df["공금"].sum()

    st.metric("총매출", f"{total_sales:,}원")
    st.metric(f"{name_a} 누적", f"{a_total:,}원")
    st.metric(f"{name_b} 누적", f"{b_total:,}원")
    st.metric(f"{name_c} 누적", f"{c_total:,}원")
    st.metric("공금 총액", f"{fund_total:,}원")



