import streamlit as st
import requests
import base64
from bs4 import BeautifulSoup
from openai import OpenAI

st.set_page_config(page_title="신문기사 공부장 v2", page_icon="📰")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("📰 신문기사 공부장 v2")
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
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    title_tag = soup.select_one("#title_area span")
    content_tag = soup.select_one("#dic_area")

    article_title = title_tag.get_text(strip=True) if title_tag else ""
    article_content = content_tag.get_text("\n", strip=True) if content_tag else ""

    return article_title, article_content


def make_prompt(title="", article="", is_image=False):
    image_instruction = ""
    if is_image:
        image_instruction = """
첨부 이미지는 경제신문 기사 스크랩이다.
이미지 속 글자를 가능한 범위에서 읽고 분석해라.
읽기 어려운 부분은 억지로 만들지 말고 "확인 어려움"이라고 표시해라.
"""

    return f"""
너는 한국 주식 투자자를 위한 경제신문 해설 전문가다.

{image_instruction}

아래 기사 내용을 한국 개인투자자 관점에서 쉽게 설명해라.
이 답변은 투자 공부용이며, 매수·매도 추천이 아니라 관련 산업과 종목 후보를 정리하는 목적이다.

[기사 제목]
{title}

[기사 내용]
{article}

절대 규칙:
- 관련 종목은 반드시 한국거래소(KRX)에 상장된 한국 종목만 제시한다.
- 해외 종목은 관련 종목 목록에 절대 넣지 않는다.
- 엔비디아, AMD, 마이크론, TSMC, ASML, 램리서치, KLA, 퀄컴, 인텔 등 해외 기업은 고객사/경쟁사 설명에서만 언급 가능하다.
- 해외 종목을 관련 종목에 포함하면 오답이다.
- 특정 종목을 암기처럼 반복하지 말고, 기사 핵심 산업과 밸류체인을 보고 직접 추론한다.
- 단순히 "반도체 기사니까 반도체주"처럼 넓게 잡지 말고, 기사 핵심 키워드의 직접 수혜 밸류체인을 우선 고려한다.
- 제조사 → 장비 → 소재 → 부품 → 검사 → 테스트 → 고객사 순으로 연결해서 생각한다.
- 기사에 직접 등장하지 않아도 산업 밸류체인상 수혜 가능성이 있으면 제시한다.
- 동일 기사군이라도 매번 같은 종목을 반복하지 말고, 현재 기사 내용에 가장 가까운 종목을 우선 선정한다.

정리 형식:

1. 기사 내용 정리
- 기사 전체 흐름
- 핵심 내용
- 신문기사 읽듯 자연스럽게 설명

2. 핵심 포인트 3가지

3. 초보자용 쉬운 설명

4. 어려운 용어 설명
- 용어:
- 뜻:

5. 왜 중요한 기사인가?

6. 한국 증시에 미칠 영향

7. 관련 테마

8. 기사 기반 국내 관련 종목 분석
- 국내 대장주 1개
- 국내 직접 수혜주 3~5개
- 국내 후발주 3~5개
- 국내 장비주 3~5개
- 국내 소재주 3~5개
- 각 종목마다 왜 관련주인지 1줄 설명

9. GPT가 가장 유력하게 보는 국내 종목 TOP5
- 한국 상장 종목만 제시
- 선정 이유 1줄

10. 투자자가 주의할 점

11. 블로그 제목 5개

12. 내가 외워야 할 한 문장
"""


def analyze_text(final_title, final_article):
    prompt = make_prompt(final_title, final_article, is_image=False)

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

    prompt = make_prompt(
        title="신문 스크랩 이미지",
        article="첨부 이미지 속 경제신문 기사를 읽고 분석해줘.",
        is_image=True
    )

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
                        }
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content


if st.button("분석하기"):

    with st.spinner("분석 중입니다..."):

        if uploaded_images and len(uploaded_images) > 0:
            for idx, uploaded_image in enumerate(uploaded_images, start=1):
                st.subheader(f"📌 기사 사진 {idx} 분석")

                try:
                    result = analyze_image(uploaded_image)
                    st.markdown(result)
                except Exception as e:
                    st.error(f"이미지 분석 중 오류가 발생했습니다: {e}")

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

        if final_article.strip() == "":
            st.warning("기사 사진, 기사 URL, 기사 내용 중 하나를 입력해주세요.")
            st.stop()

        try:
            result = analyze_text(final_title, final_article)
            st.markdown(result)
        except Exception as e:
            st.error(f"기사 분석 중 오류가 발생했습니다: {e}")
