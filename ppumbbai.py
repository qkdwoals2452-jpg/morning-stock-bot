import streamlit as st
import pandas as pd
from datetime import date
import requests

st.set_page_config(page_title="3뿜빠이 정산기")
st.title("💰 3뿜빠이 정산기")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def api_get(table):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&order=id.asc"
    r = requests.get(url, headers=HEADERS)
    return r.json() if r.status_code == 200 else []

def api_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    return requests.post(url, headers=HEADERS, json=data)

def api_update(table, row_id, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    return requests.patch(url, headers=HEADERS, json=data)

def api_delete(table, row_id):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    return requests.delete(url, headers=HEADERS)

settings = api_get("ppumbbai_settings")

if settings:
    default_a = settings[0]["name_a"]
    default_b = settings[0]["name_b"]
    default_c = settings[0]["name_c"]
else:
    default_a = "A"
    default_b = "B"
    default_c = "C"

st.subheader("오늘 정산 입력")

input_date = st.date_input("날짜", date.today())
a_card = st.number_input(f"{default_a} 카드", min_value=0, step=10000)
b_card = st.number_input(f"{default_b} 카드", min_value=0, step=10000)
c_card = st.number_input(f"{default_c} 카드", min_value=0, step=10000)
cash_total = st.number_input("현금 총액", min_value=0, step=10000)

if st.button("저장"):
    total = a_card + b_card + c_card + cash_total
    each = (total // 3) // 10000 * 10000

    a_cash = max(0, each - a_card)
    b_cash = max(0, each - b_card)
    c_cash = max(0, each - c_card)

    paid_cash = a_cash + b_cash + c_cash
    fund = max(0, cash_total - paid_cash)

    api_insert("ppumbbai_data", {
        "date": str(input_date),
        "a_card": a_card,
        "b_card": b_card,
        "c_card": c_card,
        "cash_total": cash_total,
        "a_cash": a_cash,
        "b_cash": b_cash,
        "c_cash": c_cash,
        "total": total,
        "a_total": each,
        "b_total": each,
        "c_total": each,
        "fund": fund
    })

    st.success("저장 완료")
    st.rerun()

records = api_get("ppumbbai_data")

if records:
    df = pd.DataFrame(records)

    df = df.rename(columns={
        "id": "id",
        "date": "날짜",
        "a_card": "A카드",
        "b_card": "B카드",
        "c_card": "C카드",
        "cash_total": "현금총액",
        "a_cash": "A현금지급",
        "b_cash": "B현금지급",
        "c_cash": "C현금지급",
        "total": "총금액",
        "a_total": "A",
        "b_total": "B",
        "c_total": "C",
        "fund": "공금"
    })

    df["날짜"] = pd.to_datetime(df["날짜"])
    month_list = sorted(df["날짜"].dt.strftime("%Y-%m").unique(), reverse=True)
    selected_month = st.selectbox("조회 월 선택", month_list)

    df = df[df["날짜"].dt.strftime("%Y-%m") == selected_month]
    df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d")

    view_df = df.drop(columns=["id", "created_at"], errors="ignore")

    st.subheader("일별 정산 내역")
    st.dataframe(view_df, use_container_width=True)

    latest = df.iloc[-1]

    st.subheader("오늘 현금 분배 결과")
    st.metric("총매출", f"{int(latest['총금액']):,}원")
    st.metric("1인 목표금액", f"{int(latest['A']):,}원")

    st.text(f"{default_a} 현금 지급: {int(latest['A현금지급']):,}원")
    st.text(f"{default_b} 현금 지급: {int(latest['B현금지급']):,}원")
    st.text(f"{default_c} 현금 지급: {int(latest['C현금지급']):,}원")

    st.metric("공금", f"{int(latest['공금']):,}원")

    st.subheader("기록 수정")

    edit_idx = st.number_input(
        "수정할 행 번호",
        min_value=0,
        max_value=len(df) - 1,
        step=1,
        key="edit_idx"
    )

    edit_a_card = st.number_input("수정 A 카드", min_value=0, step=10000, key="edit_a_card")
    edit_b_card = st.number_input("수정 B 카드", min_value=0, step=10000, key="edit_b_card")
    edit_c_card = st.number_input("수정 C 카드", min_value=0, step=10000, key="edit_c_card")
    edit_cash_total = st.number_input("수정 현금 총액", min_value=0, step=10000, key="edit_cash_total")

    if st.button("수정 저장"):
        row_id = int(df.iloc[edit_idx]["id"])

        total = edit_a_card + edit_b_card + edit_c_card + edit_cash_total
        each = (total // 3) // 10000 * 10000

        a_cash = max(0, each - edit_a_card)
        b_cash = max(0, each - edit_b_card)
        c_cash = max(0, each - edit_c_card)

        paid_cash = a_cash + b_cash + c_cash
        fund = max(0, edit_cash_total - paid_cash)

        api_update("ppumbbai_data", row_id, {
            "a_card": edit_a_card,
            "b_card": edit_b_card,
            "c_card": edit_c_card,
            "cash_total": edit_cash_total,
            "a_cash": a_cash,
            "b_cash": b_cash,
            "c_cash": c_cash,
            "total": total,
            "a_total": each,
            "b_total": each,
            "c_total": each,
            "fund": fund
        })

        st.success("수정 완료")
        st.rerun()

    st.subheader("기록 삭제")

    delete_idx = st.number_input(
        "삭제할 행 번호",
        min_value=0,
        max_value=len(df) - 1,
        step=1,
        key="delete_idx"
    )

    if st.button("선택 기록 삭제"):
        row_id = int(df.iloc[delete_idx]["id"])
        api_delete("ppumbbai_data", row_id)
        st.rerun()

    st.subheader("이름 설정")

    name_a = st.text_input("A 이름", default_a)
    name_b = st.text_input("B 이름", default_b)
    name_c = st.text_input("C 이름", default_c)

    if st.button("이름 저장"):
        api_update("ppumbbai_settings", 1, {
            "name_a": name_a,
            "name_b": name_b,
            "name_c": name_c
        })
        st.success("이름 저장 완료")
        st.rerun()

    st.subheader("월간 합계")

    total_sales = df["총금액"].sum()
    a_total = df["A"].sum()
    b_total = df["B"].sum()
    c_total = df["C"].sum()
    fund_total = df["공금"].sum()

    st.metric("총매출", f"{int(total_sales):,}원")
    st.metric(f"{name_a} 누적", f"{int(a_total):,}원")
    st.metric(f"{name_b} 누적", f"{int(b_total):,}원")
    st.metric(f"{name_c} 누적", f"{int(c_total):,}원")
    st.metric("공금 총액", f"{int(fund_total):,}원")

else:
    st.info("아직 저장된 정산 내역이 없습니다.")
