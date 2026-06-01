import streamlit as st
import requests
import base64
from bs4 import BeautifulSoup
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

THEME_DB = {

"HBM": [
    "SK하이닉스(000660)",
    "한미반도체(042700)",
    "테크윙(089030)",
    "이오테크닉스(039030)"
],
"2차전지": [
    "에코프로(086520)",
    "포스코퓨처엠(003670)",
    "LG에너지솔루션(373220)",
    "삼성SDI(006400)"
],
"동박": [
    "롯데에너지머티리얼즈(020150)",
    "솔루스첨단소재(336370)",
    "SKC(011790)"
],
"CCL": [
    "롯데에너지머티리얼즈(020150)",
    "코리아써키트(007810)"
],
"유리기판": [
    "SKC(011790)",
    "필옵틱스(161580)"
],
"전고체": [
    "이수스페셜티케미컬(457190)",
    "레이크머티리얼즈(281740)"
],
"PCB": [
    "삼성전기(009150)",
    "대덕전자(353200)",
    "심텍(222800)"
],
"MLCC": [
    "삼성전기(009150)",
    "삼화콘덴서(001820)"
],
"전력": [
    "효성중공업(298040)",
    "LS ELECTRIC(010120)",
    "산일전기(062040)"
],
"전력기기": [
    "효성중공업(298040)",
    "LS ELECTRIC(010120)",
    "산일전기(062040)"
],
"전선": [
    "가온전선(000500)",
    "대한전선(001440)"
],
"원전": [
    "두산에너빌리티(034020)",
    "한전기술(052690)",
    "한전KPS(051600)"
],
"태양광": [
    "한화솔루션(009830)",
    "OCI홀딩스(010060)"
],
"로봇": [
    "레인보우로보틱스(277810)",
    "두산로보틱스(454910)"
],
"우주항공": [
    "한국항공우주(047810)",
    "한화에어로스페이스(012450)"
],
"자율주행": [
    "현대모비스(012330)",
    "HL만도(204320)"
],
"방산": [
    "한화에어로스페이스(012450)",
    "LIG넥스원(079550)"
],
"바이오": [
    "삼성바이오로직스(207940)",
    "셀트리온(068270)"
],
"엔터": [
    "하이브(352820)",
    "JYP Ent.(035900)"
],
"게임": [
    "크래프톤(259960)",
    "엔씨소프트(036570)"
]

}
st.set_page_config(page_title="신문기사 공부장", page_icon="📰")

st.title("📰 신문기사 공부장")
st.write("신문 스크랩 사진, 네이버 기사 URL, 기사 내용 붙여넣기 모두 가능합니다.")

uploaded_images = st.file_uploader(
    "신문기사 사진 업로드",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

url = st.text_input("네이버 기사 URL")
title = st.text_input("기사 제목")
article = st.text_area("기사 내용 붙여넣기", height=300)


def get_naver_article(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    title_tag = soup.select_one("#title_area span")
    content_tag = soup.select_one("#dic_area")

    article_title = title_tag.get_text(strip=True) if title_tag else ""
    article_content = content_tag.get_text("\n", strip=True) if content_tag else ""

    return article_title, article_content


def analyze_text(final_title, final_article):
    prompt = f"""
너는 경제신문을 쉽게 설명해주는 한국 주식 전문가다.

아래 기사 내용을 분석해서 다음 형식으로 정리해줘.

[기사 제목]
{final_title}

[기사 내용]
{final_article}

정리 형식:

1. 기사 내용 정리
- 기사 전체 흐름 설명
- 핵심 내용 자세히 정리
- 신문기사 읽듯 자연스럽게 설명

2. 핵심 포인트 3가지

3. 초보자용 쉬운 설명

4. 어려운 용어 설명
- 용어:
- 뜻:

5. 왜 중요한 기사인가?

6. 한국 증시에 미칠 영향

7. 관련 테마

8. 기사 기반 관련 종목 분석

※ 미리 저장된 종목 DB를 참고하지 말고 기사 내용을 기반으로 직접 추론할 것.

- 대장주
- 직접 수혜주
- 후발주
- 장비주
- 소재주

각 종목마다 왜 관련주인지 설명

예시

대장주:
삼성전자

직접 수혜주:
한미반도체
테크윙

장비주:
주성엔지니어링
원익IPS

소재주:
ISC

이유:
HBM4 생산 확대 과정에서 패키징, 테스트, 증착, 검사 장비 수요 증가 예상

9. 투자자가 주의할 점

10. 블로그 제목 5개

11. 내가 외워야 할 한 문장
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content


def analyze_image(uploaded_image):
    image_bytes = uploaded_image.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
너는 한국 주식 투자자를 위한 경제신문 해설 전문가다.

첨부된 이미지는 사용자가 공부하려고 올린 경제신문 기사 스크랩이다.
이미지 속 글자를 가능한 범위에서 읽고, 원문 전체를 그대로 복사하지 말고 핵심 내용을 요약·해설해줘.

중요:
- 기사 원문을 길게 그대로 베끼지 말 것
- 이미지 속 기사 내용을 바탕으로 핵심만 정리할 것
- 읽기 어려운 부분은 추정하지 말고 "확인 어려움"이라고 표시할 것
- 한국 주식 투자자 관점에서 설명할 것

정리 형식:

1. 기사 내용 정리
- 기사 전체 흐름 설명
- 핵심 내용 자세히 정리
- 신문기사 읽듯 자연스럽게 설명

2. 핵심 포인트 3가지

3. 초보자용 쉬운 설명

4. 어려운 용어 설명
- 용어:
- 뜻:

5. 왜 중요한 기사인가?

6. 한국 증시에 미칠 영향

7. 관련 테마

8. 관련 종목
- 대장주
- 후발주
- 이유

9. 투자자가 주의할 점

10. 블로그 제목 5개

11. 내가 외워야 할 한 문장
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
    )

    return response.choices[0].message.content

if st.button("분석하기"):

    with st.spinner("분석 중입니다..."):

        if uploaded_images and len(uploaded_images) > 0:
            for idx, uploaded_image in enumerate(uploaded_images, start=1):
                st.subheader(f"📌 기사 사진 {idx} 분석")
                result = analyze_image(uploaded_image)
                st.markdown(result)
                st.divider()
            st.stop()

        final_title = title
        final_article = article

        if url:
            try:
                final_title, final_article = get_naver_article(url)
            except Exception:
                st.error("기사 URL을 읽지 못했습니다. 기사 내용을 직접 붙여넣어 주세요.")
                st.stop()

        if final_article == "":
            st.warning("기사 사진, 기사 URL, 기사 내용 중 하나를 입력해주세요.")
            st.stop()

        result = analyze_text(final_title, final_article)

        st.markdown(result)

        theme_result = ""

        for theme, stocks in THEME_DB.items():

            if theme.lower() in result.lower():

                theme_result += f"\n\n🔥 {theme}\n"

                for stock in stocks:
                    theme_result += f"- {stock}\n"

        if theme_result:

            st.markdown("## 📈 내 DB 기준 관련주")
            st.markdown(theme_result)
